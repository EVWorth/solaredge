"""Library to interact with SolarEdge's monitoring API (async-first).

This module implements an async-first `AsyncMonitoringClient` that mirrors
the SolarEdge Monitoring API endpoints. The sync client will be added after
the async implementation (per repository plan).
"""

from __future__ import annotations

from abc import ABC
from typing import Any
from collections.abc import Iterable

import httpx

BASEURL = "https://monitoringapi.solaredge.com"


class BaseMonitoringClient(ABC):
    """Shared helpers for monitoring clients.

    Contains URL building, default params and simple timeout parsing. Concrete
    clients (sync/async) should inherit this to reuse utilities.
    """

    def __init__(self, api_key: str, base_url: str = BASEURL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _build_url(self, *parts: Any) -> str:
        """Join base_url with path parts into a single URL."""
        pieces = [str(p).strip("/") for p in parts if p is not None]
        return "/".join([self.base_url, *pieces])

    def _default_params(self) -> dict:
        return {"api_key": self.api_key}

    def _parse_timeout(self, timeout: float | None) -> float:
        return timeout if timeout is not None else 10.0


class AsyncMonitoringClient(BaseMonitoringClient):
    """Asynchronous client for the SolarEdge Monitoring API.

    Usage:
        async with AsyncMonitoringClient(api_key) as client:
            overview = await client.get_overview(site_id)
    """

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = 10.0,
    ) -> None:
        super().__init__(api_key)
        self._external_client = client is not None
        self._timeout = self._parse_timeout(timeout)
        self.client = client or httpx.AsyncClient(timeout=self._timeout)

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
        if not self._external_client:
            await self.client.aclose()

    async def _request(self, method: str, path: str, params: dict | None = None) -> Any:
        url = self._build_url(path)
        combined = {**self._default_params(), **(params or {})}
        resp = await self.client.request(method, url, params=combined)
        resp.raise_for_status()
        return resp.json()

    async def get_list(
        self,
        size: int = 100,
        startIndex: int = 0,
        searchText: str = "",
        sortProperty: str = "",
        sortOrder: str = "ASC",
        status: str = "Active,Pending",
    ) -> dict:
        """Return a paginated list of sites for the account (async)."""
        path = "sites/list"
        params = {
            "size": size,
            "startIndex": startIndex,
            "sortOrder": sortOrder,
            "status": status,
        }
        if searchText:
            params["searchText"] = searchText
        if sortProperty:
            params["sortProperty"] = sortProperty
        return await self._request("GET", path, params=params)

    async def get_details(self, site_id: int) -> dict:
        """Get site details (async)."""
        path = f"site/{site_id}/details"
        return await self._request("GET", path)

    async def get_data_period(self, site_id: int) -> dict:
        """Return the site's energy data period (start/end) (async)."""
        path = f"site/{site_id}/dataPeriod"
        return await self._request("GET", path)

    async def get_energy(
        self, site_id: int, startDate: str, endDate: str, timeUnit: str = "DAY"
    ) -> dict:
        """Get aggregated energy for a site between two dates (async)."""
        path = f"site/{site_id}/energy"
        params = {"startDate": startDate, "endDate": endDate, "timeUnit": timeUnit}
        return await self._request("GET", path, params=params)

    async def get_time_frame_energy(
        self, site_id: int, startDate: str, endDate: str, timeUnit: str = "DAY"
    ) -> dict:
        """Get time-frame energy (async)."""
        path = f"site/{site_id}/timeFrameEnergy"
        params = {"startDate": startDate, "endDate": endDate, "timeUnit": timeUnit}
        return await self._request("GET", path, params=params)

    async def get_power(self, site_id: int, startTime: str, endTime: str) -> dict:
        """Return power measurements (15-minute resolution) for a timeframe (async)."""
        path = f"site/{site_id}/power"
        params = {"startTime": startTime, "endTime": endTime}
        return await self._request("GET", path, params=params)

    async def get_overview(self, site_id: int) -> dict:
        """Return a site overview (async)."""
        path = f"site/{site_id}/overview"
        return await self._request("GET", path)

    async def get_power_details(
        self,
        site_id: int,
        startTime: str,
        endTime: str,
        meters: Iterable[str] | None = None,
    ) -> dict:
        """Return detailed power measurements including optional meters (async)."""
        path = f"site/{site_id}/powerDetails"
        params = {"startTime": startTime, "endTime": endTime}
        if meters:
            params["meters"] = ",".join(meters)
        return await self._request("GET", path, params=params)

    async def get_energy_details(
        self,
        site_id: int,
        startTime: str,
        endTime: str,
        meters: Iterable[str] | None = None,
        timeUnit: str = "DAY",
    ) -> dict:
        """Return detailed energy breakdown (by meter/timeUnit) (async)."""
        path = f"site/{site_id}/energyDetails"
        params = {"startTime": startTime, "endTime": endTime, "timeUnit": timeUnit}
        if meters:
            params["meters"] = ",".join(meters)
        return await self._request("GET", path, params=params)

    async def get_current_power_flow(self, site_id: int) -> dict:
        """Return the current power flow (async)."""
        path = f"site/{site_id}/currentPowerFlow"
        return await self._request("GET", path)

    async def get_storage_data(
        self,
        site_id: int,
        startTime: str,
        endTime: str,
        serials: Iterable[str] | None = None,
    ) -> dict:
        """Return storage (battery) measurements for the timeframe (async)."""
        path = f"site/{site_id}/storageData"
        params = {"startTime": startTime, "endTime": endTime}
        if serials:
            params["serials"] = ",".join(serials)
        return await self._request("GET", path, params=params)


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
    ) -> None:
        super().__init__(api_key)
        self._external_client = client is not None
        self._timeout = self._parse_timeout(timeout)
        self.client = client or httpx.Client(timeout=self._timeout)

    def __enter__(self) -> MonitoringClient:
        """Enter the synchronous context manager and return self.

        When used as `with MonitoringClient(...)`, the internal httpx.Client
        will be closed on exit if this client created it.
        """
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Exit the synchronous context manager and close owned resources.

        If this client created the internal httpx.Client it will be closed;
        externally-provided clients are not closed.
        """
        if not self._external_client:
            self.client.close()

    def _request(self, method: str, path: str, params: dict | None = None) -> Any:
        """Perform a synchronous HTTP request and return parsed JSON.

        This mirrors the async `_request` helper but uses a blocking httpx.Client.
        """
        url = self._build_url(path)
        combined = {**self._default_params(), **(params or {})}
        resp = self.client.request(method, url, params=combined)
        resp.raise_for_status()
        return resp.json()

    # --- endpoints (sync mirror) ---
    def get_list(
        self,
        size: int = 100,
        startIndex: int = 0,
        searchText: str = "",
        sortProperty: str = "",
        sortOrder: str = "ASC",
        status: str = "Active,Pending",
    ) -> dict:
        """Return a paginated list of sites for the account (sync).

        Parameters mirror the SolarEdge `/sites/list` endpoint and control
        pagination, filtering and sorting.
        """
        path = "sites/list"
        params = {
            "size": size,
            "startIndex": startIndex,
            "sortOrder": sortOrder,
            "status": status,
        }
        if searchText:
            params["searchText"] = searchText
        if sortProperty:
            params["sortProperty"] = sortProperty
        return self._request("GET", path, params=params)

    def get_details(self, site_id: int) -> dict:
        """Get site details (sync).

        Returns parsed JSON from `/site/{siteId}/details`.
        """
        path = f"site/{site_id}/details"
        return self._request("GET", path)

    def get_data_period(self, site_id: int) -> dict:
        """Return the site's energy data period (start/end) (sync)."""
        path = f"site/{site_id}/dataPeriod"
        return self._request("GET", path)

    def get_energy(
        self, site_id: int, startDate: str, endDate: str, timeUnit: str = "DAY"
    ) -> dict:
        """Get aggregated energy for a site between two dates (sync)."""
        path = f"site/{site_id}/energy"
        params = {"startDate": startDate, "endDate": endDate, "timeUnit": timeUnit}
        return self._request("GET", path, params=params)

    def get_time_frame_energy(
        self, site_id: int, startDate: str, endDate: str, timeUnit: str = "DAY"
    ) -> dict:
        """Get time-frame energy (sync)."""
        path = f"site/{site_id}/timeFrameEnergy"
        params = {"startDate": startDate, "endDate": endDate, "timeUnit": timeUnit}
        return self._request("GET", path, params=params)

    def get_power(self, site_id: int, startTime: str, endTime: str) -> dict:
        """Return power measurements (15-minute resolution) for a timeframe (sync)."""
        path = f"site/{site_id}/power"
        params = {"startTime": startTime, "endTime": endTime}
        return self._request("GET", path, params=params)

    def get_overview(self, site_id: int) -> dict:
        """Return a site overview (sync)."""
        path = f"site/{site_id}/overview"
        return self._request("GET", path)

    def get_power_details(
        self,
        site_id: int,
        startTime: str,
        endTime: str,
        meters: Iterable[str] | None = None,
    ) -> dict:
        """Return detailed power measurements including optional meters (sync)."""
        path = f"site/{site_id}/powerDetails"
        params = {"startTime": startTime, "endTime": endTime}
        if meters:
            params["meters"] = ",".join(meters)
        return self._request("GET", path, params=params)

    def get_energy_details(
        self,
        site_id: int,
        startTime: str,
        endTime: str,
        meters: Iterable[str] | None = None,
        timeUnit: str = "DAY",
    ) -> dict:
        """Return detailed energy breakdown (by meter/timeUnit) (sync)."""
        path = f"site/{site_id}/energyDetails"
        params = {"startTime": startTime, "endTime": endTime, "timeUnit": timeUnit}
        if meters:
            params["meters"] = ",".join(meters)
        return self._request("GET", path, params=params)

    def get_current_power_flow(self, site_id: int) -> dict:
        """Return the current power flow (sync)."""
        path = f"site/{site_id}/currentPowerFlow"
        return self._request("GET", path)

    def get_storage_data(
        self,
        site_id: int,
        startTime: str,
        endTime: str,
        serials: Iterable[str] | None = None,
    ) -> dict:
        """Return storage (battery) measurements for the timeframe (sync)."""
        path = f"site/{site_id}/storageData"
        params = {"startTime": startTime, "endTime": endTime}
        if serials:
            params["serials"] = ",".join(serials)
        return self._request("GET", path, params=params)
