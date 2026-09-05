"""Endpoint definitions shared by the synchronous and asynchronous clients.

Every builder here is a pure function: it validates its arguments, assembles
the request path and query parameters, and returns a :class:`Request`. No I/O
happens in this module, so both clients share a single definition of each
endpoint and can be thin transport wrappers around it.
"""

from __future__ import annotations

from typing import Any, Literal, NamedTuple
from datetime import datetime, timedelta
from collections.abc import Iterable

from .exceptions import SolarEdgeValidationError

# Shared vocabulary for the API's enumerated values. Defined once here and
# reused in both clients' public signatures.
TimeUnit = Literal["QUARTER_OF_AN_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
SortOrder = Literal["ASC", "DESC"]
SiteStatus = Literal["Active", "Pending", "Disabled"]
SystemUnits = Literal["Metrics", "Imperial"]
Meter = Literal[
    "Production",
    "Consumption",
    "SelfConsumption",
    "FeedIn",
    "Purchased",
]
MeterReading = Literal["Production", "Consumption", "FeedIn", "Purchased"]
SiteSortProperty = Literal[
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
AccountSortProperty = Literal[
    "Name",
    "country",
    "city",
    "address",
    "zip",
    "fax",
    "phone",
    "notes",
]

# `_ONE_WEEK_MAX` is not an API time unit; it selects the one-week ceiling for
# endpoints that impose one without taking a timeUnit parameter.
ValidatedTimeUnit = Literal[
    "QUARTER_OF_AN_HOUR",
    "HOUR",
    "DAY",
    "_ONE_WEEK_MAX",
    "WEEK",
    "MONTH",
    "YEAR",
]

MAX_SITES_PER_REQUEST = 100
MAX_PAGE_SIZE = 100

_DATE_FORMAT = "%Y-%m-%d"
_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"


class Request(NamedTuple):
    """A fully-described API request, independent of how it is sent."""

    method: str
    path: str
    params: dict[str, Any] | None = None
    raw: bool = False


def validate_timeframe(
    time_unit: ValidatedTimeUnit,
    start_date: datetime,
    end_date: datetime,
) -> None:
    """Validate a requested time frame against the API's documented limits.

    Raises:
        ValueError: If the range is inverted or exceeds the limit for the unit.
    """
    delta = end_date - start_date

    if delta < timedelta(0):
        raise SolarEdgeValidationError("End date must be after start date.")

    if time_unit == "_ONE_WEEK_MAX":
        if delta > timedelta(days=7):
            raise SolarEdgeValidationError("The maximum date range is 1 week (7 days).")

    if time_unit in ("QUARTER_OF_AN_HOUR", "HOUR"):
        if delta > timedelta(days=31):
            raise SolarEdgeValidationError(
                f"For time_unit {time_unit}, "
                "the maximum date range is 1 month (31 days)."
            )
    if time_unit == "DAY":
        if delta > timedelta(days=365):
            raise SolarEdgeValidationError(
                f"For time_unit {time_unit}, "
                "the maximum date range is 1 year (365 days)."
            )


def _site_ids(site_ids: Iterable[int]) -> str:
    """Render site IDs as the API's comma-separated form, enforcing its limits.

    Raises:
        SolarEdgeValidationError: If the collection is empty or exceeds the
            documented 100-site maximum.
    """
    ids = list(site_ids)
    if not ids:
        raise SolarEdgeValidationError("At least one site ID is required.")
    if len(ids) > MAX_SITES_PER_REQUEST:
        raise SolarEdgeValidationError(
            f"Cannot request data for more than {MAX_SITES_PER_REQUEST} "
            f"sites at once; got {len(ids)}."
        )
    return ",".join(map(str, ids))


def site_list(
    size: int,
    start_index: int,
    search_text: str | None,
    sort_property: SiteSortProperty | None,
    sort_order: SortOrder,
    status: list[SiteStatus] | Literal["All"] | None,
) -> Request:
    """Build the request for a paginated list of sites."""
    if size > MAX_PAGE_SIZE:
        raise SolarEdgeValidationError(
            f"size cannot exceed {MAX_PAGE_SIZE}; got {size}."
        )
    if status is None:
        status = ["Active", "Pending"]

    params: dict[str, Any] = {
        "size": size,
        "startIndex": start_index,
        "sortOrder": sort_order,
        "status": status if status == "All" else ",".join(status),
    }
    if search_text:
        params["searchText"] = search_text
    if sort_property:
        params["sortProperty"] = sort_property
    return Request("GET", "sites/list", params)


def site_details(site_id: int) -> Request:
    """Build the request for a single site's details."""
    return Request("GET", f"site/{site_id}/details")


def site_data(site_ids: list[int]) -> Request:
    """Build the request for the sites' energy data period."""
    return Request("GET", f"site/{_site_ids(site_ids)}/dataPeriod")


def energy(
    site_ids: list[int],
    start_date: datetime,
    end_date: datetime,
    time_unit: TimeUnit,
) -> Request:
    """Build the request for aggregated site energy."""
    validate_timeframe(time_unit, start_date, end_date)
    return Request(
        "GET",
        f"site/{_site_ids(site_ids)}/energy",
        {
            "startDate": start_date.strftime(_DATE_FORMAT),
            "endDate": end_date.strftime(_DATE_FORMAT),
            "timeUnit": time_unit,
        },
    )


def time_frame_energy(
    site_ids: list[int],
    start_date: datetime,
    end_date: datetime,
    time_unit: TimeUnit,
) -> Request:
    """Build the request for on-grid energy over a time frame."""
    validate_timeframe(time_unit, start_date, end_date)
    return Request(
        "GET",
        f"site/{_site_ids(site_ids)}/timeFrameEnergy",
        {
            "startDate": start_date.strftime(_DATE_FORMAT),
            "endDate": end_date.strftime(_DATE_FORMAT),
            "timeUnit": time_unit,
        },
    )


def power(site_id: int, start_time: datetime, end_time: datetime) -> Request:
    """Build the request for 15-minute-resolution power measurements."""
    validate_timeframe("QUARTER_OF_AN_HOUR", start_time, end_time)
    return Request(
        "GET",
        f"site/{site_id}/power",
        {
            "startTime": start_time.strftime(_DATETIME_FORMAT),
            "endTime": end_time.strftime(_DATETIME_FORMAT),
        },
    )


def overview(site_ids: list[int]) -> Request:
    """Build the request for a site overview."""
    return Request("GET", f"site/{_site_ids(site_ids)}/overview")


def power_details(
    site_id: int,
    start_time: datetime,
    end_time: datetime,
    meters: Iterable[Meter] | None,
) -> Request:
    """Build the request for detailed power measurements."""
    validate_timeframe("QUARTER_OF_AN_HOUR", start_time, end_time)
    params: dict[str, Any] = {
        "startTime": start_time.strftime(_DATETIME_FORMAT),
        "endTime": end_time.strftime(_DATETIME_FORMAT),
    }
    if meters:
        params["meters"] = ",".join(meters)
    return Request("GET", f"site/{site_id}/powerDetails", params)


def energy_details(
    site_id: int,
    start_time: datetime,
    end_time: datetime,
    meters: Iterable[Meter] | None,
    time_unit: TimeUnit,
) -> Request:
    """Build the request for a detailed energy breakdown."""
    validate_timeframe(time_unit, start_time, end_time)
    params: dict[str, Any] = {
        "startTime": start_time.strftime(_DATETIME_FORMAT),
        "endTime": end_time.strftime(_DATETIME_FORMAT),
        "timeUnit": time_unit,
    }
    if meters:
        params["meters"] = ",".join(meters)
    return Request("GET", f"site/{site_id}/energyDetails", params)


def current_power_flow(site_id: int) -> Request:
    """Build the request for the site's current power flow."""
    return Request("GET", f"site/{site_id}/currentPowerFlow")


def storage_data(
    site_id: int,
    start_time: datetime,
    end_time: datetime,
    serials: Iterable[str] | None,
) -> Request:
    """Build the request for battery measurements."""
    validate_timeframe("_ONE_WEEK_MAX", start_time, end_time)
    params: dict[str, Any] = {
        "startTime": start_time.strftime(_DATETIME_FORMAT),
        "endTime": end_time.strftime(_DATETIME_FORMAT),
    }
    if serials:
        params["serials"] = ",".join(serials)
    return Request("GET", f"site/{site_id}/storageData", params)


def site_user_image(
    site_id: int,
    name: str | None,
    max_width: int | None,
    max_height: int | None,
    image_hash: int | None,
) -> Request:
    """Build the request for the site image, which returns raw bytes."""
    path = f"site/{site_id}/image" if name is None else f"site/{site_id}/image/{name}"
    return Request(
        "GET",
        path,
        {
            "maxWidth": max_width,
            "maxHeight": max_height,
            "hash": image_hash,
        },
        raw=True,
    )


def environmental_benefits(site_id: int, system_units: SystemUnits | None) -> Request:
    """Build the request for the site's environmental benefits."""
    return Request(
        "GET",
        f"site/{site_id}/envBenefits",
        {"systemUnits": system_units},
    )


def site_installer_image(site_id: int, name: str | None) -> Request:
    """Build the request for the installer image, which returns raw bytes."""
    path = (
        f"site/{site_id}/installerImage"
        if name is None
        else f"site/{site_id}/installerImage/{name}"
    )
    return Request("GET", path, raw=True)


def components_list(site_id: int) -> Request:
    """Build the request for the site's inverters and SMIs."""
    return Request("GET", f"equipment/{site_id}/list")


def inventory(site_id: int) -> Request:
    """Build the request for the site's equipment inventory."""
    return Request("GET", f"site/{site_id}/inventory")


def inverter_technical_data(
    site_id: int,
    serial_number: str,
    start_time: datetime,
    end_time: datetime,
) -> Request:
    """Build the request for a single inverter's technical data."""
    validate_timeframe("_ONE_WEEK_MAX", start_time, end_time)
    return Request(
        "GET",
        f"site/{site_id}/inverter/{serial_number}/data",
        {
            "startTime": start_time.strftime(_DATETIME_FORMAT),
            "endTime": end_time.strftime(_DATETIME_FORMAT),
        },
    )


def equipment_change_log(site_id: int, serial_number: str) -> Request:
    """Build the request for a component's replacement history."""
    return Request("GET", f"site/{site_id}/{serial_number}/changeLog")


def account_list(
    page_size: int,
    start_index: int,
    search_text: str | None,
    sort_property: AccountSortProperty | None,
    sort_order: SortOrder,
) -> Request:
    """Build the request for the account and its sub-accounts."""
    if page_size > MAX_PAGE_SIZE:
        raise SolarEdgeValidationError(
            f"page_size cannot exceed {MAX_PAGE_SIZE}; got {page_size}."
        )
    return Request(
        "GET",
        "accounts/list",
        {
            "pageSize": page_size,
            "startIndex": start_index,
            "searchText": search_text,
            "sortProperty": sort_property,
            "sortOrder": sort_order,
        },
    )


def meters(
    site_id: int,
    start_time: datetime,
    end_time: datetime,
    time_unit: TimeUnit,
    meters: Iterable[MeterReading] | None,
) -> Request:
    """Build the request for the site's meters and their readings."""
    validate_timeframe(time_unit, start_time, end_time)
    return Request(
        "GET",
        f"site/{site_id}/meters",
        {
            "startTime": start_time.strftime(_DATETIME_FORMAT),
            "endTime": end_time.strftime(_DATETIME_FORMAT),
            "timeUnit": time_unit,
            "meters": ",".join(meters) if meters else None,
        },
    )


def sensor_list(site_id: int) -> Request:
    """Build the request for the site's sensors."""
    return Request("GET", f"equipment/{site_id}/sensors")


def sensor_data(site_id: int, start_date: datetime, end_date: datetime) -> Request:
    """Build the request for sensor measurements."""
    validate_timeframe("_ONE_WEEK_MAX", start_date, end_date)
    return Request(
        "GET",
        f"equipment/{site_id}/sensors",
        {
            "startTime": start_date.strftime(_ISO_FORMAT),
            "endTime": end_date.strftime(_ISO_FORMAT),
        },
    )


def current_api_version() -> Request:
    """Build the request for the current API version."""
    return Request("GET", "version/current")


def supported_api_versions() -> Request:
    """Build the request for the list of supported API versions."""
    return Request("GET", "version/supported")
