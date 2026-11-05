"""Exceptions raised by the SolarEdge clients.

Every failure this library produces derives from :class:`SolarEdgeError`, so
callers can handle errors without importing or depending on ``httpx``. The
originating ``httpx`` exception is always preserved as ``__cause__`` for
callers who do want the transport-level detail.
"""

from __future__ import annotations

from typing import Any

import httpx

__all__ = [
    "SolarEdgeAPIError",
    "SolarEdgeAuthError",
    "SolarEdgeError",
    "SolarEdgeNotFoundError",
    "SolarEdgeRateLimitError",
    "SolarEdgeResponseError",
    "SolarEdgeServerError",
    "SolarEdgeValidationError",
]


class SolarEdgeError(Exception):
    """Base class for every error raised by this library."""


class SolarEdgeValidationError(SolarEdgeError, ValueError):
    """A request was rejected locally, before anything was sent.

    Also subclasses :class:`ValueError`, so existing ``except ValueError``
    handlers continue to work.
    """


class SolarEdgeAPIError(SolarEdgeError):
    """The API responded with an error status.

    Attributes:
        status_code: HTTP status code returned by the API.
        response_body: Parsed JSON body if the response carried one, else the
            decoded text, else None.
        url: The requested URL. The API key travels in a header, so it never
            appears here.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: Any = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.url = url


class SolarEdgeAuthError(SolarEdgeAPIError):
    """The API key was rejected, or the request is not permitted (401, 403).

    V2 also returns 403 for endpoints the account's plan does not include,
    such as power flow on the free tier.
    """


class SolarEdgeNotFoundError(SolarEdgeAPIError):
    """The requested site, equipment or endpoint does not exist (404)."""


class SolarEdgeRateLimitError(SolarEdgeAPIError):
    """The per-minute or monthly credit quota was exceeded (429).

    No automatic retry is attempted.

    Attributes:
        retry_after: The ``Retry-After`` header value if the API sent one,
            else None. The API omits it when the monthly quota runs out.
        limits: The ``x-ratelimit-*`` headers the API sent, as integers, e.g.
            ``{"x-ratelimit-remaining-minute": 0}``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: Any = None,
        url: str | None = None,
        retry_after: str | None = None,
        limits: dict[str, int] | None = None,
    ) -> None:
        super().__init__(
            message, status_code=status_code, response_body=response_body, url=url
        )
        self.retry_after = retry_after
        self.limits = limits or {}


class SolarEdgeServerError(SolarEdgeAPIError):
    """The API failed to handle a valid request (5xx)."""


class SolarEdgeResponseError(SolarEdgeError):
    """The API returned a success status with a body that could not be parsed."""


def _response_body(response: httpx.Response) -> Any:
    """Extract the most useful representation of an error body."""
    try:
        return response.json()
    except ValueError:
        try:
            return response.text or None
        except UnicodeDecodeError:
            return None


def _rate_limit_headers(headers: httpx.Headers) -> dict[str, int]:
    """Collect the documented ``x-ratelimit-*`` headers that parse as integers."""
    return {
        name.lower(): int(value)
        for name, value in headers.items()
        if name.lower().startswith("x-ratelimit-") and value.strip().isdecimal()
    }


def error_from_response(response: httpx.Response) -> SolarEdgeAPIError:
    """Build the most specific SolarEdgeAPIError for an error response."""
    status = response.status_code
    body = _response_body(response)
    url = str(response.request.url) if response.request is not None else None

    if status in (401, 403):
        cls: type[SolarEdgeAPIError] = SolarEdgeAuthError
        summary = (
            "Authentication failed or not permitted; check the API key and "
            "that your plan includes this endpoint"
        )
    elif status == 404:
        cls = SolarEdgeNotFoundError
        summary = "The requested resource was not found"
    elif status == 429:
        cls = SolarEdgeRateLimitError
        summary = "Rate limit exceeded"
    elif status >= 500:
        cls = SolarEdgeServerError
        summary = "The SolarEdge API failed to handle the request"
    else:
        cls = SolarEdgeAPIError
        summary = "The SolarEdge API returned an error"

    message = f"{summary} (HTTP {status})"
    if url:
        message = f"{message} for {url}"
    if body:
        message = f"{message}: {body}"

    if cls is SolarEdgeRateLimitError:
        return SolarEdgeRateLimitError(
            message,
            status_code=status,
            response_body=body,
            url=url,
            retry_after=response.headers.get("Retry-After"),
            limits=_rate_limit_headers(response.headers),
        )
    return cls(message, status_code=status, response_body=body, url=url)
