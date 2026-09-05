"""Library to interact with SolarEdge's monitoring API."""

from __future__ import annotations

import asyncio
from abc import ABC
from typing import Any, Literal
from datetime import datetime
from collections.abc import Iterable

import httpx

from . import _endpoints
from ._endpoints import (
    Meter,
    Request,
    TimeUnit,
    SortOrder,
    SiteStatus,
    SystemUnits,
    MeterReading,
    SiteSortProperty,
    ValidatedTimeUnit,
    AccountSortProperty,
)

DEFAULT_BASE_URL = "https://monitoringapi.solaredge.com"
MAX_CONCURRENT_REQUESTS = 3


class BaseMonitoringClient(ABC):  # noqa: B024 - shared helpers, not an interface
    """Shared helpers for monitoring clients.

    Holds URL building, default params, timeout parsing and the request/response
    plumbing that does not depend on whether I/O is blocking. Concrete clients
    (sync/async) inherit this and supply only the transport.
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

    def _validate_timeframe(
        self,
        time_unit: ValidatedTimeUnit,
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """Validate the time frame for API requests.

        throws an error or returns None.
        """
        _endpoints.validate_timeframe(time_unit, start_date, end_date)

    def _prepare(self, request: Request) -> tuple[str, dict[str, Any]]:
        """Resolve a Request into the URL and query params to send.

        Params whose value is None are dropped: httpx encodes them as empty
        query values rather than omitting them.
        """
        url = self._build_url(request.path)
        combined = {**self._default_params(), **(request.params or {})}
        return url, {k: v for k, v in combined.items() if v is not None}

    @staticmethod
    def _parse_response(response: httpx.Response, raw: bool) -> Any:
        """Raise for error status, then return raw bytes or parsed JSON."""
        response.raise_for_status()
        return response.content if raw else response.json()


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

    async def aclose(self) -> None:
        """Close the internal httpx.Client if owned by this instance."""
        if self._external_client:
            raise ValueError("Will not close externally provided httpx.Client.")
        await self.client.aclose()

    async def _send(self, request: Request) -> Any:
        """Send a prepared request, respecting the concurrency limit."""
        async with self._semaphore:  # Acquire semaphore before making request
            url, params = self._prepare(request)
            response = await self.client.request(
                method=request.method,
                url=url,
                params=params,
            )
            return self._parse_response(response, request.raw)

    async def get_site_list(
        self,
        size: int = 100,
        start_index: int = 0,
        search_text: str | None = None,
        sort_property: SiteSortProperty | None = None,
        sort_order: SortOrder = "ASC",
        status: list[SiteStatus] | Literal["All"] | None = None,
    ) -> dict:
        """Return a paginated list of sites for the account (async).

        Args:
            size: Number of sites to return per page (max 100)
            start_index: Starting index for pagination
            search_text: Text to search for across multiple fields. The API will
                search in: Name, Notes, Email, Country, State, City, Zip, Full address
            sort_property: Property to sort by
            sort_order: Sort order ("ASC" or "DESC")
            status: Site status filter (["Active", "Pending"] by default)
        """
        return await self._send(
            _endpoints.site_list(
                size, start_index, search_text, sort_property, sort_order, status
            )
        )

    async def get_site_details(self, site_id: int) -> dict:
        """Get site details (async)."""
        return await self._send(_endpoints.site_details(site_id))

    async def get_site_data(self, site_ids: list[int]) -> dict:
        """Return the site's energy data period (start/end) (async)."""
        return await self._send(_endpoints.site_data(site_ids))

    async def get_energy(
        self,
        site_ids: list[int],
        start_date: datetime,
        end_date: datetime,
        time_unit: TimeUnit = "DAY",
    ) -> dict:
        """Get aggregated energy for a site between two dates (async).

        this endpoint returns the same energy measurements
        that appear in the Site Dashboard.
        """
        return await self._send(
            _endpoints.energy(site_ids, start_date, end_date, time_unit)
        )

    async def get_time_frame_energy(
        self,
        site_ids: list[int],
        start_date: datetime,
        end_date: datetime,
        time_unit: TimeUnit = "DAY",
    ) -> dict:
        """Get time-frame energy (async).

        This endpoint only returns on-grid energy for the requested period.
        In sites with storage/backup, this may mean that results can differ from what appears in the Site Dashboard.
        Use the regular Site Energy API to obtain results that match the Site Dashboard calculation.
        """  # noqa: E501
        return await self._send(
            _endpoints.time_frame_energy(site_ids, start_date, end_date, time_unit)
        )

    async def get_power(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Return power measurements (15-minute resolution) for a timeframe (async)."""
        return await self._send(_endpoints.power(site_id, start_time, end_time))

    async def get_overview(self, site_ids: list[int]) -> dict:
        """Return a site overview (async)."""
        return await self._send(_endpoints.overview(site_ids))

    async def get_power_details(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        meters: Iterable[Meter] | None = None,
    ) -> dict:
        """Return detailed power measurements including optional meters (async)."""
        return await self._send(
            _endpoints.power_details(site_id, start_time, end_time, meters)
        )

    async def get_energy_details(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        meters: Iterable[Meter] | None = None,
        time_unit: TimeUnit = "DAY",
    ) -> dict:
        """Return detailed energy breakdown (by meter/timeUnit) (async)."""
        return await self._send(
            _endpoints.energy_details(site_id, start_time, end_time, meters, time_unit)
        )

    async def get_current_power_flow(self, site_id: int) -> dict:
        """Return the current power flow (async)."""
        return await self._send(_endpoints.current_power_flow(site_id))

    async def get_storage_data(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        serials: Iterable[str] | None = None,
    ) -> dict:
        """Return storage (battery) measurements for the timeframe (async)."""
        return await self._send(
            _endpoints.storage_data(site_id, start_time, end_time, serials)
        )

    async def get_site_user_image(
        self,
        site_id: int,
        name: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        hash: int | None = None,  # noqa: A002 - mirrors the API's parameter name
    ) -> bytes:
        """Return the site image (async)."""
        return await self._send(
            _endpoints.site_user_image(site_id, name, max_width, max_height, hash)
        )

    async def get_environmental_benefits(
        self,
        site_id: int,
        system_units: SystemUnits | None = None,
    ) -> dict:
        """Return the environmental benefits (async)."""
        return await self._send(
            _endpoints.environmental_benefits(site_id, system_units)
        )

    async def get_site_installer_image(
        self,
        site_id: int,
        name: str | None = None,
    ) -> bytes:
        """Return the site installer image (async)."""
        return await self._send(_endpoints.site_installer_image(site_id, name))

    async def get_components_list(self, site_id: int) -> dict:
        """Return a list of inverters/SMIs in the specific site. (async)."""
        return await self._send(_endpoints.components_list(site_id))

    async def get_inventory(self, site_id: int) -> dict:
        """Return the inventory of SolarEdge equipment in the site (async).

        Including inverters/SMIs, batteries, meters, gateways and sensors.
        """
        return await self._send(_endpoints.inventory(site_id))

    async def get_inverter_technical_data(
        self,
        site_id: int,
        serial_number: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Return specific inverter data for a given timeframe (async)."""
        return await self._send(
            _endpoints.inverter_technical_data(
                site_id, serial_number, start_time, end_time
            )
        )

    async def get_equipment_change_log(
        self,
        site_id: int,
        serial_number: str,
    ) -> dict:
        """Returns a list of equipment component replacements ordered by date (async).

        This method is applicable to inverters, optimizers, batteries and gateways.
        """
        return await self._send(_endpoints.equipment_change_log(site_id, serial_number))

    async def get_account_list(
        self,
        page_size: int = 100,
        start_index: int = 0,
        search_text: str | None = None,
        sort_property: AccountSortProperty | None = None,
        sort_order: SortOrder = "ASC",
    ) -> dict:
        """Return the account and list of sub-accounts (async)."""
        return await self._send(
            _endpoints.account_list(
                page_size, start_index, search_text, sort_property, sort_order
            )
        )

    async def get_meters(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        time_unit: TimeUnit = "DAY",
        meters: Iterable[MeterReading] | None = None,
    ) -> dict:
        """Return a list of meters in the specific site. (async).

        Returns for each meter on site its lifetime energy reading,
        metadata and the device to which it's connected to.
        """
        return await self._send(
            _endpoints.meters(site_id, start_time, end_time, time_unit, meters)
        )

    async def get_sensor_list(self, site_id: int) -> dict:
        """Returns a list of all the sensors in the site, and the device to which they are connected.  (async)."""  # noqa: E501
        return await self._send(_endpoints.sensor_list(site_id))

    async def get_sensor_data(
        self,
        site_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Returns the data of all the sensors in the site, by the gateway they are connected to. (async)."""  # noqa: E501
        return await self._send(_endpoints.sensor_data(site_id, start_date, end_date))

    async def get_current_api_version(self) -> dict:
        """Returns the current API version. (async)."""
        return await self._send(_endpoints.current_api_version())

    async def get_supported_api_versions(self) -> dict:
        """Returns a list of supported API versions. (async)."""
        return await self._send(_endpoints.supported_api_versions())


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

    def close(self) -> None:
        """Close the internal httpx.Client if owned by this instance."""
        if self._external_client:
            raise ValueError("Will not close externally provided httpx.Client.")
        self.client.close()

    def _send(self, request: Request) -> Any:
        """Send a prepared request using the blocking client."""
        url, params = self._prepare(request)
        response = self.client.request(
            method=request.method,
            url=url,
            params=params,
        )
        return self._parse_response(response, request.raw)

    def get_site_list(
        self,
        size: int = 100,
        start_index: int = 0,
        search_text: str | None = None,
        sort_property: SiteSortProperty | None = None,
        sort_order: SortOrder = "ASC",
        status: list[SiteStatus] | Literal["All"] | None = None,
    ) -> dict:
        """Return a paginated list of sites for the account (sync).

        Args:
            size: Number of sites to return per page (max 100)
            start_index: Starting index for pagination
            search_text: Text to search for across multiple fields. The API will
                search in: Name, Notes, Email, Country, State, City, Zip, Full address
            sort_property: Property to sort by
            sort_order: Sort order ("ASC" or "DESC")
            status: Site status filter (["Active", "Pending"] by default)
        """
        return self._send(
            _endpoints.site_list(
                size, start_index, search_text, sort_property, sort_order, status
            )
        )

    def get_site_details(self, site_id: int) -> dict:
        """Get site details (sync).

        Returns parsed JSON from `/site/{siteId}/details`.
        """
        return self._send(_endpoints.site_details(site_id))

    def get_site_data(self, site_ids: list[int]) -> dict:
        """Return the site's energy data period (start/end) (sync)."""
        return self._send(_endpoints.site_data(site_ids))

    def get_energy(
        self,
        site_ids: list[int],
        start_date: datetime,
        end_date: datetime,
        time_unit: TimeUnit = "DAY",
    ) -> dict:
        """Get aggregated energy for a site between two dates (sync).

        this endpoint returns the same energy measurements
        that appear in the Site Dashboard.
        """
        return self._send(_endpoints.energy(site_ids, start_date, end_date, time_unit))

    def get_time_frame_energy(
        self,
        site_ids: list[int],
        start_date: datetime,
        end_date: datetime,
        time_unit: TimeUnit = "DAY",
    ) -> dict:
        """Get time-frame energy (sync).

        This endpoint only returns on-grid energy for the requested period.
        In sites with storage/backup, this may mean that results can differ from what appears in the Site Dashboard.
        Use the regular Site Energy API to obtain results that match the Site Dashboard calculation.
        """  # noqa: E501
        return self._send(
            _endpoints.time_frame_energy(site_ids, start_date, end_date, time_unit)
        )

    def get_power(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Return power measurements (15-minute resolution) for a timeframe (sync)."""
        return self._send(_endpoints.power(site_id, start_time, end_time))

    def get_overview(self, site_ids: list[int]) -> dict:
        """Return a site overview (sync)."""
        return self._send(_endpoints.overview(site_ids))

    def get_power_details(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        meters: Iterable[Meter] | None = None,
    ) -> dict:
        """Return detailed power measurements including optional meters (sync)."""
        return self._send(
            _endpoints.power_details(site_id, start_time, end_time, meters)
        )

    def get_energy_details(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        meters: Iterable[Meter] | None = None,
        time_unit: TimeUnit = "DAY",
    ) -> dict:
        """Return detailed energy breakdown (by meter/timeUnit) (sync)."""
        return self._send(
            _endpoints.energy_details(site_id, start_time, end_time, meters, time_unit)
        )

    def get_current_power_flow(self, site_id: int) -> dict:
        """Return the current power flow (sync)."""
        return self._send(_endpoints.current_power_flow(site_id))

    def get_storage_data(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        serials: Iterable[str] | None = None,
    ) -> dict:
        """Return storage (battery) measurements for the timeframe (sync)."""
        return self._send(
            _endpoints.storage_data(site_id, start_time, end_time, serials)
        )

    def get_site_user_image(
        self,
        site_id: int,
        name: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        hash: int | None = None,  # noqa: A002 - mirrors the API's parameter name
    ) -> bytes:
        """Return the site image (sync)."""
        return self._send(
            _endpoints.site_user_image(site_id, name, max_width, max_height, hash)
        )

    def get_environmental_benefits(
        self,
        site_id: int,
        system_units: SystemUnits | None = None,
    ) -> dict:
        """Return the environmental benefits (sync)."""
        return self._send(_endpoints.environmental_benefits(site_id, system_units))

    def get_site_installer_image(
        self,
        site_id: int,
        name: str | None = None,
    ) -> bytes:
        """Return the site installer image (sync)."""
        return self._send(_endpoints.site_installer_image(site_id, name))

    def get_components_list(self, site_id: int) -> dict:
        """Return a list of inverters/SMIs in the specific site. (sync)."""
        return self._send(_endpoints.components_list(site_id))

    def get_inventory(self, site_id: int) -> dict:
        """Return the inventory of SolarEdge equipment in the site (sync).

        Including inverters/SMIs, batteries, meters, gateways and sensors.
        """
        return self._send(_endpoints.inventory(site_id))

    def get_inverter_technical_data(
        self,
        site_id: int,
        serial_number: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Return specific inverter data for a given timeframe (sync)."""
        return self._send(
            _endpoints.inverter_technical_data(
                site_id, serial_number, start_time, end_time
            )
        )

    def get_equipment_change_log(
        self,
        site_id: int,
        serial_number: str,
    ) -> dict:
        """Returns a list of equipment component replacements ordered by date (sync).

        This method is applicable to inverters, optimizers, batteries and gateways.
        """
        return self._send(_endpoints.equipment_change_log(site_id, serial_number))

    def get_account_list(
        self,
        page_size: int = 100,
        start_index: int = 0,
        search_text: str | None = None,
        sort_property: AccountSortProperty | None = None,
        sort_order: SortOrder = "ASC",
    ) -> dict:
        """Return the account and list of sub-accounts (sync)."""
        return self._send(
            _endpoints.account_list(
                page_size, start_index, search_text, sort_property, sort_order
            )
        )

    def get_meters(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        time_unit: TimeUnit = "DAY",
        meters: Iterable[MeterReading] | None = None,
    ) -> dict:
        """Return a list of meters in the specific site. (sync).

        Returns for each meter on site its lifetime energy reading,
        metadata and the device to which it's connected to.
        """
        return self._send(
            _endpoints.meters(site_id, start_time, end_time, time_unit, meters)
        )

    def get_sensor_list(self, site_id: int) -> dict:
        """Returns a list of all the sensors in the site, and the device to which they are connected.  (sync)."""  # noqa: E501
        return self._send(_endpoints.sensor_list(site_id))

    def get_sensor_data(
        self,
        site_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Returns the data of all the sensors in the site, by the gateway they are connected to. (sync)."""  # noqa: E501
        return self._send(_endpoints.sensor_data(site_id, start_date, end_date))

    def get_current_api_version(self) -> dict:
        """Returns the current API version. (sync)."""
        return self._send(_endpoints.current_api_version())

    def get_supported_api_versions(self) -> dict:
        """Returns a list of supported API versions. (sync)."""
        return self._send(_endpoints.supported_api_versions())
