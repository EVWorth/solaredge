"""Every Monitoring API V2 operation, defined once for both clients.

:class:`Operations` turns each method call into a :class:`Request` and hands
it to ``_call``. The sync client's ``_call`` returns the parsed body; the async
client's returns an awaitable of it. That lets one set of methods (and one set
of docstrings) serve both clients without the two ever drifting apart. The
overloads on each method only tell type checkers which TypedDict comes back.

Time windows take timezone-aware datetimes. Where ``start``/``end`` are
optional, omitting them makes the API default to midnight today and now, in
the site's local time. The maximum window depends on the resolution and is
enforced by the API, which answers ``400`` when it is exceeded:

=============  ==========
Resolution     Max window
=============  ==========
QUARTER_HOUR   12 hours
HOUR           24 hours
DAY            1 month
WEEK           1 year
MONTH          3 years
YEAR, TOTAL    unlimited
=============  ==========

Status endpoints allow 1 week at QUARTER_HOUR; lifetime-energy endpoints
allow 1 week.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, overload
from datetime import datetime
from collections.abc import Mapping, Iterable, Awaitable

from . import _endpoints as ep
from .types import (
    Alert,
    DeviceData,
    SiteSummary,
    Measurements,
    WeatherGuard,
    SitePowerFlow,
    SiteListResponse,
    SiteLifetimeEnergy,
    StartLivePowerFlow,
    PowerPerDestination,
    BatteryBackupReserve,
    EnergyPerDestination,
    SiteMetadataExtended,
    EnvironmentalBenefits,
    StorageStatusResponse,
    InverterStatusResponse,
    MeterTelemetryResponse,
    SensorTelemetryResponse,
    SitePerformanceResponse,
    StorageTelemetryResponse,
    InverterTelemetryResponse,
    EvChargerTelemetryResponse,
    MeterLifetimeEnergyResponse,
    SiteExternalProductionEnergy,
    StorageLifetimeEnergyResponse,
    InverterLifetimeEnergyResponse,
    SiteInverterLifetimeEnergyResponse,
)
from ._endpoints import (
    Request,
    MeterType,
    PowerUnit,
    DeviceType,
    EnergyUnit,
    Resolution,
    SystemUnits,
    PercentageUnit,
    PowerResolution,
    SensorResolution,
)


class Sync:
    """Marks a client whose operations return the parsed body directly."""


class Async:
    """Marks a client whose operations return an awaitable of the body."""


M = TypeVar("M", Sync, Async)


class Operations(ABC, Generic[M]):
    """The Monitoring API V2 operations, independent of transport.

    Each method is overloaded on ``self``: on an ``Operations[Sync]`` it returns
    the response's TypedDict (see :mod:`solaredge.types`), and on an
    ``Operations[Async]`` an awaitable of it. The single implementation below
    the overloads serves both.
    """

    @abstractmethod
    def _call(self, request: Request) -> Any:
        """Send ``request`` and return the parsed body (or an awaitable of it)."""

    # --- escape hatch --------------------------------------------------------

    @overload
    def get(
        self: Operations[Sync], path: str, params: Mapping[str, Any] | None = None
    ) -> Any: ...
    @overload
    def get(
        self: Operations[Async], path: str, params: Mapping[str, Any] | None = None
    ) -> Awaitable[Any]: ...
    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        """GET any V2 path, for operations SolarEdge adds after this release.

        Args:
            path: Path relative to the base URL, e.g. ``"sites/123/alerts"``.
            params: Query parameters. Datetimes must be timezone-aware; list
                values are sent as a repeated key.
        """
        return self._call(ep.raw(path, params))

    # --- sites ---------------------------------------------------------------

    @overload
    def get_sites(
        self: Operations[Sync],
        page: int | None = None,
        sites_in_page: int | None = None,
        name: str | None = None,
        group: str | None = None,
        state: str | None = None,
        city: str | None = None,
    ) -> SiteListResponse: ...
    @overload
    def get_sites(
        self: Operations[Async],
        page: int | None = None,
        sites_in_page: int | None = None,
        name: str | None = None,
        group: str | None = None,
        state: str | None = None,
        city: str | None = None,
    ) -> Awaitable[SiteListResponse]: ...
    def get_sites(
        self,
        page: int | None = None,
        sites_in_page: int | None = None,
        name: str | None = None,
        group: str | None = None,
        state: str | None = None,
        city: str | None = None,
    ) -> Any:
        """List the sites this API key can access. API key only, not OAuth.

        Args:
            page: 1-based page number.
            sites_in_page: Page size, 1-1000 (API default 50).
            name: Filter by site name substring.
            group: Filter by site group UUID.
            state: Filter by state abbreviation, e.g. ``"CA"``.
            city: Filter by city.
        """
        return self._call(ep.sites(page, sites_in_page, name, group, state, city))

    @overload
    def get_site_details(
        self: Operations[Sync], site_id: int
    ) -> SiteMetadataExtended: ...
    @overload
    def get_site_details(
        self: Operations[Async], site_id: int
    ) -> Awaitable[SiteMetadataExtended]: ...
    def get_site_details(self, site_id: int) -> Any:
        """Return a site's metadata."""
        return self._call(ep.site_details(site_id))

    @overload
    def get_overview(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> SiteSummary: ...
    @overload
    def get_overview(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Awaitable[SiteSummary]: ...
    def get_overview(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Any:
        """Return production and consumption, split by destination and source."""
        return self._call(ep.overview(site_id, start, end))

    @overload
    def get_performance(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> SitePerformanceResponse: ...
    @overload
    def get_performance(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Awaitable[SitePerformanceResponse]: ...
    def get_performance(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Any:
        """Return specific yield and performance ratio for a time window."""
        return self._call(ep.performance(site_id, start, end))

    @overload
    def get_power(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_power(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_power(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return site production power, averaged per bucket.

        Resolution defaults to QUARTER_HOUR and unit to W.
        """
        return self._call(
            ep.site_series(site_id, "power", start, end, resolution, unit)
        )

    @overload
    def get_energy(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_energy(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_energy(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return site production energy, summed per bucket.

        Resolution defaults to QUARTER_HOUR and unit to WH. DAY and coarser
        buckets align to midnight in the site's time zone.
        """
        return self._call(
            ep.site_series(site_id, "energy", start, end, resolution, unit)
        )

    @overload
    def get_environmental_benefits(
        self: Operations[Sync], site_id: int, unit: SystemUnits | None = None
    ) -> EnvironmentalBenefits: ...
    @overload
    def get_environmental_benefits(
        self: Operations[Async], site_id: int, unit: SystemUnits | None = None
    ) -> Awaitable[EnvironmentalBenefits]: ...
    def get_environmental_benefits(
        self, site_id: int, unit: SystemUnits | None = None
    ) -> Any:
        """Return CO2 and other emissions saved, and equivalent trees planted."""
        return self._call(ep.environmental_benefits(site_id, unit))

    @overload
    def get_lifetime_energy(
        self: Operations[Sync], site_id: int
    ) -> SiteLifetimeEnergy: ...
    @overload
    def get_lifetime_energy(
        self: Operations[Async], site_id: int
    ) -> Awaitable[SiteLifetimeEnergy]: ...
    def get_lifetime_energy(self, site_id: int) -> Any:
        """Return the site's lifetime production counter."""
        return self._call(ep.site_resource(site_id, "lifetime-energy"))

    @overload
    def get_external_production_energy(
        self: Operations[Sync], site_id: int
    ) -> SiteExternalProductionEnergy: ...
    @overload
    def get_external_production_energy(
        self: Operations[Async], site_id: int
    ) -> Awaitable[SiteExternalProductionEnergy]: ...
    def get_external_production_energy(self, site_id: int) -> Any:
        """Return lifetime production with and without external meters' share."""
        return self._call(ep.site_resource(site_id, "external-production-energy"))

    # --- alerts --------------------------------------------------------------

    @overload
    def get_alerts(
        self: Operations[Sync],
        page: int | None = None,
        alerts_in_page: int | None = None,
        group: str | None = None,
        alert_type: str | None = None,
        state: str | None = None,
        city: str | None = None,
        only_open: bool | None = None,
    ) -> list[Alert]: ...
    @overload
    def get_alerts(
        self: Operations[Async],
        page: int | None = None,
        alerts_in_page: int | None = None,
        group: str | None = None,
        alert_type: str | None = None,
        state: str | None = None,
        city: str | None = None,
        only_open: bool | None = None,
    ) -> Awaitable[list[Alert]]: ...
    def get_alerts(
        self,
        page: int | None = None,
        alerts_in_page: int | None = None,
        group: str | None = None,
        alert_type: str | None = None,
        state: str | None = None,
        city: str | None = None,
        only_open: bool | None = None,
    ) -> Any:
        """Return alerts across every accessible site. API key only, not OAuth.

        Args:
            page: 1-based page number.
            alerts_in_page: Page size, 1-100 (API default 50).
            group: Filter by site group UUID.
            alert_type: Filter by alert type.
            state: Filter by state abbreviation.
            city: Filter by city.
            only_open: Only OPEN alerts (API default True).
        """
        return self._call(
            ep.fleet_alerts(
                page, alerts_in_page, group, alert_type, state, city, only_open
            )
        )

    @overload
    def get_site_alerts(
        self: Operations[Sync],
        site_id: int,
        page: int | None = None,
        alerts_in_page: int | None = None,
        only_open: bool | None = None,
    ) -> list[Alert]: ...
    @overload
    def get_site_alerts(
        self: Operations[Async],
        site_id: int,
        page: int | None = None,
        alerts_in_page: int | None = None,
        only_open: bool | None = None,
    ) -> Awaitable[list[Alert]]: ...
    def get_site_alerts(
        self,
        site_id: int,
        page: int | None = None,
        alerts_in_page: int | None = None,
        only_open: bool | None = None,
    ) -> Any:
        """Return a site's alerts; only OPEN ones unless ``only_open=False``."""
        return self._call(ep.site_alerts(site_id, page, alerts_in_page, only_open))

    # --- inventory -----------------------------------------------------------

    @overload
    def get_devices(
        self: Operations[Sync],
        site_id: int,
        types: DeviceType | Iterable[DeviceType] | None = None,
    ) -> list[DeviceData]: ...
    @overload
    def get_devices(
        self: Operations[Async],
        site_id: int,
        types: DeviceType | Iterable[DeviceType] | None = None,
    ) -> Awaitable[list[DeviceData]]: ...
    def get_devices(
        self, site_id: int, types: DeviceType | Iterable[DeviceType] | None = None
    ) -> Any:
        """Return the site's devices. The API returns only inverters by default."""
        return self._call(ep.devices(site_id, types))

    @overload
    def get_device(
        self: Operations[Sync], site_id: int, serial_number: str
    ) -> DeviceData: ...
    @overload
    def get_device(
        self: Operations[Async], site_id: int, serial_number: str
    ) -> Awaitable[DeviceData]: ...
    def get_device(self, site_id: int, serial_number: str) -> Any:
        """Return one device's details."""
        return self._call(ep.device(site_id, serial_number))

    # --- bulk telemetry ------------------------------------------------------

    @overload
    def get_inverters_telemetry(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> InverterTelemetryResponse: ...
    @overload
    def get_inverters_telemetry(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Awaitable[InverterTelemetryResponse]: ...
    def get_inverters_telemetry(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Any:
        """Return every inverter metric for all, or the given, inverters.

        Power, voltage, current and frequency are only available at
        QUARTER_HOUR and HOUR; coarser resolutions return energy metrics only.
        """
        return self._call(
            ep.family_series(
                site_id,
                "inverters",
                "telemetry",
                serial_numbers,
                start,
                end,
                resolution,
            )
        )

    @overload
    def get_meters_telemetry(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> MeterTelemetryResponse: ...
    @overload
    def get_meters_telemetry(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Awaitable[MeterTelemetryResponse]: ...
    def get_meters_telemetry(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Any:
        """Return production, consumption, import and export for all meters."""
        return self._call(
            ep.family_series(
                site_id, "meters", "telemetry", serial_numbers, start, end, resolution
            )
        )

    @overload
    def get_storage_telemetry(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> StorageTelemetryResponse: ...
    @overload
    def get_storage_telemetry(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Awaitable[StorageTelemetryResponse]: ...
    def get_storage_telemetry(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Any:
        """Return charge, discharge and state of energy for all batteries."""
        return self._call(
            ep.family_series(
                site_id, "storage", "telemetry", serial_numbers, start, end, resolution
            )
        )

    @overload
    def get_ev_chargers_telemetry(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> EvChargerTelemetryResponse: ...
    @overload
    def get_ev_chargers_telemetry(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Awaitable[EvChargerTelemetryResponse]: ...
    def get_ev_chargers_telemetry(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Any:
        """Return charging power and energy for all EV chargers.

        DAY and coarser resolutions return charging energy only. Serial numbers
        that are not EV chargers on the site are skipped; ``404`` if none is.
        """
        return self._call(
            ep.family_series(
                site_id,
                "ev-chargers",
                "telemetry",
                serial_numbers,
                start,
                end,
                resolution,
            )
        )

    @overload
    def get_sensors_telemetry(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: SensorResolution | None = None,
    ) -> SensorTelemetryResponse: ...
    @overload
    def get_sensors_telemetry(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: SensorResolution | None = None,
    ) -> Awaitable[SensorTelemetryResponse]: ...
    def get_sensors_telemetry(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: SensorResolution | None = None,
    ) -> Any:
        """Return irradiance, temperature and wind readings for all sensors.

        Keyed by sensor ``id``, as listed by ``get_devices(types="SENSOR")``.
        DAY, WEEK and MONTH allow up to 1 month.
        """
        return self._call(ep.sensor_telemetry(site_id, start, end, resolution))

    # --- status --------------------------------------------------------------

    @overload
    def get_inverters_status(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> InverterStatusResponse: ...
    @overload
    def get_inverters_status(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Awaitable[InverterStatusResponse]: ...
    def get_inverters_status(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Any:
        """Return inverter mode, power limit and temperature, last value per bucket."""
        return self._call(
            ep.family_series(
                site_id, "inverters", "status", serial_numbers, start, end, resolution
            )
        )

    @overload
    def get_storage_status(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> StorageStatusResponse: ...
    @overload
    def get_storage_status(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Awaitable[StorageStatusResponse]: ...
    def get_storage_status(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> Any:
        """Return battery state code and internal temperature (QUARTER_HOUR only)."""
        return self._call(
            ep.family_series(
                site_id, "storage", "status", serial_numbers, start, end, resolution
            )
        )

    # --- lifetime energy counters ------------------------------------------

    # The single-inverter path returns a different shape from the all-inverters
    # one, so the return type also depends on whether serial_number is given.
    @overload
    def get_inverters_lifetime_energy(
        self: Operations[Sync],
        site_id: int,
        start: datetime,
        end: datetime,
        serial_number: None = None,
    ) -> SiteInverterLifetimeEnergyResponse: ...
    @overload
    def get_inverters_lifetime_energy(
        self: Operations[Sync],
        site_id: int,
        start: datetime,
        end: datetime,
        serial_number: str,
    ) -> InverterLifetimeEnergyResponse: ...
    @overload
    def get_inverters_lifetime_energy(
        self: Operations[Async],
        site_id: int,
        start: datetime,
        end: datetime,
        serial_number: None = None,
    ) -> Awaitable[SiteInverterLifetimeEnergyResponse]: ...
    @overload
    def get_inverters_lifetime_energy(
        self: Operations[Async],
        site_id: int,
        start: datetime,
        end: datetime,
        serial_number: str,
    ) -> Awaitable[InverterLifetimeEnergyResponse]: ...
    def get_inverters_lifetime_energy(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        serial_number: str | None = None,
    ) -> Any:
        """Return lifetime counters for all inverters, or one. Max window 1 week."""
        serials = None if serial_number is None else [serial_number]
        return self._call(
            ep.family_lifetime_energy(site_id, "inverters", serials, start, end)
        )

    @overload
    def get_meters_lifetime_energy(
        self: Operations[Sync],
        site_id: int,
        start: datetime,
        end: datetime,
        serial_numbers: Iterable[str] | None = None,
        meters: MeterType | Iterable[MeterType] | None = None,
    ) -> MeterLifetimeEnergyResponse: ...
    @overload
    def get_meters_lifetime_energy(
        self: Operations[Async],
        site_id: int,
        start: datetime,
        end: datetime,
        serial_numbers: Iterable[str] | None = None,
        meters: MeterType | Iterable[MeterType] | None = None,
    ) -> Awaitable[MeterLifetimeEnergyResponse]: ...
    def get_meters_lifetime_energy(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        serial_numbers: Iterable[str] | None = None,
        meters: MeterType | Iterable[MeterType] | None = None,
    ) -> Any:
        """Return lifetime counters for all, or the given, meters.

        ``meters`` limits the directions returned. Max window 1 week.
        """
        return self._call(
            ep.family_lifetime_energy(
                site_id, "meters", serial_numbers, start, end, meters
            )
        )

    @overload
    def get_storage_lifetime_energy(
        self: Operations[Sync],
        site_id: int,
        start: datetime,
        end: datetime,
        serial_numbers: Iterable[str] | None = None,
    ) -> StorageLifetimeEnergyResponse: ...
    @overload
    def get_storage_lifetime_energy(
        self: Operations[Async],
        site_id: int,
        start: datetime,
        end: datetime,
        serial_numbers: Iterable[str] | None = None,
    ) -> Awaitable[StorageLifetimeEnergyResponse]: ...
    def get_storage_lifetime_energy(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        serial_numbers: Iterable[str] | None = None,
    ) -> Any:
        """Return charge/discharge counters for all, or the given, batteries."""
        return self._call(
            ep.family_lifetime_energy(site_id, "storage", serial_numbers, start, end)
        )

    # --- per-inverter measurements -------------------------------------------

    def _inverter(
        self,
        site_id: int,
        serial_number: str,
        metric: str,
        start: datetime | None,
        end: datetime | None,
        resolution: str | None,
        unit: str | None = None,
    ) -> Any:
        return self._call(
            ep.device_measurement(
                site_id,
                "inverters",
                serial_number,
                metric,
                start,
                end,
                resolution,
                unit,
            )
        )

    @overload
    def get_inverter_power(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_inverter_power(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_inverter_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return an inverter's AC output power."""
        return self._inverter(
            site_id, serial_number, "power", start, end, resolution, unit
        )

    @overload
    def get_inverter_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_inverter_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_inverter_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return an inverter's AC energy produced."""
        return self._inverter(
            site_id, serial_number, "energy", start, end, resolution, unit
        )

    @overload
    def get_inverter_consumed_ac_power(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_inverter_consumed_ac_power(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_inverter_consumed_ac_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return the AC power an inverter drew, e.g. to charge from the grid."""
        return self._inverter(
            site_id, serial_number, "consumed-ac-power", start, end, resolution, unit
        )

    @overload
    def get_inverter_consumed_ac_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_inverter_consumed_ac_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_inverter_consumed_ac_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return the AC energy an inverter drew."""
        return self._inverter(
            site_id, serial_number, "consumed-ac-energy", start, end, resolution, unit
        )

    @overload
    def get_inverter_voltage(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Measurements: ...
    @overload
    def get_inverter_voltage(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_inverter_voltage(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Any:
        """Return an inverter's AC voltage, averaged across active phases."""
        return self._inverter(site_id, serial_number, "voltage", start, end, resolution)

    @overload
    def get_inverter_current(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Measurements: ...
    @overload
    def get_inverter_current(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_inverter_current(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Any:
        """Return an inverter's AC current, derived as power / voltage."""
        return self._inverter(site_id, serial_number, "current", start, end, resolution)

    @overload
    def get_inverter_frequency(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Measurements: ...
    @overload
    def get_inverter_frequency(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_inverter_frequency(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Any:
        """Return an inverter's AC grid frequency."""
        return self._inverter(
            site_id, serial_number, "frequency", start, end, resolution
        )

    # --- per-meter measurements ----------------------------------------------

    def _meter(
        self,
        site_id: int,
        serial_number: str,
        metric: str,
        start: datetime | None,
        end: datetime | None,
        resolution: str | None,
        unit: str | None,
    ) -> Any:
        return self._call(
            ep.device_measurement(
                site_id, "meters", serial_number, metric, start, end, resolution, unit
            )
        )

    @overload
    def get_meter_production_power(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_meter_production_power(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_meter_production_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return PV production power measured by a meter."""
        return self._meter(
            site_id, serial_number, "production-power", start, end, resolution, unit
        )

    @overload
    def get_meter_production_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_meter_production_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_meter_production_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return PV production energy measured by a meter."""
        return self._meter(
            site_id, serial_number, "production-energy", start, end, resolution, unit
        )

    @overload
    def get_meter_consumption_power(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_meter_consumption_power(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_meter_consumption_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return consumption power measured by a meter."""
        return self._meter(
            site_id, serial_number, "consumption-power", start, end, resolution, unit
        )

    @overload
    def get_meter_consumption_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_meter_consumption_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_meter_consumption_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return consumption energy measured by a meter."""
        return self._meter(
            site_id, serial_number, "consumption-energy", start, end, resolution, unit
        )

    @overload
    def get_meter_import_power(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_meter_import_power(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_meter_import_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return power drawn from the grid, measured by a meter."""
        return self._meter(
            site_id, serial_number, "import-power", start, end, resolution, unit
        )

    @overload
    def get_meter_import_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_meter_import_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_meter_import_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return energy drawn from the grid, measured by a meter."""
        return self._meter(
            site_id, serial_number, "import-energy", start, end, resolution, unit
        )

    @overload
    def get_meter_export_power(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_meter_export_power(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_meter_export_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return power fed to the grid, measured by a meter."""
        return self._meter(
            site_id, serial_number, "export-power", start, end, resolution, unit
        )

    @overload
    def get_meter_export_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_meter_export_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_meter_export_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return energy fed to the grid, measured by a meter."""
        return self._meter(
            site_id, serial_number, "export-energy", start, end, resolution, unit
        )

    # --- per-battery measurements --------------------------------------------

    def _battery(
        self,
        site_id: int,
        serial_number: str,
        metric: str,
        start: datetime | None,
        end: datetime | None,
        resolution: str | None,
        unit: str | None,
    ) -> Any:
        return self._call(
            ep.device_measurement(
                site_id, "storage", serial_number, metric, start, end, resolution, unit
            )
        )

    @overload
    def get_battery_charge_power(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_battery_charge_power(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_battery_charge_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return a battery's charge power (always positive)."""
        return self._battery(
            site_id, serial_number, "charge-power", start, end, resolution, unit
        )

    @overload
    def get_battery_discharge_power(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_battery_discharge_power(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_battery_discharge_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> Any:
        """Return a battery's discharge power (always positive)."""
        return self._battery(
            site_id, serial_number, "discharge-power", start, end, resolution, unit
        )

    @overload
    def get_battery_charge_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_battery_charge_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_battery_charge_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return energy charged into a battery."""
        return self._battery(
            site_id, serial_number, "charge-energy", start, end, resolution, unit
        )

    @overload
    def get_battery_discharge_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_battery_discharge_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_battery_discharge_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return energy discharged from a battery."""
        return self._battery(
            site_id, serial_number, "discharge-energy", start, end, resolution, unit
        )

    @overload
    def get_battery_state_of_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PercentageUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_battery_state_of_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PercentageUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_battery_state_of_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PercentageUnit | None = None,
    ) -> Any:
        """Return a battery's state of energy as a percentage of usable capacity."""
        return self._battery(
            site_id, serial_number, "state-of-energy", start, end, resolution, unit
        )

    @overload
    def get_battery_remaining_energy(
        self: Operations[Sync],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Measurements: ...
    @overload
    def get_battery_remaining_energy(
        self: Operations[Async],
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Awaitable[Measurements]: ...
    def get_battery_remaining_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> Any:
        """Return the energy stored in a battery."""
        return self._battery(
            site_id, serial_number, "remaining-energy", start, end, resolution, unit
        )

    # --- Advanced Monitoring (Business Pro / Enterprise plans) -----------------

    @overload
    def get_power_per_destination(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> PowerPerDestination: ...
    @overload
    def get_power_per_destination(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Awaitable[PowerPerDestination]: ...
    def get_power_per_destination(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> Any:
        """Return production power split into self-consumption, storage and grid.

        Advanced Monitoring: other plans get 403, raised as SolarEdgeAuthError.
        """
        return self._call(
            ep.site_series(site_id, "power/per-destination", start, end, resolution)
        )

    @overload
    def get_energy_per_destination(
        self: Operations[Sync],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
    ) -> EnergyPerDestination: ...
    @overload
    def get_energy_per_destination(
        self: Operations[Async],
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
    ) -> Awaitable[EnergyPerDestination]: ...
    def get_energy_per_destination(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
    ) -> Any:
        """Return production energy split into self-consumption, storage and grid.

        Advanced Monitoring: other plans get 403, raised as SolarEdgeAuthError.
        """
        return self._call(
            ep.site_series(site_id, "energy/per-destination", start, end, resolution)
        )

    @overload
    def get_current_power_flow(
        self: Operations[Sync], site_id: int
    ) -> SitePowerFlow: ...
    @overload
    def get_current_power_flow(
        self: Operations[Async], site_id: int
    ) -> Awaitable[SitePowerFlow]: ...
    def get_current_power_flow(self, site_id: int) -> Any:
        """Return the latest power-flow sample for the PV, grid, storage and load.

        Without a live session this is the last 5-minute sample; check the
        response's ``refreshRate`` and ``updatedAt``. Advanced Monitoring only.
        """
        return self._call(ep.site_resource(site_id, "power-flow"))

    @overload
    def start_live_power_flow(
        self: Operations[Sync], site_id: int
    ) -> StartLivePowerFlow | None: ...
    @overload
    def start_live_power_flow(
        self: Operations[Async], site_id: int
    ) -> Awaitable[StartLivePowerFlow | None]: ...
    def start_live_power_flow(self, site_id: int) -> Any:
        """Start a 1-minute live power-flow session (the API's only write).

        Needs supported firmware and an Ethernet, Wi-Fi or (US) LTE connection.
        Advanced Monitoring only.
        """
        return self._call(ep.start_live_power_flow(site_id))

    @overload
    def get_weather_guard(self: Operations[Sync], site_id: int) -> WeatherGuard: ...
    @overload
    def get_weather_guard(
        self: Operations[Async], site_id: int
    ) -> Awaitable[WeatherGuard]: ...
    def get_weather_guard(self, site_id: int) -> Any:
        """Return whether Weather Guard storm mode is enabled.

        Advanced Monitoring only.
        """
        return self._call(ep.site_resource(site_id, "weather-guard"))

    @overload
    def get_backup_reserve(
        self: Operations[Sync], site_id: int
    ) -> BatteryBackupReserve: ...
    @overload
    def get_backup_reserve(
        self: Operations[Async], site_id: int
    ) -> Awaitable[BatteryBackupReserve]: ...
    def get_backup_reserve(self, site_id: int) -> Any:
        """Return the battery backup reserve configuration.

        Advanced Monitoring only.
        """
        return self._call(ep.site_resource(site_id, "backup-reserve"))
