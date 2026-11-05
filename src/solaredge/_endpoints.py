"""Request builders for every SolarEdge Monitoring API V2 operation.

Every builder here is a pure function: it validates its arguments, assembles
the request path and query parameters, and returns a :class:`Request`. No I/O
happens in this module, so the synchronous and asynchronous clients share a
single definition of each operation.

Paths are relative to ``https://monitoringapi.solaredge.com/v2`` and follow
SolarEdge's Basic Monitoring API 2.1.0 and Advanced Monitoring API 2.0.1
specifications.
"""

from __future__ import annotations

import re
from typing import Any, Literal, NamedTuple
from datetime import datetime, timezone
from collections.abc import Mapping, Iterable

from .exceptions import SolarEdgeValidationError

# Shared vocabulary for the API's enumerated values, reused in the clients'
# public signatures. These are type hints only: values are passed through
# unchanged, so a value SolarEdge adds later still works.
Resolution = Literal["QUARTER_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR", "TOTAL"]
PowerResolution = Literal["QUARTER_HOUR", "HOUR"]
EnergyUnit = Literal["WH", "KWH", "MWH"]
PowerUnit = Literal["W", "KW", "MW"]
PercentageUnit = Literal["PERCENTAGE", "PERCENTAGE_100"]
SystemUnits = Literal["METRIC", "IMPERIAL"]
DeviceType = Literal[
    "INVERTER",
    "BATTERY",
    "BATTERY_MODULE",
    "OPTIMIZER",
    "METER",
    "EV_CHARGER",
    "BUI",
    "GATEWAY",
]
MeterType = Literal[
    "PRODUCTION", "CONSUMPTION", "FEEDIN", "PURCHASED", "EXPORT", "IMPORT"
]
DeviceFamily = Literal["inverters", "meters", "storage"]

Params = list[tuple[str, Any]]

_SERIAL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class Request(NamedTuple):
    """A fully-described API request, independent of how it is sent.

    ``params`` is a list of pairs rather than a dict so a key can repeat, as
    ``/devices`` expects for ``types``.
    """

    method: str
    path: str
    params: Params | None = None


# --- argument helpers --------------------------------------------------------


def format_datetime(value: datetime, name: str = "datetime") -> str:
    """Render a timezone-aware datetime as the UTC instant V2 expects.

    V2 rejects timestamps without an offset, so a naive datetime is refused
    locally rather than guessed at. Converting to UTC with a ``Z`` suffix
    matches SolarEdge's documented examples and avoids sending a ``+``.

    Raises:
        SolarEdgeValidationError: If ``value`` has no timezone.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise SolarEdgeValidationError(
            f"{name} must be timezone-aware, e.g. "
            "datetime(2026, 1, 1, tzinfo=timezone.utc); got a naive datetime."
        )
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _window(start: datetime | None, end: datetime | None) -> Params:
    """Render an optional time window as ``from``/``to`` params.

    Either bound may be omitted; the API then defaults to midnight today and
    now, in the site's local time.
    """
    params: Params = []
    if start is not None:
        params.append(("from", format_datetime(start, "start")))
    if end is not None:
        params.append(("to", format_datetime(end, "end")))
    if start is not None and end is not None and end < start:
        raise SolarEdgeValidationError("end must not be before start.")
    return params


def _required_window(start: datetime, end: datetime) -> Params:
    """Render a mandatory time window, as the lifetime-energy endpoints need."""
    if start is None or end is None:
        raise SolarEdgeValidationError("start and end are both required.")
    return _window(start, end)


def _site(site_id: int | str) -> str:
    """Render a site ID, refusing anything that is not plain digits.

    Validating here keeps a malformed ID from producing a different path,
    e.g. ``"1/../2"``.
    """
    sid = str(site_id)
    if isinstance(site_id, bool) or not (sid.isascii() and sid.isdecimal()):
        raise SolarEdgeValidationError(
            f"site_id must be a positive integer; got {site_id!r}."
        )
    return sid


def _serial(serial: str) -> str:
    """Validate one device serial number for use as a path segment."""
    if not isinstance(serial, str) or not _SERIAL.fullmatch(serial):
        raise SolarEdgeValidationError(
            "serial numbers may contain only letters, digits, '.', '_' and '-'; "
            f"got {serial!r}."
        )
    return serial


def _serials(serials: Iterable[str]) -> str:
    """Render serial numbers as the comma-separated path segment V2 expects."""
    if isinstance(serials, str):
        serials = [serials]
    rendered = [_serial(s) for s in serials]
    if not rendered:
        raise SolarEdgeValidationError("serial_numbers must not be empty.")
    return ",".join(rendered)


def _bounded(name: str, value: int | None, low: int, high: int) -> int | None:
    """Check an optional integer against the API's documented bounds."""
    if value is not None and not low <= value <= high:
        raise SolarEdgeValidationError(
            f"{name} must be between {low} and {high}; got {value}."
        )
    return value


