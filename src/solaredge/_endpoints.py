"""Endpoint definitions shared by the synchronous and asynchronous clients.

Every builder here is a pure function: it validates its arguments, assembles
the request path and query parameters, and returns a :class:`Request`. No I/O
happens in this module, so both clients share a single definition of each
endpoint and can be thin transport wrappers around it.

Paths are relative to the V2 base URL (``https://monitoringapi.solaredge.com/v2``).
"""

from __future__ import annotations

from typing import Any, Literal, NamedTuple
from datetime import datetime
from collections.abc import Mapping, Iterable

from .exceptions import SolarEdgeValidationError

# Shared vocabulary for the API's enumerated values. Defined once here and
# reused in both clients' public signatures. These are type hints only: values
# are passed through unchanged, so a value SolarEdge adds later still works.
Resolution = Literal["QUARTER_HOUR", "HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
EnergyUnit = Literal["WH", "KWH", "MWH"]
PowerUnit = Literal["W", "KW", "MW"]
DeviceType = Literal["INVERTER", "METER", "BATTERY", "GATEWAY"]


class Request(NamedTuple):
    """A fully-described API request, independent of how it is sent.

    ``params`` is a list of pairs rather than a dict so a key can repeat, as
    ``/devices`` expects for ``types``.
    """

    method: str
    path: str
    params: list[tuple[str, Any]] | None = None


def format_datetime(value: datetime, name: str = "datetime") -> str:
    """Render a timezone-aware datetime in the ISO 8601 form V2 expects.

    V2 rejects timestamps without an offset, so a naive datetime is refused
    locally rather than guessed at.

    Raises:
        SolarEdgeValidationError: If ``value`` has no timezone.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise SolarEdgeValidationError(
            f"{name} must be timezone-aware, e.g. "
            "datetime(2026, 1, 1, tzinfo=timezone.utc); got a naive datetime."
        )
    return value.isoformat(timespec="seconds")


def _time_range(start: datetime, end: datetime) -> list[tuple[str, Any]]:
    """Validate a time range and render it as V2 ``from``/``to`` params."""
    params = [
        ("from", format_datetime(start, "start")),
        ("to", format_datetime(end, "end")),
    ]
    if end < start:
        raise SolarEdgeValidationError("end must not be before start.")
    return params


def _site_path(site_id: int | str, *parts: str) -> str:
    """Build ``sites/{id}/...``, refusing IDs that are not plain digits.

    Validating here keeps a malformed ID from producing a different path,
    e.g. ``"1/../2"``.
    """
    sid = str(site_id)
    if isinstance(site_id, bool) or not (sid.isascii() and sid.isdecimal()):
        raise SolarEdgeValidationError(
            f"site_id must be a positive integer; got {site_id!r}."
        )
    return "/".join(["sites", sid, *parts])


def sites() -> Request:
    """Build the request for the sites this key can access (Fleet Access)."""
    return Request("GET", "sites")


def site_details(site_id: int | str) -> Request:
    """Build the request for a single site's details."""
    return Request("GET", _site_path(site_id))


def overview(
    site_id: int | str,
    start: datetime | None,
    end: datetime | None,
) -> Request:
    """Build the request for a site overview, optionally for a time range."""
    if (start is None) != (end is None):
        raise SolarEdgeValidationError("Pass both start and end, or neither.")
    params = _time_range(start, end) if start and end else None
    return Request("GET", _site_path(site_id, "overview"), params)


def energy(
    site_id: int | str,
    start: datetime,
    end: datetime,
    resolution: Resolution,
    unit: EnergyUnit,
) -> Request:
    """Build the request for site energy over a time range."""
    return Request(
        "GET",
        _site_path(site_id, "energy"),
        [*_time_range(start, end), ("resolution", resolution), ("unit", unit)],
    )


def power(
    site_id: int | str,
    start: datetime,
    end: datetime,
    resolution: Resolution,
    unit: PowerUnit,
) -> Request:
    """Build the request for site power over a time range."""
    return Request(
        "GET",
        _site_path(site_id, "power"),
        [*_time_range(start, end), ("resolution", resolution), ("unit", unit)],
    )


def lifetime_energy(site_id: int | str) -> Request:
    """Build the request for the site's lifetime production counter."""
    return Request("GET", _site_path(site_id, "lifetime-energy"))


def power_flow(site_id: int | str) -> Request:
    """Build the request for the site's current power flow."""
    return Request("GET", _site_path(site_id, "power-flow"))


def devices(site_id: int | str, types: Iterable[DeviceType] | None) -> Request:
    """Build the request for the site's devices, optionally filtered by type."""
    params = [("types", t) for t in types] if types else None
    return Request("GET", _site_path(site_id, "devices"), params)


def storage_lifetime_energy(
    site_id: int | str, start: datetime, end: datetime
) -> Request:
    """Build the request for battery charge/discharge counters over a range."""
    return Request(
        "GET",
        _site_path(site_id, "storage", "lifetime-energy"),
        _time_range(start, end),
    )


def storage_telemetry(site_id: int | str, start: datetime, end: datetime) -> Request:
    """Build the request for battery telemetry over a time range."""
    return Request(
        "GET", _site_path(site_id, "storage", "telemetry"), _time_range(start, end)
    )


def meters_telemetry(site_id: int | str, start: datetime, end: datetime) -> Request:
    """Build the request for meter telemetry over a time range."""
    return Request(
        "GET", _site_path(site_id, "meters", "telemetry"), _time_range(start, end)
    )


def inverters_telemetry(site_id: int | str, start: datetime, end: datetime) -> Request:
    """Build the request for inverter telemetry over a time range."""
    return Request(
        "GET", _site_path(site_id, "inverters", "telemetry"), _time_range(start, end)
    )


def raw(path: str, params: Mapping[str, Any] | None) -> Request:
    """Build a GET for any V2 path, for endpoints without a dedicated method.

    Datetime values are rendered the same way as in the dedicated methods, and
    list or tuple values become a repeated key.
    """
    path = path.strip("/")
    if not path or ".." in path.split("/"):
        raise SolarEdgeValidationError(f"Invalid API path: {path!r}.")

    pairs: list[tuple[str, Any]] = []
    for key, value in (params or {}).items():
        values = value if isinstance(value, (list, tuple)) else [value]
        pairs.extend(
            (key, format_datetime(v, key) if isinstance(v, datetime) else v)
            for v in values
        )
    return Request("GET", path, pairs or None)
