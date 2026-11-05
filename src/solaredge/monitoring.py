"""Clients for SolarEdge's Monitoring API (V2)."""

from __future__ import annotations

import asyncio
from abc import ABC
from typing import Any
from datetime import datetime
from collections.abc import Mapping, Iterable

import httpx

from . import _endpoints
from ._endpoints import (
    Request,
    PowerUnit,
    DeviceType,
    EnergyUnit,
    Resolution,
)
from .exceptions import (
    SolarEdgeResponseError,
    SolarEdgeValidationError,
    error_from_response,
)

DEFAULT_BASE_URL = "https://monitoringapi.solaredge.com/v2"
MAX_CONCURRENT_REQUESTS = 3
API_KEY_HEADER = "X-API-Key"


class BaseMonitoringClient(ABC):  # noqa: B024 - shared helpers, not an interface
    """Shared helpers for monitoring clients.

    Holds URL building, authentication, timeout parsing and the
    request/response plumbing that does not depend on whether I/O is blocking.
    Concrete clients (sync/async) inherit this and supply only the transport.
    """

    def __init__(self, api_key: str, base_url: str | None = None):
        if not api_key:
            raise SolarEdgeValidationError("api_key is required.")
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    def __repr__(self) -> str:
        """Describe the client without exposing the API key."""
        return f"{type(self).__name__}(base_url={self.base_url!r})"

    def _build_url(self, *parts: Any) -> str:
        """Join base_url with path parts into a single URL."""
        pieces = [str(p).strip("/") for p in parts if p is not None]
        return "/".join([self.base_url, *pieces])

    def _headers(self) -> dict[str, str]:
        return {API_KEY_HEADER: self.api_key, "Accept": "application/json"}

    def _parse_timeout(self, timeout: float | None) -> float:
        return timeout if timeout is not None else 10.0

    def _prepare(self, request: Request) -> tuple[str, list[tuple[str, Any]]]:
        """Resolve a Request into the URL and query params to send.

        Params whose value is None are dropped: httpx encodes them as empty
        query values rather than omitting them.
        """
        url = self._build_url(request.path)
        params = [(k, v) for k, v in (request.params or []) if v is not None]
        return url, params

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

        try:
            return response.json()
        except ValueError as exc:
            raise SolarEdgeResponseError(
                f"The API returned a non-JSON body (HTTP {response.status_code}) "
                f"for {response.request.url}"
            ) from exc