def _bool(value: bool | None) -> str | None:
    return None if value is None else str(bool(value)).lower()


def _path(*parts: str) -> str:
    return "/".join(parts)


def _get(path: str, params: Params | None = None) -> Request:
    return Request("GET", path, params or None)


# --- sites -------------------------------------------------------------------


def sites(
    page: int | None,
    sites_in_page: int | None,
    name: str | None,
    group: str | None,
    state: str | None,
    city: str | None,
) -> Request:
    """``GET /sites``: the sites this API key can access."""
    return _get(
        "sites",
        [
            ("page", _bounded("page", page, 1, 10_000_000)),
            ("sites-in-page", _bounded("sites_in_page", sites_in_page, 1, 1000)),
            ("name", name),
            ("group", group),
            ("state", state),
            ("city", city),
        ],
    )


def site_details(site_id: int | str) -> Request:
    """``GET /sites/{id}``."""
    return _get(_path("sites", _site(site_id)))


def overview(
    site_id: int | str, start: datetime | None, end: datetime | None
) -> Request:
    """``GET /sites/{id}/overview``."""
    return _get(_path("sites", _site(site_id), "overview"), _window(start, end))


def performance(
    site_id: int | str, start: datetime | None, end: datetime | None
) -> Request:
    """``GET /sites/{id}/overview/performance``."""
    return _get(
        _path("sites", _site(site_id), "overview", "performance"), _window(start, end)
    )


def site_series(
    site_id: int | str,
    metric: str,
    start: datetime | None,
    end: datetime | None,
    resolution: str | None,
    unit: str | None = None,
) -> Request:
    """``GET /sites/{id}/{metric}`` for site-level time series.

    Covers ``power``, ``energy``, ``power/per-destination`` and
    ``energy/per-destination``.
    """
    return _get(
        _path("sites", _site(site_id), metric),
        [*_window(start, end), ("resolution", resolution), ("unit", unit)],
    )


def environmental_benefits(site_id: int | str, unit: SystemUnits | None) -> Request:
    """``GET /sites/{id}/environmental-benefits``."""
    return _get(
        _path("sites", _site(site_id), "environmental-benefits"), [("unit", unit)]
    )


def site_resource(site_id: int | str, resource: str) -> Request:
    """``GET /sites/{id}/{resource}`` for endpoints without parameters.

    Covers ``lifetime-energy``, ``external-production-energy``,
    ``power-flow``, ``weather-guard`` and ``backup-reserve``.
    """
    return _get(_path("sites", _site(site_id), resource))


def start_live_power_flow(site_id: int | str) -> Request:
    """``POST /sites/{id}/power-flow``: start a 1-minute live session."""
    return Request("POST", _path("sites", _site(site_id), "power-flow"))


# --- alerts ------------------------------------------------------------------


def fleet_alerts(
    page: int | None,
    alerts_in_page: int | None,
    group: str | None,
    alert_type: str | None,
    state: str | None,
    city: str | None,
    only_open: bool | None,
) -> Request:
    """``GET /alerts``: alerts across every site the key can access."""
    return _get(
        "alerts",
        [
            ("page", _bounded("page", page, 1, 10_000_000)),
            ("alerts-in-page", _bounded("alerts_in_page", alerts_in_page, 1, 100)),
            ("group", group),
            ("type", alert_type),
            ("state", state),
            ("city", city),
            ("only-open", _bool(only_open)),
        ],
    )


