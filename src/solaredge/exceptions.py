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

_REDACTED = "REDACTED"


def redact_url(url: httpx.URL | str) -> str:
    """Return `url` with the api_key query value replaced.

    SolarEdge authenticates by query parameter, so the key appears in every
    request URL. Error messages are routinely pasted into bug reports, so the
    key is masked anywhere this library renders a URL.
    """
    url = httpx.URL(url)
    if "api_key" in url.params:
        url = url.copy_set_param("api_key", _REDACTED)
    return str(url)


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
        url: The requested URL, with the api_key value redacted.
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
    """The API key was missing, invalid, or not permitted (401, 403)."""


class SolarEdgeNotFoundError(SolarEdgeAPIError):
    """The requested site, equipment or endpoint does not exist (404)."""


class SolarEdgeRateLimitError(SolarEdgeAPIError):
    """The account's request quota or concurrency limit was exceeded (429)."""


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


def error_from_response(response: httpx.Response) -> SolarEdgeAPIError:
    """Build the most specific SolarEdgeAPIError for an error response."""
    status = response.status_code
    body = _response_body(response)
    url = redact_url(response.request.url) if response.request is not None else None

    if status in (401, 403):
        cls: type[SolarEdgeAPIError] = SolarEdgeAuthError
        summary = "Authentication failed; check the API key"
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

    return cls(message, status_code=status, response_body=body, url=url)
