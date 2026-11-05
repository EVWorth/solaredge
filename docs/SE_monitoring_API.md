# SolarEdge Monitoring API V2 reference

This client covers all 56 operations in SolarEdge's published specifications:

- [Basic Monitoring API](https://api-docs.solaredge.com/docs/basic-monitoring-api) 2.1.0: 50 operations, available on every plan.
- [Advanced Monitoring API](https://api-docs.solaredge.com/docs/advanced-monitoring) 2.0.1: 6 operations, Business Pro and Enterprise plans only. Other plans get `403`.

Monitoring API V1 was retired on 2026-11-03.

## Base URL and authentication

- **Base URL:** `https://monitoringapi.solaredge.com/v2`
- **API key:**
  - Sent in the `X-API-Key` header.
  - Comes from the [developer portal](https://developer.solaredge.com/).
  - Every operation accepts it, and this client uses it.
- **OAuth 2.0:**
  - Bearer token, authorization code flow.
  - Accepted by every operation except `GET /sites` and `GET /alerts`.
  - Not yet supported here; see [#122](https://github.com/EVWorth/solaredge/issues/122).

## Conventions

- **Time windows:**
  - Passed as `from`/`to`, which this client takes as timezone-aware `start`/`end`.
  - Sent as UTC instants, e.g. `2026-10-01T00:00:00Z`. V2 rejects timestamps without an offset.
  - Where optional, the window defaults to midnight today until now, in the site's local time.
  - Required on the lifetime-energy operations.
- **Buckets:** each value's timestamp marks the start of its bucket, except inverter voltage and frequency, where it marks the end. `DAY` and coarser buckets align to midnight in the site's time zone.
- **Units in responses:** upper case (`WH`, `KWH`, `W`, `KW`). Compare case-insensitively.
- **Serial numbers:** operations marked `[/{sn}]` take an optional comma-separated list of serials. Without it, the site-wide variant covers every active device of that family.

### Maximum window per request

The API answers `400` when a request exceeds these limits:

| Resolution | Max window |
| --- | --- |
| `QUARTER_HOUR` | 12 hours (status: 1 week) |
| `HOUR` | 24 hours |
| `DAY` | 1 month |
| `WEEK` | 1 year |
| `MONTH` | 3 years |
| `YEAR`, `TOTAL` | unlimited |

Lifetime-energy operations allow at most 1 week. `QUARTER_HOUR` data is
guaranteed only for the last year.

## Operations

Paths are relative to the base URL. `{id}` is the site ID.

### Sites

| Method | Operation | Query parameters |
| --- | --- | --- |
| `get_sites` | `GET /sites` (API key only) | `page`, `sites-in-page` (1-1000, default 50), `name`, `group`, `state`, `city` |
| `get_site_details` | `GET /sites/{id}` | |
| `get_overview` | `GET /sites/{id}/overview` | `from`, `to` |
| `get_performance` | `GET /sites/{id}/overview/performance` | `from`, `to` |
| `get_power` | `GET /sites/{id}/power` | `from`, `to`, `resolution` (`QUARTER_HOUR`/`HOUR`), `unit` (`W`/`KW`/`MW`) |
| `get_energy` | `GET /sites/{id}/energy` | `from`, `to`, `resolution` (all), `unit` (`WH`/`KWH`/`MWH`) |
| `get_environmental_benefits` | `GET /sites/{id}/environmental-benefits` | `unit` (`METRIC`/`IMPERIAL`) |
| `get_lifetime_energy` | `GET /sites/{id}/lifetime-energy` | |
| `get_external_production_energy` | `GET /sites/{id}/external-production-energy` | |

### Alerts

| Method | Operation | Query parameters |
| --- | --- | --- |
| `get_alerts` | `GET /alerts` (API key only) | `page`, `alerts-in-page` (1-100, default 50), `group`, `type`, `state`, `city`, `only-open` (default true) |
| `get_site_alerts` | `GET /sites/{id}/alerts` | `page`, `alerts-in-page`, `only-open` |

### Inventory

| Method | Operation | Query parameters |
| --- | --- | --- |
| `get_devices` | `GET /sites/{id}/devices` | `types`, repeated; defaults to `INVERTER` only |
| `get_device` | `GET /sites/{id}/devices/{sn}` | |

Device types: `INVERTER`, `BATTERY`, `BATTERY_MODULE`, `OPTIMIZER`, `METER`,
`EV_CHARGER`, `BUI`, `GATEWAY`.

### Telemetry, status and lifetime energy

| Method | Operation | Query parameters |
| --- | --- | --- |
| `get_inverters_telemetry` | `GET /sites/{id}/inverters[/{sn}]/telemetry` | `from`, `to`, `resolution` |
| `get_meters_telemetry` | `GET /sites/{id}/meters[/{sn}]/telemetry` | `from`, `to`, `resolution` |
| `get_storage_telemetry` | `GET /sites/{id}/storage[/{sn}]/telemetry` | `from`, `to`, `resolution` |
| `get_inverters_status` | `GET /sites/{id}/inverters[/{sn}]/status` | `from`, `to`, `resolution` (`QUARTER_HOUR`/`HOUR`) |
| `get_storage_status` | `GET /sites/{id}/storage[/{sn}]/status` | `from`, `to`, `resolution` (`QUARTER_HOUR`) |
| `get_inverters_lifetime_energy` | `GET /sites/{id}/inverters[/{sn}]/lifetime-energy` | `from`*, `to`* |
| `get_meters_lifetime_energy` | `GET /sites/{id}/meters[/{sn}]/lifetime-energy` | `from`*, `to`*, `meters` |
| `get_storage_lifetime_energy` | `GET /sites/{id}/storage[/{sn}]/lifetime-energy` | `from`*, `to`* |

\* required. For `get_inverters_lifetime_energy`, `{sn}` is a single serial.

`meters` takes a comma-separated list of directions to return:
`PRODUCTION`, `CONSUMPTION`, `FEEDIN` and `PURCHASED`. `EXPORT` and `IMPORT`
are accepted as equivalents of `FEEDIN` and `PURCHASED`.

Metrics at coarser resolutions:

- **Inverter telemetry:** power, voltage, current and frequency are available
  at `QUARTER_HOUR` and `HOUR` only.
- **Storage telemetry:** power and state of energy are available at
  `QUARTER_HOUR` and `HOUR` only.
- **Coarser resolutions:** return energy metrics only.

### Single-device measurements

All take `from`, `to` and `resolution`. Power metrics accept `QUARTER_HOUR` or
`HOUR`; energy metrics accept every resolution. `unit` applies where shown.

| Method | Path under `/sites/{id}/` | `unit` |
| --- | --- | --- |
| `get_inverter_power` | `inverters/{sn}/power` | `W`/`KW`/`MW` |
| `get_inverter_energy` | `inverters/{sn}/energy` | `WH`/`KWH`/`MWH` |
| `get_inverter_consumed_ac_power` | `inverters/{sn}/consumed-ac-power` | `W`/`KW`/`MW` |
| `get_inverter_consumed_ac_energy` | `inverters/{sn}/consumed-ac-energy` | `WH`/`KWH`/`MWH` |
| `get_inverter_voltage` | `inverters/{sn}/voltage` | |
| `get_inverter_current` | `inverters/{sn}/current` | |
| `get_inverter_frequency` | `inverters/{sn}/frequency` | |
| `get_meter_production_power` / `_energy` | `meters/{sn}/production-power` / `-energy` | power / energy units |
| `get_meter_consumption_power` / `_energy` | `meters/{sn}/consumption-power` / `-energy` | power / energy units |
| `get_meter_import_power` / `_energy` | `meters/{sn}/import-power` / `-energy` | power / energy units |
| `get_meter_export_power` / `_energy` | `meters/{sn}/export-power` / `-energy` | power / energy units |
| `get_battery_charge_power` | `storage/{sn}/charge-power` | `W`/`KW`/`MW` |
| `get_battery_discharge_power` | `storage/{sn}/discharge-power` | `W`/`KW`/`MW` |
| `get_battery_charge_energy` | `storage/{sn}/charge-energy` | `WH`/`KWH`/`MWH` |
| `get_battery_discharge_energy` | `storage/{sn}/discharge-energy` | `WH`/`KWH`/`MWH` |
| `get_battery_state_of_energy` | `storage/{sn}/state-of-energy` | `PERCENTAGE`/`PERCENTAGE_100` |
| `get_battery_remaining_energy` | `storage/{sn}/remaining-energy` | `WH`/`KWH`/`MWH` |

### Advanced Monitoring

| Method | Operation | Query parameters |
| --- | --- | --- |
| `get_power_per_destination` | `GET /sites/{id}/power/per-destination` | `from`, `to`, `resolution` (`QUARTER_HOUR`/`HOUR`) |
| `get_energy_per_destination` | `GET /sites/{id}/energy/per-destination` | `from`, `to`, `resolution` |
| `get_current_power_flow` | `GET /sites/{id}/power-flow` | |
| `start_live_power_flow` | `POST /sites/{id}/power-flow` | |
| `get_weather_guard` | `GET /sites/{id}/weather-guard` | |
| `get_backup_reserve` | `GET /sites/{id}/backup-reserve` | |

How power flow works:

- `GET .../power-flow` returns the most recent sample. Without a live session,
  that is the last 5-minute reading (`refreshRate: 300`).
- `POST .../power-flow` starts a 1-minute live session, the API's only write.
  It needs supported firmware and an Ethernet, Wi-Fi or (US only) LTE connection.

Weather Guard and backup reserve are read-only here. SolarEdge says changing
them will be part of a separate Fleet Management API that hasn't been released.

## Rate limits

- **Cost:** every operation costs 1 credit.
- **Limits:** a monthly credit quota and a calls-per-minute (CPM) limit, both
  set by plan tier. The Free tier allows 2,000 credits a month and 10 CPM.
- **On a 429:** the response may carry `retry-after` and `x-ratelimit-*`
  headers (`limit`/`remaining`, per `minute`, `month` and `second`). This
  client exposes them as `SolarEdgeRateLimitError.retry_after` and `.limits`.
- **In practice:** other projects report seeing only the per-minute headers,
  and no `retry-after` once the monthly quota is spent.

## V1 data with no V2 equivalent

- Optimizer-level telemetry: optimizers appear only in `get_devices`.
- Site data period (`dataPeriod`) and time-frame energy (`timeFrameEnergy`).
- Comma-separated bulk requests across multiple sites.