def site_alerts(
    site_id: int | str,
    page: int | None,
    alerts_in_page: int | None,
    only_open: bool | None,
) -> Request:
    """``GET /sites/{id}/alerts``."""
    return _get(
        _path("sites", _site(site_id), "alerts"),
        [
            ("page", _bounded("page", page, 1, 10_000_000)),
            ("alerts-in-page", _bounded("alerts_in_page", alerts_in_page, 1, 100)),
            ("only-open", _bool(only_open)),
        ],
    )


# --- inventory ---------------------------------------------------------------


def devices(site_id: int | str, types: Iterable[DeviceType] | None) -> Request:
    """``GET /sites/{id}/devices``, with ``types`` sent as a repeated key."""
    if isinstance(types, str):
        types = [types]
    params = [("types", t) for t in types] if types else None
    return _get(_path("sites", _site(site_id), "devices"), params)


def device(site_id: int | str, serial_number: str) -> Request:
    """``GET /sites/{id}/devices/{serialNumber}``."""
    return _get(_path("sites", _site(site_id), "devices", _serial(serial_number)))


# --- per-family telemetry, status and lifetime energy --------------------------


def family_series(
    site_id: int | str,
    family: DeviceFamily,
    kind: Literal["telemetry", "status"],
    serial_numbers: Iterable[str] | None,
    start: datetime | None,
    end: datetime | None,
    resolution: str | None,
) -> Request:
    """``GET /sites/{id}/{family}[/{serialNumbers}]/{kind}``.

    Without serial numbers the site-wide variant is used, covering every
    active device of that family.
    """
    parts = ["sites", _site(site_id), family]
    if serial_numbers is not None:
        parts.append(_serials(serial_numbers))
    parts.append(kind)
    return _get(_path(*parts), [*_window(start, end), ("resolution", resolution)])


def family_lifetime_energy(
    site_id: int | str,
    family: DeviceFamily,
    serial_numbers: Iterable[str] | None,
    start: datetime,
    end: datetime,
    meters: Iterable[MeterType] | None = None,
) -> Request:
    """``GET /sites/{id}/{family}[/{serialNumbers}]/lifetime-energy``."""
    parts = ["sites", _site(site_id), family]
    if serial_numbers is not None:
        parts.append(_serials(serial_numbers))
    parts.append("lifetime-energy")
    if isinstance(meters, str):
        meters = [meters]
    return _get(
        _path(*parts),
        [
            *_required_window(start, end),
            ("meters", ",".join(meters) if meters else None),
        ],
    )


# --- single-device measurements ----------------------------------------------


def device_measurement(
    site_id: int | str,
    family: DeviceFamily,
    serial_number: str,
    metric: str,
    start: datetime | None,
    end: datetime | None,
    resolution: str | None,
    unit: str | None = None,
) -> Request:
    """``GET /sites/{id}/{family}/{serialNumber}/{metric}``.

    Covers every per-inverter, per-meter and per-battery measurement series.
    """
    return _get(
        _path("sites", _site(site_id), family, _serial(serial_number), metric),
        [*_window(start, end), ("resolution", resolution), ("unit", unit)],
    )


# --- escape hatch ------------------------------------------------------------


def raw(path: str, params: Mapping[str, Any] | None) -> Request:
    """Build a GET for any V2 path, for operations SolarEdge adds later.

    Datetime values are rendered the same way as in the dedicated methods, and
    list or tuple values become a repeated key.
    """
    path = path.strip("/")
    if not path or ".." in path.split("/"):
        raise SolarEdgeValidationError(f"Invalid API path: {path!r}.")

    pairs: Params = []
    for key, value in (params or {}).items():
        values = value if isinstance(value, (list, tuple)) else [value]
        pairs.extend(
            (key, format_datetime(v, key) if isinstance(v, datetime) else v)
            for v in values
        )
    return _get(path, pairs)