class AsyncMonitoringClient(BaseMonitoringClient):
    """Asynchronous client for the SolarEdge Monitoring API (V2).

    Authenticates with a Fleet Access API key, sent in the ``X-API-Key``
    header. Limits itself to 3 concurrent requests.

    Usage:
        async with AsyncMonitoringClient(api_key) as client:
            overview = await client.get_overview(site_id)
    """

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = 10.0,
        base_url: str | None = None,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self._external_client = client is not None
        self._timeout = self._parse_timeout(timeout)
        self.client = client or httpx.AsyncClient(timeout=self._timeout)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def __aenter__(self) -> AsyncMonitoringClient:
        """Enter the async context manager and return self.

        The internal httpx.AsyncClient will be closed on exit if this
        instance created it.
        """
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the async context manager and close owned resources.

        If this instance created the internal httpx.AsyncClient it will be
        closed; externally-provided clients are not closed.
        """
        await self.aclose()

    async def aclose(self) -> None:
        """Close the internal httpx.AsyncClient if this instance created it.

        Does nothing when the client was supplied by the caller, who owns its
        lifetime.
        """
        if self._external_client:
            return
        await self.client.aclose()

    async def _send(self, request: Request) -> Any:
        """Send a prepared request, respecting the concurrency limit."""
        async with self._semaphore:
            url, params = self._prepare(request)
            response = await self.client.request(
                method=request.method,
                url=url,
                params=params,
                headers=self._headers(),
            )
            return self._parse_response(response)

    async def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        """GET any V2 path, for endpoints without a dedicated method (async).

        Args:
            path: Path relative to the base URL, e.g. ``"sites/123/alerts"``.
            params: Query parameters. Datetimes must be timezone-aware and are
                sent as ISO 8601; list values are sent as a repeated key.
        """
        return await self._send(_endpoints.raw(path, params))

    async def get_sites(self) -> Any:
        """Return the sites this API key can access (async).

        Listing sites requires Fleet Access.
        """
        return await self._send(_endpoints.sites())

    async def get_site_details(self, site_id: int) -> dict:
        """Return a site's details (async)."""
        return await self._send(_endpoints.site_details(site_id))

    async def get_overview(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict:
        """Return the site overview, optionally for a time range (async).

        Covers production, consumption, grid and storage figures.
        """
        return await self._send(_endpoints.overview(site_id, start, end))

    async def get_energy(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        resolution: Resolution = "DAY",
        unit: EnergyUnit = "WH",
    ) -> dict:
        """Return site energy between two timezone-aware datetimes (async)."""
        return await self._send(
            _endpoints.energy(site_id, start, end, resolution, unit)
        )

    async def get_power(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        resolution: Resolution = "QUARTER_HOUR",
        unit: PowerUnit = "W",
    ) -> dict:
        """Return site power between two timezone-aware datetimes (async).

        QUARTER_HOUR is the finest resolution the API offers; each value is
        the average over its interval, not an instantaneous reading.
        """
        return await self._send(_endpoints.power(site_id, start, end, resolution, unit))

    async def get_lifetime_energy(self, site_id: int) -> dict:
        """Return the site's lifetime production counter (async)."""
        return await self._send(_endpoints.lifetime_energy(site_id))

    async def get_current_power_flow(self, site_id: int) -> dict:
        """Return the site's current power flow (async).

        Requires an Advanced Monitoring plan; other plans get HTTP 403, raised
        as SolarEdgeAuthError.
        """
        return await self._send(_endpoints.power_flow(site_id))

    async def get_devices(
        self,
        site_id: int,
        types: Iterable[DeviceType] | None = None,
    ) -> Any:
        """Return the site's devices, optionally filtered by type (async).

        Replaces V1's inventory and components list.
        """
        return await self._send(_endpoints.devices(site_id, types))

    async def get_storage_lifetime_energy(
        self, site_id: int, start: datetime, end: datetime
    ) -> dict:
        """Return battery charge/discharge counters for a time range (async)."""
        return await self._send(_endpoints.storage_lifetime_energy(site_id, start, end))

    async def get_storage_telemetry(
        self, site_id: int, start: datetime, end: datetime
    ) -> dict:
        """Return battery telemetry for a time range (async)."""
        return await self._send(_endpoints.storage_telemetry(site_id, start, end))

    async def get_meters_telemetry(
        self, site_id: int, start: datetime, end: datetime
    ) -> dict:
        """Return meter telemetry for a time range (async)."""
        return await self._send(_endpoints.meters_telemetry(site_id, start, end))

    async def get_inverters_telemetry(
        self, site_id: int, start: datetime, end: datetime
    ) -> dict:
        """Return inverter telemetry for a time range (async)."""
        return await self._send(_endpoints.inverters_telemetry(site_id, start, end))


class MonitoringClient(BaseMonitoringClient):
    """Synchronous client that mirrors `AsyncMonitoringClient` using httpx.Client.

    Usage:
        with MonitoringClient(api_key) as client:
            overview = client.get_overview(site_id)
    """

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        timeout: float | None = 10.0,
        base_url: str | None = None,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self._external_client = client is not None
        self._timeout = self._parse_timeout(timeout)
        self.client = client or httpx.Client(timeout=self._timeout)

    def __enter__(self) -> MonitoringClient:
        """Enter the synchronous context manager and return self.

        The internal httpx.Client will be closed on exit if this client
        created it.
        """
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Exit the synchronous context manager and close owned resources.

        If this client created the internal httpx.Client it will be closed;
        externally-provided clients are not closed.
        """
        self.close()

    def close(self) -> None:
        """Close the internal httpx.Client if this instance created it.

        Does nothing when the client was supplied by the caller, who owns its
        lifetime.
        """
        if self._external_client:
            return
        self.client.close()

    def _send(self, request: Request) -> Any:
        """Send a prepared request using the blocking client."""
        url, params = self._prepare(request)
        response = self.client.request(
            method=request.method,
            url=url,
            params=params,
            headers=self._headers(),
        )
        return self._parse_response(response)

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        """GET any V2 path, for endpoints without a dedicated method (sync).

        Args:
            path: Path relative to the base URL, e.g. ``"sites/123/alerts"``.
            params: Query parameters. Datetimes must be timezone-aware and are
                sent as ISO 8601; list values are sent as a repeated key.
        """
        return self._send(_endpoints.raw(path, params))

    def get_sites(self) -> Any:
        """Return the sites this API key can access (sync).

        Listing sites requires Fleet Access.
        """
        return self._send(_endpoints.sites())

    def get_site_details(self, site_id: int) -> dict:
        """Return a site's details (sync)."""
        return self._send(_endpoints.site_details(site_id))

    def get_overview(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict:
        """Return the site overview, optionally for a time range (sync).

        Covers production, consumption, grid and storage figures.
        """
        return self._send(_endpoints.overview(site_id, start, end))

    def get_energy(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        resolution: Resolution = "DAY",
        unit: EnergyUnit = "WH",
    ) -> dict:
        """Return site energy between two timezone-aware datetimes (sync)."""
        return self._send(_endpoints.energy(site_id, start, end, resolution, unit))

    def get_power(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        resolution: Resolution = "QUARTER_HOUR",
        unit: PowerUnit = "W",
    ) -> dict:
        """Return site power between two timezone-aware datetimes (sync).

        QUARTER_HOUR is the finest resolution the API offers; each value is
        the average over its interval, not an instantaneous reading.
        """
        return self._send(_endpoints.power(site_id, start, end, resolution, unit))

    def get_lifetime_energy(self, site_id: int) -> dict:
        """Return the site's lifetime production counter (sync)."""
        return self._send(_endpoints.lifetime_energy(site_id))

    def get_current_power_flow(self, site_id: int) -> dict:
        """Return the site's current power flow (sync).

        Requires an Advanced Monitoring plan; other plans get HTTP 403, raised
        as SolarEdgeAuthError.
        """
        return self._send(_endpoints.power_flow(site_id))

    def get_devices(
        self,
        site_id: int,
        types: Iterable[DeviceType] | None = None,
    ) -> Any:
        """Return the site's devices, optionally filtered by type (sync).

        Replaces V1's inventory and components list.
        """
        return self._send(_endpoints.devices(site_id, types))

    def get_storage_lifetime_energy(
        self, site_id: int, start: datetime, end: datetime
    ) -> dict:
        """Return battery charge/discharge counters for a time range (sync)."""
        return self._send(_endpoints.storage_lifetime_energy(site_id, start, end))

    def get_storage_telemetry(
        self, site_id: int, start: datetime, end: datetime
    ) -> dict:
        """Return battery telemetry for a time range (sync)."""
        return self._send(_endpoints.storage_telemetry(site_id, start, end))

    def get_meters_telemetry(
        self, site_id: int, start: datetime, end: datetime
    ) -> dict:
        """Return meter telemetry for a time range (sync)."""
        return self._send(_endpoints.meters_telemetry(site_id, start, end))

    def get_inverters_telemetry(
        self, site_id: int, start: datetime, end: datetime
    ) -> dict:
        """Return inverter telemetry for a time range (sync)."""
        return self._send(_endpoints.inverters_telemetry(site_id, start, end))
