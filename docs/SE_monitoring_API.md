# SolarEdge Monitoring API V2: notes for this library

SolarEdge retired Monitoring API V1 on November 3, 2026. This file records
what the client relies on about V2 and how sure we are of each piece.

SolarEdge's official reference is at <https://api-docs.solaredge.com/>. It is
rendered by JavaScript, so it could not be read automatically while this client
was written. Everything below comes from that documentation as quoted by other
projects, and from their working V2 code:
[aiosolaredge](https://github.com/Solarlibs/aiosolaredge/pull/151),
[Home Assistant](https://github.com/home-assistant/core/pull/187939),
[ioBroker](https://github.com/iobroker-community-adapters/ioBroker.solaredge/pull/307)
and [Domoticz](https://github.com/domoticz/domoticz/pull/7028).

**Nothing here has been checked against a live site by this project yet.** If
you have V2 credentials and find a difference, please open an issue.

## Base URL

```
https://monitoringapi.solaredge.com/v2
```

## Authentication

V1 keys (the `api_key` query parameter) are not accepted by V2.

| Access type | Request header | Status in this library |
| --- | --- | --- |
| Fleet Access | `X-API-Key: <key>` | Supported |
| Site Access (OAuth2) | `Authorization: Bearer <access token>` | Not supported; see [#122](https://github.com/EVWorth/solaredge/issues/122) |

Site Access, for reference:

- **Authorize:** `https://connect.solaredge.com/authorize`, with scopes
  `SITE_DATA DEVICE_DATA`.
- **Token:** `POST /v2/oauth2/token`, with a JSON body.
- **Tokens:**
  - Access tokens last about 2 hours.
  - Refresh tokens rotate on every use.
  - SolarEdge appends `site_id` to the redirect URL and does not echo `state`.

## Parameters

- **Time ranges:**
  - Passed as `from` and `to`, in ISO 8601 with a UTC offset, e.g.
    `2026-01-01T00:00:00+01:00`.
  - A timestamp without an offset is rejected server-side ("Failed to convert
    ... to required type [Instant]"). The client refuses naive datetimes
    locally for that reason.
  - The `+` must be URL-encoded; httpx does this.
- **`resolution`:**
  - Confirmed: `QUARTER_HOUR`, `MONTH`, `YEAR`.
  - Assumed by analogy, not confirmed: `HOUR`, `DAY`, `WEEK`.
- **`unit`:** energy `WH`/`KWH`/`MWH`; power `W`/`KW`.
- **Units in responses:** upper case. Compare case-insensitively.
- **`types` on `/devices`:** sent as a repeated key, e.g.
  `?types=INVERTER&types=BATTERY`. Values seen: `INVERTER`, `METER`,
  `BATTERY`, `GATEWAY`.

## Endpoints

"Confirmed" means the path and parameters appear in at least one other
project's working V2 code. "Reported" means it is named in other projects'
notes, but the parameters this client sends are assumed.

| Method | Path | Params | Status |
| --- | --- | --- | --- |
| `get_sites` | `/sites` | none (paging unknown) | Reported; Fleet Access only |
| `get_site_details` | `/sites/{id}` | none | Confirmed |
| `get_overview` | `/sites/{id}/overview` | optional `from`, `to` | Confirmed |
| `get_energy` | `/sites/{id}/energy` | `from`, `to`, `resolution`, `unit` | Confirmed |
| `get_power` | `/sites/{id}/power` | `from`, `to`, `resolution`, `unit` | Confirmed |
| `get_lifetime_energy` | `/sites/{id}/lifetime-energy` | none | Confirmed |
| `get_current_power_flow` | `/sites/{id}/power-flow` | none | Confirmed; 403 below Advanced Monitoring |
| `get_devices` | `/sites/{id}/devices` | repeated `types` | Confirmed |
| `get_storage_lifetime_energy` | `/sites/{id}/storage/lifetime-energy` | `from`, `to` | Confirmed |
| `get_storage_telemetry` | `/sites/{id}/storage/telemetry` | `from`, `to` | Reported |
| `get_meters_telemetry` | `/sites/{id}/meters/telemetry` | `from`, `to` | Reported |
| `get_inverters_telemetry` | `/sites/{id}/inverters/telemetry` | `from`, `to` | Reported; about a 12-hour window per call |
| `get` | any | any | For anything else, e.g. `/sites/{id}/alerts` |

## V1 data with no known V2 equivalent

- Optimizer-level telemetry: optimizers appear only in `/devices`.
- Environmental benefits (`envBenefits`).
- Site data period (`dataPeriod`) and time-frame energy (`timeFrameEnergy`).
- Comma-separated bulk requests for multiple sites.
- Some inverter fields: temperature, mode, per-phase values.
- Some battery fields: temperature, state code.

## Limits

These are the free-tier figures; paid plans differ.

- **Per minute:** 10 requests. Remaining calls are reported in
  `x-ratelimit-limit-minute` and `x-ratelimit-remaining-minute`.
- **Per month:** 2,000 credits, at 1 credit per call, with no overage.
- **On a 429:** the response may carry `Retry-After`. This is exposed as
  `SolarEdgeRateLimitError.retry_after`.
