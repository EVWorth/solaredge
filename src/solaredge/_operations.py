"""Every Monitoring API V2 operation, defined once for both clients.

:class:`Operations` turns each method call into a :class:`Request` and hands
it to ``_call``. The sync client's ``_call`` returns the parsed body; the async
client's returns an awaitable of it. That lets one set of methods (and one set
of docstrings) serve both clients without the two ever drifting apart.

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
from typing import Any, Generic, TypeVar
from datetime import datetime
from collections.abc import Mapping, Iterable

from . import _endpoints as ep
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
)

R = TypeVar("R")


class Operations(ABC, Generic[R]):
    """The Monitoring API V2 operations, independent of transport."""

    @abstractmethod
    def _call(self, request: Request) -> R:
        """Send ``request`` and return the parsed body (or an awaitable of it)."""

    # --- escape hatch --------------------------------------------------------

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> R:
        """GET any V2 path, for operations SolarEdge adds after this release.

        Args:
            path: Path relative to the base URL, e.g. ``"sites/123/alerts"``.
            params: Query parameters. Datetimes must be timezone-aware; list
                values are sent as a repeated key.
        """
        return self._call(ep.raw(path, params))

    # --- sites ---------------------------------------------------------------

    def get_sites(
        self,
        page: int | None = None,
        sites_in_page: int | None = None,
        name: str | None = None,
        group: str | None = None,
        state: str | None = None,
        city: str | None = None,
    ) -> R:
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

    def get_site_details(self, site_id: int) -> R:
        """Return a site's metadata."""
        return self._call(ep.site_details(site_id))

    def get_overview(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> R:
        """Return production and consumption, split by destination and source."""
        return self._call(ep.overview(site_id, start, end))

    def get_performance(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> R:
        """Return specific yield and performance ratio for a time window."""
        return self._call(ep.performance(site_id, start, end))

    def get_power(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return site production power, averaged per bucket.

        Resolution defaults to QUARTER_HOUR and unit to W.
        """
        return self._call(
            ep.site_series(site_id, "power", start, end, resolution, unit)
        )

    def get_energy(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return site production energy, summed per bucket.

        Resolution defaults to QUARTER_HOUR and unit to WH. DAY and coarser
        buckets align to midnight in the site's time zone.
        """
        return self._call(
            ep.site_series(site_id, "energy", start, end, resolution, unit)
        )

    def get_environmental_benefits(
        self, site_id: int, unit: SystemUnits | None = None
    ) -> R:
        """Return CO2 and other emissions saved, and equivalent trees planted."""
        return self._call(ep.environmental_benefits(site_id, unit))

    def get_lifetime_energy(self, site_id: int) -> R:
        """Return the site's lifetime production counter."""
        return self._call(ep.site_resource(site_id, "lifetime-energy"))

    def get_external_production_energy(self, site_id: int) -> R:
        """Return lifetime production with and without external meters' share."""
        return self._call(ep.site_resource(site_id, "external-production-energy"))

    # --- alerts --------------------------------------------------------------

    def get_alerts(
        self,
        page: int | None = None,
        alerts_in_page: int | None = None,
        group: str | None = None,
        alert_type: str | None = None,
        state: str | None = None,
        city: str | None = None,
        only_open: bool | None = None,
    ) -> R:
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

    def get_site_alerts(
        self,
        site_id: int,
        page: int | None = None,
        alerts_in_page: int | None = None,
        only_open: bool | None = None,
    ) -> R:
        """Return a site's alerts; only OPEN ones unless ``only_open=False``."""
        return self._call(ep.site_alerts(site_id, page, alerts_in_page, only_open))

    # --- inventory -----------------------------------------------------------

    def get_devices(
        self, site_id: int, types: DeviceType | Iterable[DeviceType] | None = None
    ) -> R:
        """Return the site's devices. The API returns only inverters by default."""
        return self._call(ep.devices(site_id, types))

    def get_device(self, site_id: int, serial_number: str) -> R:
        """Return one device's details."""
        return self._call(ep.device(site_id, serial_number))

    # --- bulk telemetry ------------------------------------------------------

    def get_inverters_telemetry(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> R:
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

    def get_meters_telemetry(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> R:
        """Return production, consumption, import and export for all meters."""
        return self._call(
            ep.family_series(
                site_id, "meters", "telemetry", serial_numbers, start, end, resolution
            )
        )

    def get_storage_telemetry(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> R:
        """Return charge, discharge and state of energy for all batteries."""
        return self._call(
            ep.family_series(
                site_id, "storage", "telemetry", serial_numbers, start, end, resolution
            )
        )

    # --- status --------------------------------------------------------------

    def get_inverters_status(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> R:
        """Return inverter mode, power limit and temperature, last value per bucket."""
        return self._call(
            ep.family_series(
                site_id, "inverters", "status", serial_numbers, start, end, resolution
            )
        )

    def get_storage_status(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        serial_numbers: Iterable[str] | None = None,
    ) -> R:
        """Return battery state code and internal temperature (QUARTER_HOUR only)."""
        return self._call(
            ep.family_series(
                site_id, "storage", "status", serial_numbers, start, end, resolution
            )
        )

    # --- lifetime energy counters ------------------------------------------

    def get_inverters_lifetime_energy(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        serial_number: str | None = None,
    ) -> R:
        """Return lifetime counters for all inverters, or one. Max window 1 week."""
        serials = None if serial_number is None else [serial_number]
        return self._call(
            ep.family_lifetime_energy(site_id, "inverters", serials, start, end)
        )

    def get_meters_lifetime_energy(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        serial_numbers: Iterable[str] | None = None,
        meters: MeterType | Iterable[MeterType] | None = None,
    ) -> R:
        """Return lifetime counters for all, or the given, meters.

        ``meters`` limits the directions returned. Max window 1 week.
        """
        return self._call(
            ep.family_lifetime_energy(
                site_id, "meters", serial_numbers, start, end, meters
            )
        )

    def get_storage_lifetime_energy(
        self,
        site_id: int,
        start: datetime,
        end: datetime,
        serial_numbers: Iterable[str] | None = None,
    ) -> R:
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
    ) -> R:
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

    def get_inverter_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return an inverter's AC output power."""
        return self._inverter(
            site_id, serial_number, "power", start, end, resolution, unit
        )

    def get_inverter_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return an inverter's AC energy produced."""
        return self._inverter(
            site_id, serial_number, "energy", start, end, resolution, unit
        )

    def get_inverter_consumed_ac_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return the AC power an inverter drew, e.g. to charge from the grid."""
        return self._inverter(
            site_id, serial_number, "consumed-ac-power", start, end, resolution, unit
        )

    def get_inverter_consumed_ac_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return the AC energy an inverter drew."""
        return self._inverter(
            site_id, serial_number, "consumed-ac-energy", start, end, resolution, unit
        )

    def get_inverter_voltage(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> R:
        """Return an inverter's AC voltage, averaged across active phases."""
        return self._inverter(site_id, serial_number, "voltage", start, end, resolution)

    def get_inverter_current(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> R:
        """Return an inverter's AC current, derived as power / voltage."""
        return self._inverter(site_id, serial_number, "current", start, end, resolution)

    def get_inverter_frequency(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> R:
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
    ) -> R:
        return self._call(
            ep.device_measurement(
                site_id, "meters", serial_number, metric, start, end, resolution, unit
            )
        )

    def get_meter_production_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return PV production power measured by a meter."""
        return self._meter(
            site_id, serial_number, "production-power", start, end, resolution, unit
        )

    def get_meter_production_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return PV production energy measured by a meter."""
        return self._meter(
            site_id, serial_number, "production-energy", start, end, resolution, unit
        )

    def get_meter_consumption_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return consumption power measured by a meter."""
        return self._meter(
            site_id, serial_number, "consumption-power", start, end, resolution, unit
        )

    def get_meter_consumption_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return consumption energy measured by a meter."""
        return self._meter(
            site_id, serial_number, "consumption-energy", start, end, resolution, unit
        )

    def get_meter_import_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return power drawn from the grid, measured by a meter."""
        return self._meter(
            site_id, serial_number, "import-power", start, end, resolution, unit
        )

    def get_meter_import_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return energy drawn from the grid, measured by a meter."""
        return self._meter(
            site_id, serial_number, "import-energy", start, end, resolution, unit
        )

    def get_meter_export_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return power fed to the grid, measured by a meter."""
        return self._meter(
            site_id, serial_number, "export-power", start, end, resolution, unit
        )

    def get_meter_export_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
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
    ) -> R:
        return self._call(
            ep.device_measurement(
                site_id, "storage", serial_number, metric, start, end, resolution, unit
            )
        )

    def get_battery_charge_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return a battery's charge power (always positive)."""
        return self._battery(
            site_id, serial_number, "charge-power", start, end, resolution, unit
        )

    def get_battery_discharge_power(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PowerUnit | None = None,
    ) -> R:
        """Return a battery's discharge power (always positive)."""
        return self._battery(
            site_id, serial_number, "discharge-power", start, end, resolution, unit
        )

    def get_battery_charge_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return energy charged into a battery."""
        return self._battery(
            site_id, serial_number, "charge-energy", start, end, resolution, unit
        )

    def get_battery_discharge_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return energy discharged from a battery."""
        return self._battery(
            site_id, serial_number, "discharge-energy", start, end, resolution, unit
        )

    def get_battery_state_of_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
        unit: PercentageUnit | None = None,
    ) -> R:
        """Return a battery's state of energy as a percentage of usable capacity."""
        return self._battery(
            site_id, serial_number, "state-of-energy", start, end, resolution, unit
        )

    def get_battery_remaining_energy(
        self,
        site_id: int,
        serial_number: str,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
        unit: EnergyUnit | None = None,
    ) -> R:
        """Return the energy stored in a battery."""
        return self._battery(
            site_id, serial_number, "remaining-energy", start, end, resolution, unit
        )

    # --- Advanced Monitoring (Business Pro / Enterprise plans) -----------------

    def get_power_per_destination(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: PowerResolution | None = None,
    ) -> R:
        """Return production power split into self-consumption, storage and grid.

        Advanced Monitoring: other plans get 403, raised as SolarEdgeAuthError.
        """
        return self._call(
            ep.site_series(site_id, "power/per-destination", start, end, resolution)
        )

    def get_energy_per_destination(
        self,
        site_id: int,
        start: datetime | None = None,
        end: datetime | None = None,
        resolution: Resolution | None = None,
    ) -> R:
        """Return production energy split into self-consumption, storage and grid.

        Advanced Monitoring: other plans get 403, raised as SolarEdgeAuthError.
        """
        return self._call(
            ep.site_series(site_id, "energy/per-destination", start, end, resolution)
        )

    def get_current_power_flow(self, site_id: int) -> R:
        """Return the latest power-flow sample for the PV, grid, storage and load.

        Without a live session this is the last 5-minute sample; check the
        response's ``refreshRate`` and ``updatedAt``. Advanced Monitoring only.
        """
        return self._call(ep.site_resource(site_id, "power-flow"))

    def start_live_power_flow(self, site_id: int) -> R:
        """Start a 1-minute live power-flow session (the API's only write).

        Needs supported firmware and an Ethernet, Wi-Fi or (US) LTE connection.
        Advanced Monitoring only.
        """
        return self._call(ep.start_live_power_flow(site_id))

    def get_weather_guard(self, site_id: int) -> R:
        """Return whether Weather Guard storm mode is enabled.

        Advanced Monitoring only.
        """
        return self._call(ep.site_resource(site_id, "weather-guard"))

    def get_backup_reserve(self, site_id: int) -> R:
        """Return the battery backup reserve configuration.

        Advanced Monitoring only.
        """
        return self._call(ep.site_resource(site_id, "backup-reserve"))
