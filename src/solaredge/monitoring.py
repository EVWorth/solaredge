"""Clients for SolarEdge's Monitoring API (V2).

The operations themselves live in :mod:`solaredge._operations`; this module
supplies the transport. :class:`MonitoringClient` blocks and returns parsed
JSON; :class:`AsyncMonitoringClient` returns awaitables of the same.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .oauth import OAuth2
from ._endpoints import Request
from .exceptions import (
    SolarEdgeResponseError,
    SolarEdgeValidationError,
    error_from_response,
)
from ._operations import Sync, Async, Operations

DEFAULT_BASE_URL = "https://monitoringapi.solaredge.com/v2"
DEFAULT_TIMEOUT = 10.0
MAX_CONCURRENT_REQUESTS = 3
API_KEY_HEADER = "X-API-Key"


class BaseMonitoringClient:
    """Shared configuration and request/response plumbing.

    Holds URL building, authentication and response parsing, none of which
    depends on whether I/O is blocking.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        access_token: str | None = None,
        oauth: OAuth2 | None = None,
    ):
        given = [x for x in (api_key, access_token, oauth) if x]
        if len(given) != 1:
            raise SolarEdgeValidationError(
                "Pass exactly one of api_key (Fleet Access), access_token or "
                "oauth (Site Access)."
            )
        self.api_key = api_key
        if access_token:
            oauth = OAuth2(access_token)
        self.oauth = oauth
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    def __repr__(self) -> str:
        """Describe the client without exposing credentials."""
        return f"{type(self).__name__}(base_url={self.base_url!r})"

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request_kwargs(self, request: Request) -> dict[str, Any]:
        """Resolve a Request into keyword arguments for ``httpx.request``.

        Params whose value is None are dropped: httpx encodes them as empty
        query values rather than omitting them.
        """
        return {
            "method": request.method,
            "url": self._url(request.path),
            "params": [(k, v) for k, v in (request.params or []) if v is not None],
            "headers": self._headers(),
            # Site Access: the OAuth2 auth adds the bearer token and refreshes it.
            "auth": self.oauth,
        }

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers[API_KEY_HEADER] = self.api_key
        return headers

    @staticmethod
    def _parse_response(response: httpx.Response) -> Any:
        """Return the parsed JSON body, translating failures.

        Raises a SolarEdgeError subclass rather than an httpx exception, so
        callers never need to depend on this library's transport. The original
        httpx error is preserved as __cause__.
        """
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise error_from_response(response) from exc

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise SolarEdgeResponseError(
                f"The API returned a non-JSON body (HTTP {response.status_code}) "
                f"for {response.request.url}"
            ) from exc


class AsyncMonitoringClient(BaseMonitoringClient, Operations[Async]):
    """Asynchronous client for the SolarEdge Monitoring API (V2).

    Authenticate with exactly one of:

    - ``api_key``: a Fleet Access key (installers), sent as ``X-API-Key``.
    - ``access_token``: a Site Access bearer token you obtain and refresh
      yourself.
    - ``oauth``: a :class:`solaredge.oauth.OAuth2`, which refreshes the Site
      Access token automatically. This is the route for homeowners.

    Limits itself to 3 concurrent requests.

    Usage:
        async with AsyncMonitoringClient(api_key) as client:
            overview = await client.get_overview(site_id)
    """

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        base_url: str | None = None,
        *,
        access_token: str | None = None,
        oauth: OAuth2 | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            access_token=access_token,
            oauth=oauth,
        )
        self._external_client = client is not None
        self.client = client or httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT if timeout is None else timeout
        )
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def __aenter__(self) -> AsyncMonitoringClient:
        """Enter the async context manager and return self."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Close the internal httpx.AsyncClient if this instance created it."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the internal httpx.AsyncClient if this instance created it.

        Does nothing when the client was supplied by the caller, who owns its
        lifetime.
        """
        if not self._external_client:
            await self.client.aclose()

    async def _call(self, request: Request) -> Any:
        """Send a request, respecting the concurrency limit."""
        async with self._semaphore:
            response = await self.client.request(**self._request_kwargs(request))
        return self._parse_response(response)


class MonitoringClient(BaseMonitoringClient, Operations[Sync]):
    """Synchronous client for the SolarEdge Monitoring API (V2).

    Mirrors :class:`AsyncMonitoringClient` using ``httpx.Client``.

    Usage:
        with MonitoringClient(api_key) as client:
            overview = client.get_overview(site_id)
    """

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        base_url: str | None = None,
        *,
        access_token: str | None = None,
        oauth: OAuth2 | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            access_token=access_token,
            oauth=oauth,
        )
        self._external_client = client is not None
        self.client = client or httpx.Client(
            timeout=DEFAULT_TIMEOUT if timeout is None else timeout
        )

    def __enter__(self) -> MonitoringClient:
        """Enter the context manager and return self."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Close the internal httpx.Client if this instance created it."""
        self.close()

    def close(self) -> None:
        """Close the internal httpx.Client if this instance created it.

        Does nothing when the client was supplied by the caller, who owns its
        lifetime.
        """
        if not self._external_client:
            self.client.close()

    def _call(self, request: Request) -> Any:
        """Send a request using the blocking client."""
        return self._parse_response(
            self.client.request(**self._request_kwargs(request))
        )
