"""Library to interact with SolarEdge's monitoring API."""

from __future__ import annotations

import asyncio
from abc import ABC
from typing import Any, Literal
from datetime import datetime
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

    def _validate_timeframe(
        self,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR",
            "HOUR",
            "DAY",
            "_ONE_WEEK_MAX",
            "WEEK",
            "MONTH",
            "YEAR",
        ],
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """Validate the time frame for API requests.

        throws an error or returns None.
        """
        day_delta = (end_date - start_date).days

        if day_delta < 0:
            raise ValueError("End date must be after start date.")

        if time_unit == "_ONE_WEEK_MAX":
            if day_delta > 7:
                raise ValueError(("The maximum date range is 1 week (7 days).",))

        if time_unit in ("QUARTER_OF_AN_HOUR", "HOUR"):
            if day_delta > 31:
                raise ValueError(
                    (
                        f"For time_unit {time_unit}, ",
                        "the maximum date range is 1 month (31 days).",
                    )
                )
        if time_unit == "DAY":
            if day_delta > 365:
                raise ValueError(
                    (
                        f"For time_unit {time_unit}, ",
                        "the maximum date range is 1 year (365 days).",
                    )
                )


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

    async def get_site_list(
        self,
        size: int = 100,
        start_index: int = 0,
        search_text: str | None = None,
        sort_property: Literal[
            "Name",
            "Country",
            "State",
            "City",
            "Address",
            "Zip",
            "Status",
            "PeakPower",
            "InstallationDate",
            "Amount",
            "MaxSeverity",
            "CreationTime",
        ]
        | None = None,
        sort_order: Literal["ASC", "DESC"] = "ASC",
        status: list[Literal["Active", "Pending", "Disabled"]] | Literal["All"] = [
            "Active",
            "Pending",
        ],
    ) -> dict:
        """Return a paginated list of sites for the account (async).

        Args:
            size: Number of sites to return per page (max 100)
            start_index: Starting index for pagination
            search_text: Text to search for across multiple fields. The API will
                search in: Name, Notes, Email, Country, State, City, Zip, Full address
            sort_property: Property to sort by
            sort_order: Sort order ("ASC" or "DESC")
            status: Site status filter ("Active,Pending" by default)
        """
        path = "sites/list"
        params = {
            "size": size,
            "startIndex": start_index,
            "sortOrder": sort_order,
            "status": status if status == "All" else ",".join(status),
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

    async def get_site_details(self, site_id: int) -> dict:
        """Get site details (async)."""
        path = f"site/{site_id}/details"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_site_data(self, site_ids: list[int]) -> dict:
        """Return the site's energy data period (start/end) (async)."""
        if len(site_ids) > 100:
            raise ValueError("Cannot request data for more than 100 sites at once.")
        path = f"site/{','.join(map(str, site_ids))}/dataPeriod"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_energy(
        self,
        site_ids: list[int],
        start_date: datetime,
        end_date: datetime,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"
        ] = "DAY",
    ) -> dict:
        """Get aggregated energy for a site between two dates (async).

        this endpoint returns the same energy measurements
        that appear in the Site Dashboard.
        """
        self._validate_timeframe(time_unit, start_date, end_date)

        path = f"site/{','.join(map(str, site_ids))}/energy"
        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "timeUnit": time_unit,
        }
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_time_frame_energy(
        self,
        site_ids: list[int],
        start_date: datetime,
        end_date: datetime,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"
        ] = "DAY",
    ) -> dict:
        """Get time-frame energy (async).

        This endpoint only returns on-grid energy for the requested period.
        In sites with storage/backup, this may mean that results can differ from what appears in the Site Dashboard.
        Use the regular Site Energy API to obtain results that match the Site Dashboard calculation.
        """  # noqa: E501
        self._validate_timeframe(time_unit, start_date, end_date)

        path = f"site/{','.join(map(str, site_ids))}/timeFrameEnergy"
        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
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
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Return power measurements (15-minute resolution) for a timeframe (async)."""
        self._validate_timeframe("QUARTER_OF_AN_HOUR", start_time, end_time)

        path = f"site/{site_id}/power"
        params = {
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_overview(self, site_ids: list[int]) -> dict:
        """Return a site overview (async)."""
        path = f"site/{','.join(map(str, site_ids))}/overview"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_power_details(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        meters: Iterable[
            Literal[
                "Production",
                "Consumption",
                "SelfConsumption",
                "FeedIn",
                "Purchased",
            ]
        ]
        | None = None,
    ) -> dict:
        """Return detailed power measurements including optional meters (async)."""
        self._validate_timeframe("QUARTER_OF_AN_HOUR", start_time, end_time)

        path = f"site/{site_id}/powerDetails"
        params = {
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
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
        start_time: datetime,
        end_time: datetime,
        meters: Iterable[
            Literal[
                "Production",
                "Consumption",
                "SelfConsumption",
                "FeedIn",
                "Purchased",
            ]
        ]
        | None = None,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"
        ] = "DAY",
    ) -> dict:
        """Return detailed energy breakdown (by meter/timeUnit) (async)."""
        self._validate_timeframe(time_unit, start_time, end_time)

        path = f"site/{site_id}/energyDetails"
        params = {
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
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
        start_time: datetime,
        end_time: datetime,
        serials: Iterable[str] | None = None,
    ) -> dict:
        """Return storage (battery) measurements for the timeframe (async)."""
        self._validate_timeframe("_ONE_WEEK_MAX", start_time, end_time)

        path = f"site/{site_id}/storageData"
        params = {
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if serials:
            params["serials"] = ",".join(serials)
        return await self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    async def get_site_user_image(
        self,
        site_id: int,
        name: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        hash: int | None = None,
    ) -> bytes:
        """Return the site image (async)."""
        if name is None:
            path = f"site/{site_id}/image"
        else:
            path = f"site/{site_id}/image/{name}"
        return await self._make_request(
            method="GET",
            path=path,
            params={
                "maxWidth": max_width,
                "maxHeight": max_height,
                "hash": hash,
            },
        )

    async def get_environmental_benefits(
        self,
        site_id: int,
        system_units: Literal["Metrics", "Imperial"] | None = None,
    ) -> dict:
        """Return the environmental benefits (async)."""
        path = f"site/{site_id}/envBenefits"
        return await self._make_request(
            method="GET",
            path=path,
            params={
                "systemUnits": system_units,
            },
        )

    async def get_site_installer_image(
        self,
        site_id: int,
        name: str | None = None,
    ) -> bytes:
        """Return the site installer image (async)."""
        if name is None:
            path = f"site/{site_id}/installerImage"
        else:
            path = f"site/{site_id}/installerImage/{name}"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_components_list(self, site_id: int) -> dict:
        """Return a list of inverters/SMIs in the specific site. (async)."""
        path = f"equipment/{site_id}/list"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_inventory(self, site_id: int) -> dict:
        """Return the inventory of SolarEdge equipment in the site (async).

        Including inverters/SMIs, batteries, meters, gateways and sensors.
        """
        path = f"site/{site_id}/inventory"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_inverter_technical_data(
        self,
        site_id: int,
        serial_number: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Return specific inverter data for a given timeframe (async)."""
        self._validate_timeframe("_ONE_WEEK_MAX", start_time, end_time)
        path = f"site/{site_id}/inverter/{serial_number}/data"
        return await self._make_request(
            method="GET",
            path=path,
            params={
                "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )

    async def get_equipment_change_log(
        self,
        site_id: int,
        serial_number: str,
    ) -> dict:
        """Returns a list of equipment component replacements ordered by date (async).

        This method is applicable to inverters, optimizers, batteries and gateways.
        """
        path = f"site/{site_id}/{serial_number}/changeLog"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_account_list(
        self,
        page_size: int = 100,
        start_index: int = 0,
        search_text: str | None = None,
        sort_property: Literal[
            "Name",
            "country",
            "city",
            "address",
            "zip",
            "fax",
            "phone",
            "notes",
        ]
        | None = None,
        sort_order: Literal["ASC", "DESC"] = "ASC",
    ) -> dict:
        """Return the account and list of sub-accounts (async)."""
        path = "accounts/list"
        return await self._make_request(
            method="GET",
            path=path,
            params={
                "pageSize": min(page_size, 100),
                "startIndex": start_index,
                "searchText": search_text,
                "sortProperty": sort_property,
                "sortOrder": sort_order,
            },
        )

    async def get_meters(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"
        ] = "DAY",
        meters: Iterable[
            Literal[
                "Production",
                "Consumption",
                "FeedIn",
                "Purchased",
            ]
        ]
        | None = None,
    ) -> dict:
        """Return a list of meters in the specific site. (async).

        Returns for each meter on site its lifetime energy reading,
        metadata and the device to which it's connected to.
        """
        self._validate_timeframe(time_unit, start_time, end_time)
        path = f"site/{site_id}/meters"
        return await self._make_request(
            method="GET",
            path=path,
            params={
                "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeUnit": time_unit,
                "meters": ",".join(meters) if meters else None,
            },
        )

    async def get_sensor_list(self, site_id: int) -> dict:
        """Returns a list of all the sensors in the site, and the device to which they are connected.  (async)."""  # noqa: E501
        path = f"equipment/{site_id}/sensors"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_sensor_data(
        self,
        site_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Returns the data of all the sensors in the site, by the gateway they are connected to. (async)."""  # noqa: E501
        self._validate_timeframe("_ONE_WEEK_MAX", start_date, end_date)
        path = f"equipment/{site_id}/sensors"
        return await self._make_request(
            method="GET",
            path=path,
            params={
                "startTime": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                "endTime": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )

    async def get_current_api_version(self) -> dict:
        """Returns the current API version. (async)."""
        path = "version/current"
        return await self._make_request(
            method="GET",
            path=path,
        )

    async def get_supported_api_versions(self) -> dict:
        """Returns a list of supported API versions. (async)."""
        path = "version/supported"
        return await self._make_request(
            method="GET",
            path=path,
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

    def close(self) -> None:
        """Close the internal httpx.Client if owned by this instance."""
        if self._external_client:
            raise ValueError("Will not close externally provided httpx.Client.")
        self.client.close()

    def _make_request(self, method: str, path: str, params: dict | None = None) -> Any:
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

    def get_site_list(
        self,
        size: int = 100,
        start_index: int = 0,
        search_text: str | None = None,
        sort_property: Literal[
            "Name",
            "Country",
            "State",
            "City",
            "Address",
            "Zip",
            "Status",
            "PeakPower",
            "InstallationDate",
            "Amount",
            "MaxSeverity",
            "CreationTime",
        ]
        | None = None,
        sort_order: Literal["ASC", "DESC"] = "ASC",
        status: list[Literal["Active", "Pending", "Disabled"]] | Literal["All"] = [
            "Active",
            "Pending",
        ],
    ) -> dict:
        """Return a paginated list of sites for the account (sync).

        Args:
            size: Number of sites to return per page (max 100)
            start_index: Starting index for pagination
            search_text: Text to search for across multiple fields. The API will
                search in: Name, Notes, Email, Country, State, City, Zip, Full address
            sort_property: Property to sort by
            sort_order: Sort order ("ASC" or "DESC")
            status: Site status filter ("Active,Pending" by default)
        """
        path = "sites/list"
        params = {
            "size": size,
            "startIndex": start_index,
            "sortOrder": sort_order,
            "status": status if status == "All" else ",".join(status),
        }
        if search_text:
            params["searchText"] = search_text
        if sort_property:
            params["sortProperty"] = sort_property
        return self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    def get_site_details(self, site_id: int) -> dict:
        """Get site details (sync).

        Returns parsed JSON from `/site/{siteId}/details`.
        """
        path = f"site/{site_id}/details"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_site_data(self, site_ids: list[int]) -> dict:
        """Return the site's energy data period (start/end) (sync)."""
        if len(site_ids) > 100:
            raise ValueError("Cannot request data for more than 100 sites at once.")
        path = f"site/{','.join(map(str, site_ids))}/dataPeriod"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_energy(
        self,
        site_ids: list[int],
        start_date: datetime,
        end_date: datetime,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"
        ] = "DAY",
    ) -> dict:
        """Get aggregated energy for a site between two dates (sync).

        this endpoint returns the same energy measurements
        that appear in the Site Dashboard.
        """
        self._validate_timeframe(time_unit, start_date, end_date)

        path = f"site/{','.join(map(str, site_ids))}/energy"
        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "timeUnit": time_unit,
        }
        return self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    def get_time_frame_energy(
        self,
        site_ids: list[int],
        start_date: datetime,
        end_date: datetime,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"
        ] = "DAY",
    ) -> dict:
        """Get time-frame energy (sync).

        This endpoint only returns on-grid energy for the requested period.
        In sites with storage/backup, this may mean that results can differ from what appears in the Site Dashboard.
        Use the regular Site Energy API to obtain results that match the Site Dashboard calculation.
        """  # noqa: E501
        self._validate_timeframe(time_unit, start_date, end_date)

        path = f"site/{','.join(map(str, site_ids))}/timeFrameEnergy"
        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "timeUnit": time_unit,
        }
        return self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    def get_power(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Return power measurements (15-minute resolution) for a timeframe (sync)."""
        self._validate_timeframe("QUARTER_OF_AN_HOUR", start_time, end_time)

        path = f"site/{site_id}/power"
        params = {
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        return self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    def get_overview(self, site_ids: list[int]) -> dict:
        """Return a site overview (sync)."""
        path = f"site/{','.join(map(str, site_ids))}/overview"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_power_details(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        meters: Iterable[
            Literal[
                "Production",
                "Consumption",
                "SelfConsumption",
                "FeedIn",
                "Purchased",
            ]
        ]
        | None = None,
    ) -> dict:
        """Return detailed power measurements including optional meters (sync)."""
        self._validate_timeframe("QUARTER_OF_AN_HOUR", start_time, end_time)

        path = f"site/{site_id}/powerDetails"
        params = {
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if meters:
            params["meters"] = ",".join(meters)
        return self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    def get_energy_details(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        meters: Iterable[
            Literal[
                "Production",
                "Consumption",
                "SelfConsumption",
                "FeedIn",
                "Purchased",
            ]
        ]
        | None = None,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"
        ] = "DAY",
    ) -> dict:
        """Return detailed energy breakdown (by meter/timeUnit) (sync)."""
        self._validate_timeframe(time_unit, start_time, end_time)

        path = f"site/{site_id}/energyDetails"
        params = {
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeUnit": time_unit,
        }
        if meters:
            params["meters"] = ",".join(meters)
        return self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    def get_current_power_flow(self, site_id: int) -> dict:
        """Return the current power flow (sync)."""
        path = f"site/{site_id}/currentPowerFlow"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_storage_data(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        serials: Iterable[str] | None = None,
    ) -> dict:
        """Return storage (battery) measurements for the timeframe (sync)."""
        self._validate_timeframe("_ONE_WEEK_MAX", start_time, end_time)

        path = f"site/{site_id}/storageData"
        params = {
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if serials:
            params["serials"] = ",".join(serials)
        return self._make_request(
            method="GET",
            path=path,
            params=params,
        )

    def get_site_user_image(
        self,
        site_id: int,
        name: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        hash: int | None = None,
    ) -> bytes:
        """Return the site image (async)."""
        if name is None:
            path = f"site/{site_id}/image"
        else:
            path = f"site/{site_id}/image/{name}"
        return self._make_request(
            method="GET",
            path=path,
            params={
                "maxWidth": max_width,
                "maxHeight": max_height,
                "hash": hash,
            },
        )

    def get_environmental_benefits(
        self,
        site_id: int,
        system_units: Literal["Metrics", "Imperial"] | None = None,
    ) -> dict:
        """Return the environmental benefits (async)."""
        path = f"site/{site_id}/envBenefits"
        return self._make_request(
            method="GET",
            path=path,
            params={
                "systemUnits": system_units,
            },
        )

    def get_site_installer_image(
        self,
        site_id: int,
        name: str | None = None,
    ) -> bytes:
        """Return the site installer image (sync)."""
        if name is None:
            path = f"site/{site_id}/installerImage"
        else:
            path = f"site/{site_id}/installerImage/{name}"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_components_list(self, site_id: int) -> dict:
        """Return a list of inverters/SMIs in the specific site. (sync)."""
        path = f"equipment/{site_id}/list"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_inventory(self, site_id: int) -> dict:
        """Return the inventory of SolarEdge equipment in the site (sync).

        Including inverters/SMIs, batteries, meters, gateways and sensors.
        """
        path = f"site/{site_id}/inventory"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_inverter_technical_data(
        self,
        site_id: int,
        serial_number: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Return specific inverter data for a given timeframe (sync)."""
        self._validate_timeframe("_ONE_WEEK_MAX", start_time, end_time)
        path = f"site/{site_id}/inverter/{serial_number}/data"
        return self._make_request(
            method="GET",
            path=path,
            params={
                "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )

    def get_equipment_change_log(
        self,
        site_id: int,
        serial_number: str,
    ) -> dict:
        """Returns a list of equipment component replacements ordered by date (sync).

        This method is applicable to inverters, optimizers, batteries and gateways.
        """
        path = f"site/{site_id}/{serial_number}/changeLog"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_account_list(
        self,
        page_size: int = 100,
        start_index: int = 0,
        search_text: str | None = None,
        sort_property: Literal[
            "Name",
            "country",
            "city",
            "address",
            "zip",
            "fax",
            "phone",
            "notes",
        ]
        | None = None,
        sort_order: Literal["ASC", "DESC"] = "ASC",
    ) -> dict:
        """Return the account and list of sub-accounts (sync)."""
        path = "accounts/list"
        return self._make_request(
            method="GET",
            path=path,
            params={
                "pageSize": min(page_size, 100),
                "startIndex": start_index,
                "searchText": search_text,
                "sortProperty": sort_property,
                "sortOrder": sort_order,
            },
        )

    def get_meters(
        self,
        site_id: int,
        start_time: datetime,
        end_time: datetime,
        time_unit: Literal[
            "QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"
        ] = "DAY",
        meters: Iterable[
            Literal[
                "Production",
                "Consumption",
                "FeedIn",
                "Purchased",
            ]
        ]
        | None = None,
    ) -> dict:
        """Return a list of meters in the specific site. (sync).

        Returns for each meter on site its lifetime energy reading,
        metadata and the device to which it's connected to.
        """
        self._validate_timeframe(time_unit, start_time, end_time)
        path = f"site/{site_id}/meters"
        return self._make_request(
            method="GET",
            path=path,
            params={
                "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeUnit": time_unit,
                "meters": ",".join(meters) if meters else None,
            },
        )

    def get_sensor_list(self, site_id: int) -> dict:
        """Returns a list of all the sensors in the site, and the device to which they are connected.  (sync)."""  # noqa: E501
        path = f"equipment/{site_id}/sensors"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_sensor_data(
        self,
        site_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Returns the data of all the sensors in the site, by the gateway they are connected to. (sync)."""  # noqa: E501
        self._validate_timeframe("_ONE_WEEK_MAX", start_date, end_date)
        path = f"equipment/{site_id}/sensors"
        return self._make_request(
            method="GET",
            path=path,
            params={
                "startTime": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                "endTime": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )

    def get_current_api_version(self) -> dict:
        """Returns the current API version. (sync)."""
        path = "version/current"
        return self._make_request(
            method="GET",
            path=path,
        )

    def get_supported_api_versions(self) -> dict:
        """Returns a list of supported API versions. (sync)."""
        path = "version/supported"
        return self._make_request(
            method="GET",
            path=path,
        )
