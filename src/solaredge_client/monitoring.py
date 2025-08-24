"""Library to interact with SolarEdge's monitoring API (async-first).

This module implements an async-first `AsyncMonitoringClient` that mirrors
the SolarEdge Monitoring API endpoints. The sync client will be added after
the async implementation (per repository plan).
"""

from __future__ import annotations

import asyncio
from abc import ABC
from typing import Any
from collections.abc import Iterable

import httpx

DEFAULT_BASE_URL = "https://monitoringapi.solaredge.com"
MAX_CONCURRENT_REQUESTS = 3


class BaseMonitoringClient(ABC):
    """Shared helpers for monitoring clients.

    Contains URL building, default params and simple timeout parsing. Concrete
    clients (sync/async) should inherit this to reuse utilities.
    """

    def __init__(self, api_key: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

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

    Automatically limits concurrent requests to 3 per the API specification.

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
        super().__init__(
            api_key=api_key,
            base_url=base_url,
        )
        self._external_client = client is not None
        self._timeout = self._parse_timeout(timeout)
        self.client = client or httpx.AsyncClient(timeout=self._timeout)

        # Semaphore to limit concurrent requests per SolarEdge API specification
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
        if not self._external_client:
            await self.client.aclose()

    async def _make_request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
    ) -> Any:
        async with self._semaphore:  # Acquire semaphore before making request
            url = self._build_url(path)
            combined = {**self._default_params(), **(params or {})}
            response = await self.client.request(
                method=method,
                url=url,
                params=combined,
            )
            response.raise_for_status()
            return response.json()

    async def get_list(
        self,
        size: int = 100,
        start_index: int = 0,
        search_text: str = "",
        sort_property: str = "",
        sort_order: str = "ASC",
        status: str = "Active,Pending",
    ) -> dict:
        """Return a paginated list of sites for the account (async)."""
        path = "sites/list"
        params = {
            "size": size,
            "startIndex": start_index,
            "sortOrder": sort_order,
            "status": status,
        }
        if search_text:
            params["searchText"] = search_text
        if sort_property:
            params["sortProperty"] = sort_property
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_details(self, site_id: int) -> dict:
        """Get site details (async)."""
        path = f"site/{site_id}/details"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_data_period(self, site_id: int) -> dict:
        """Return the site's energy data period (start/end) (async)."""
        path = f"site/{site_id}/dataPeriod"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_energy(
        self,
        site_id: int,
        start_date: str,
        end_date: str,
        time_unit: str = "DAY",
    ) -> dict:
        """Get aggregated energy for a site between two dates (async)."""
        path = f"site/{site_id}/energy"
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
        }
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_time_frame_energy(
        self,
        site_id: int,
        start_date: str,
        end_date: str,
        time_unit: str = "DAY",
    ) -> dict:
        """Get time-frame energy (async)."""
        path = f"site/{site_id}/timeFrameEnergy"
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
        }
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_power(
        self,
        site_id: int,
        start_time: str,
        end_time: str,
    ) -> dict:
        """Return power measurements (15-minute resolution) for a timeframe (async)."""
        path = f"site/{site_id}/power"
        params = {
            "startTime": start_time,
            "endTime": end_time,
        }
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_overview(self, site_id: int) -> dict:
        """Return a site overview (async)."""
        path = f"site/{site_id}/overview"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_power_details(
        self,
        site_id: int,
        start_time: str,
        end_time: str,
        meters: Iterable[str] | None = None,
    ) -> dict:
        """Return detailed power measurements including optional meters (async)."""
        path = f"site/{site_id}/powerDetails"
        params = {
            "startTime": start_time,
            "endTime": end_time,
        }
        if meters:
            params["meters"] = ",".join(meters)
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_energy_details(
        self,
        site_id: int,
        start_time: str,
        end_time: str,
        meters: Iterable[str] | None = None,
        time_unit: str = "DAY",
    ) -> dict:
        """Return detailed energy breakdown (by meter/timeUnit) (async)."""
        path = f"site/{site_id}/energyDetails"
        params = {
            "startTime": start_time,
            "endTime": end_time,
            "timeUnit": time_unit,
        }
        if meters:
            params["meters"] = ",".join(meters)
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_current_power_flow(self, site_id: int) -> dict:
        """Return the current power flow (async)."""
        path = f"site/{site_id}/currentPowerFlow"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_storage_data(
        self,
        site_id: int,
        start_time: str,
        end_time: str,
        serials: Iterable[str] | None = None,
    ) -> dict:
        """Return storage (battery) measurements for the timeframe (async)."""
        path = f"site/{site_id}/storageData"
        params = {
            "startTime": start_time,
            "endTime": end_time,
        }
        if serials:
            params["serials"] = ",".join(serials)
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )


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
        super().__init__(
            api_key=api_key,
            base_url=base_url,
        )
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
        combined = {
            **self._default_params(),
            **(params or {}),
        }
        response = self.client.request(
            method=method,
            url=url,
            params=combined,
        )
        response.raise_for_status()
        return response.json()

    def get_list(
        self,
        size: int = 100,
        start_index: int = 0,
        search_text: str = "",
        sort_property: str = "",
        sort_order: str = "ASC",
        status: str = "Active,Pending",
    ) -> dict:
        """Return a paginated list of sites for the account (sync).

        Parameters mirror the SolarEdge `/sites/list` endpoint and control
        pagination, filtering and sorting.
        """
        path = "sites/list"
        params = {
            "size": size,
            "startIndex": start_index,
            "sortOrder": sort_order,
            "status": status,
        }
        if search_text:
            params["searchText"] = search_text
        if sort_property:
            params["sortProperty"] = sort_property
        return self._request(
            method="GET",
            path=path,
            params=params,
        )

    def get_details(self, site_id: int) -> dict:
        """Get site details (sync).

        Returns parsed JSON from `/site/{siteId}/details`.
        """
        path = f"site/{site_id}/details"
        return self._request(
            method="GET",
            path=path,
        )

    def get_data_period(self, site_id: int) -> dict:
        """Return the site's energy data period (start/end) (sync)."""
        path = f"site/{site_id}/dataPeriod"
        return self._request(
            method="GET",
            path=path,
        )

    def get_energy(
        self,
        site_id: int,
        start_date: str,
        end_date: str,
        time_unit: str = "DAY",
    ) -> dict:
        """Get aggregated energy for a site between two dates (sync)."""
        path = f"site/{site_id}/energy"
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
        }
        return self._request(
            method="GET",
            path=path,
            params=params,
        )

    def get_time_frame_energy(
        self,
        site_id: int,
        start_date: str,
        end_date: str,
        time_unit: str = "DAY",
    ) -> dict:
        """Get time-frame energy (sync)."""
        path = f"site/{site_id}/timeFrameEnergy"
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
        }
        return self._request(
            method="GET",
            path=path,
            params=params,
        )

    def get_power(
        self,
        site_id: int,
        start_time: str,
        end_time: str,
    ) -> dict:
        """Return power measurements (15-minute resolution) for a timeframe (sync)."""
        path = f"site/{site_id}/power"
        params = {
            "startTime": start_time,
            "endTime": end_time,
        }
        return self._request(
            method="GET",
            path=path,
            params=params,
        )

    def get_overview(self, site_id: int) -> dict:
        """Return a site overview (sync)."""
        path = f"site/{site_id}/overview"
        return self._request(
            method="GET",
            path=path,
        )

    def get_power_details(
        self,
        site_id: int,
        start_time: str,
        end_time: str,
        meters: Iterable[str] | None = None,
    ) -> dict:
        """Return detailed power measurements including optional meters (sync)."""
        path = f"site/{site_id}/powerDetails"
        params = {
            "startTime": start_time,
            "endTime": end_time,
        }
        if meters:
            params["meters"] = ",".join(meters)
        return self._request(
            method="GET",
            path=path,
            params=params,
        )

    def get_energy_details(
        self,
        site_id: int,
        start_time: str,
        end_time: str,
        meters: Iterable[str] | None = None,
        time_unit: str = "DAY",
    ) -> dict:
        """Return detailed energy breakdown (by meter/timeUnit) (sync)."""
        path = f"site/{site_id}/energyDetails"
        params = {
            "startTime": start_time,
            "endTime": end_time,
            "timeUnit": time_unit,
        }
        if meters:
            params["meters"] = ",".join(meters)
        return self._request(
            method="GET",
            path=path,
            params=params,
        )

    def get_current_power_flow(self, site_id: int) -> dict:
        """Return the current power flow (sync)."""
        path = f"site/{site_id}/currentPowerFlow"
        return self._request(
            method="GET",
            path=path,
        )

    def get_storage_data(
        self,
        site_id: int,
        start_time: str,
        end_time: str,
        serials: Iterable[str] | None = None,
    ) -> dict:
        """Return storage (battery) measurements for the timeframe (sync)."""
        path = f"site/{site_id}/storageData"
        params = {
            "startTime": start_time,
            "endTime": end_time,
        }
        if serials:
            params["serials"] = ",".join(serials)
        return self._request(
            method="GET",
            path=path,
            params=params,
        )
