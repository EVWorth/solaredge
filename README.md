# SolarEdge Client (Monitoring API)

<p align="center">
  <a href="https://docs.astral.sh/uv/">
    <img src="https://img.shields.io/badge/packaging-UV-299bd7?style=flat-square&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDEiIGhlaWdodD0iNDEiIHZpZXdCb3g9IjAgMCA0MSA0MSIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTS01LjI4NjE5ZS0wNiAwLjE2ODYyOUwwLjA4NDMwOTggMjAuMTY4NUwwLjE1MTc2MiAzNi4xNjgzQzAuMTYxMDc1IDM4LjM3NzQgMS45NTk0NyA0MC4xNjA3IDQuMTY4NTkgNDAuMTUxNEwyMC4xNjg0IDQwLjA4NEwzMC4xNjg0IDQwLjA0MThMMzEuMTg1MiA0MC4wMzc1QzMzLjM4NzcgNDAuMDI4MiAzNS4xNjgzIDM4LjIwMjYgMzUuMTY4MyAzNlYzNkwzNy4wMDAzIDM2TDM3LjAwMDMgMzkuOTk5Mkw0MC4xNjgzIDM5Ljk5OTZMMzkuOTk5NiAtOS45NDY1M2UtMDdMMjEuNTk5OCAwLjA3NzU2ODlMMjEuNjc3NCAxNi4wMTg1TDIxLjY3NzQgMjUuOTk5OEwyMC4wNzc0IDI1Ljk5OThMMTguMzk5OCAyNS45OTk4TDE4LjQ3NzQgMTYuMDMyTDE4LjM5OTggMC4wOTEwNTkzTC01LjI4NjE5ZS0wNiAwLjE2ODYyOVoiIGZpbGw9IiNERTVGRTkiLz4KPC9zdmc+Cg==" alt="UV">
  </a>
  <a href="https://docs.astral.sh/ruff/">
    <img src="https://img.shields.io/badge/code%20style-Ruff-8400ff?style=flat-square" alt="Ruff">
  </a>
  <a href="https://github.com/j178/prek">
    <img src="https://img.shields.io/badge/hooks-prek-f6d55c?style=flat-square" alt="prek">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/solaredge/">
    <img src="https://img.shields.io/pypi/v/solaredge?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/solaredge?style=flat-square&logo=python&logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/solaredge?style=flat-square" alt="License">
</p>



A Python client for the SolarEdge Monitoring API (V2), with synchronous and asynchronous interfaces and a method for every documented operation.

> **Upgrading from 2.x?** SolarEdge retired Monitoring API V1 on November 3,
> 2026, and every request from 2.x now fails with HTTP 410. 3.0 talks to V2,
> which needs a new API key and has different endpoints and response shapes.
> See [Migrating from 2.x](#migrating-from-2x).

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Credentials](#credentials)
- [Quick Start](#quick-start)
  - [Synchronous Usage](#synchronous-usage)
  - [Asynchronous Usage](#asynchronous-usage)
  - [Methods](#methods)
  - [Error Handling](#error-handling)
- [Rate Limits](#rate-limits)
- [Migrating from 2.x](#migrating-from-2x)
- [Development](#development)
- [API Documentation](#api-documentation)

## Features

- **Complete V2 coverage**: all 56 operations in SolarEdge's Basic Monitoring
  (2.1.0) and Advanced Monitoring (2.0.1) APIs, plus `get()` for anything added later
- **Sync & Async Support**: `MonitoringClient` and `AsyncMonitoringClient` share
  one definition of every method, so they cannot drift apart
- **Typed**: full annotations, `py.typed`, and `Literal` types for every enumerated parameter
- **OAuth built in**: Site Access tokens are refreshed automatically, with a
  `uv run python -m solaredge login` helper for homeowners
- **Safe by default**: arguments are validated before anything is sent, and
  credentials never appear in URLs, reprs or error messages

## Installation

```bash
uv add solaredge
```

## Credentials

V1 API keys do not work with V2. Which V2 credential you need depends on who
you are:

| You are | Access type | Pass to the client |
| --- | --- | --- |
| A **homeowner** reading your own system | Site Access (OAuth 2.0) | `oauth=OAuth2(...)`, or `access_token="..."` |
| An **installer** with a fleet of sites | Fleet Access (API key) | `api_key="..."` |

SolarEdge only offers Fleet Access keys to installer accounts, so homeowners
use OAuth. See SolarEdge's
[Homeowner and Self-Access Guide](https://api-docs.solaredge.com/docs/developer-platform/df8kx5j4z9vi0-homeowner-and-self-access-guide).

### Homeowners: Site Access (OAuth)

1. **Create a developer account:** sign in to the
   [Developer Platform](https://developer.solaredge.com/) with your
   mySolarEdge login and fill in the developer profile. The Free tier is enough.
2. **Create a Site Access application:**
   - Service: Monitoring API.
   - Redirect URI: `http://localhost:8080/oauth/callback`.
   - Scopes: `SITE_DATA` and `DEVICE_DATA`.
   - Copy the client secret: it is shown only once.
3. **Authorize the app for your site** with the bundled helper. It opens the
   consent page, catches the redirect and saves the token to a file only you
   can read:

   ```bash
   export SOLAREDGE_CLIENT_SECRET=...   # or omit it to be prompted
   uv run python -m solaredge login --client-id YOUR_CLIENT_ID
   # Saved the token for site 1234567 to solaredge-token.json (mode 600).
   ```

4. **Use the token.** Access tokens last 2 hours; `OAuth2` refreshes them
   automatically. Each refresh also **replaces the refresh token**, so save
   every new token in `on_token_update`, or the next run will hold a dead one.
   A refresh token unused for 14 days expires, and you have to run
   `login` again.

```python
import json
from pathlib import Path

from solaredge import MonitoringClient, OAuth2, OAuthToken

TOKEN_FILE = Path("solaredge-token.json")


def save(token: OAuthToken) -> None:
    TOKEN_FILE.write_text(json.dumps(token.to_dict()))


auth = OAuth2(
    OAuthToken.from_dict(json.loads(TOKEN_FILE.read_text())),
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    on_token_update=save,
)

with MonitoringClient(oauth=auth) as client:
    overview = client.get_overview(auth.token.site_id)
```

`OAuth2` works with both clients. With `AsyncMonitoringClient`,
`on_token_update` may be an `async` function. Concurrent requests share a single
refresh, so they never spend the same refresh token twice.

If you already manage tokens yourself, for example through Home Assistant's
OAuth helper, pass the current one with `MonitoringClient(access_token="...")`.

Building an app for *other* homeowners? `solaredge.oauth` has the pieces:
`authorization_url`, `parse_callback`, `exchange_code`, `refresh_token`,
`revoke_token`, and their `async_` variants.

### Installers: Fleet Access (API key)

Create a Fleet Access application on the Developer Platform and pass its key:
`MonitoringClient("YOUR_API_KEY")`. It is sent in the `X-API-Key` header, and
it is the only credential accepted by `get_sites` and `get_alerts`, which list
data across a fleet.

## Quick Start

All time windows take **timezone-aware** `datetime`s, which are sent as UTC. V2
rejects timestamps without an offset, so a naive `datetime` raises
`SolarEdgeValidationError` before any request is sent. Where `start`/`end` are
optional, leaving them out means "midnight today until now" in the site's
time zone.

The examples below use `auth`, the `OAuth2` object from
[Credentials](#homeowners-site-access-oauth). With a Fleet Access key, pass
`api_key="..."` instead.

### Synchronous Usage

```python
from datetime import datetime, timedelta, timezone

from solaredge import MonitoringClient

SITE_ID = 1234567
now = datetime.now(timezone.utc)

with MonitoringClient(oauth=auth) as client:
    details = client.get_site_details(SITE_ID)
    today = client.get_overview(SITE_ID)
    daily = client.get_energy(
        SITE_ID,
        start=now - timedelta(days=30),
        end=now,
        resolution="DAY",
        unit="KWH",
    )
    batteries = client.get_storage_telemetry(SITE_ID)
```

### Asynchronous Usage

```python
import asyncio
from datetime import datetime, timedelta, timezone

from solaredge import AsyncMonitoringClient


async def main():
    now = datetime.now(timezone.utc)
    async with AsyncMonitoringClient(oauth=auth) as client:
        details, power = await asyncio.gather(
            client.get_site_details(1234567),
            client.get_power(1234567, start=now - timedelta(hours=2), end=now),
        )


asyncio.run(main())
```

### Methods

Every method returns the parsed JSON unchanged. Optional arguments left as
`None` are not sent, so the API's own defaults apply. The
[API reference](docs/SE_monitoring_API.md) lists the paths, parameters and
per-resolution window limits.

| Area | Methods |
| --- | --- |
| Sites | `get_sites`, `get_site_details`, `get_overview`, `get_performance`, `get_power`, `get_energy`, `get_environmental_benefits`, `get_lifetime_energy`, `get_external_production_energy` |
| Alerts | `get_alerts` (all sites), `get_site_alerts` |
| Inventory | `get_devices`, `get_device` |
| Telemetry | `get_inverters_telemetry`, `get_meters_telemetry`, `get_storage_telemetry` |
| Status | `get_inverters_status`, `get_storage_status` |
| Lifetime counters | `get_inverters_lifetime_energy`, `get_meters_lifetime_energy`, `get_storage_lifetime_energy` |
| Inverter | `get_inverter_power`, `_energy`, `_consumed_ac_power`, `_consumed_ac_energy`, `_voltage`, `_current`, `_frequency` |
| Meter | `get_meter_production_power` / `_energy`, `get_meter_consumption_*`, `get_meter_import_*`, `get_meter_export_*` |
| Battery | `get_battery_charge_power`, `_discharge_power`, `_charge_energy`, `_discharge_energy`, `_state_of_energy`, `_remaining_energy` |
| Advanced Monitoring* | `get_power_per_destination`, `get_energy_per_destination`, `get_current_power_flow`, `start_live_power_flow`, `get_weather_guard`, `get_backup_reserve` |
| Anything else | `get(path, params=None)` |

\* Business Pro and Enterprise plans only. Other plans get HTTP 403, raised as
`SolarEdgeAuthError`.

Telemetry, status and lifetime methods cover every device of that kind on the
site. Pass `serial_numbers=[...]` to limit them to specific devices. V2 reports
units in upper case (`"WH"`, `"KWH"`, `"W"`), so compare them
case-insensitively.

### Error Handling

Every failure raises a `SolarEdgeError` subclass, so you never need to import
`httpx` to handle one. The originating `httpx` exception is preserved as
`__cause__` if you want the transport-level detail.

```python
from solaredge import (
    MonitoringClient,
    SolarEdgeAuthError,
    SolarEdgeRateLimitError,
    SolarEdgeError,
)

with MonitoringClient("YOUR_API_KEY") as client:
    try:
        flow = client.get_current_power_flow(1234567)
    except SolarEdgeAuthError:
        ...  # bad credentials, or an operation your plan does not include
    except SolarEdgeRateLimitError as exc:
        ...  # exc.retry_after, exc.limits
    except SolarEdgeError:
        ...  # anything else this library raises
```

The hierarchy:

| Exception | Raised when |
| --- | --- |
| `SolarEdgeError` | Base class for everything below |
| `SolarEdgeValidationError` | Arguments rejected locally, before any request. Also a `ValueError` |
| `SolarEdgeAPIError` | The API returned an error status, e.g. 400 for a window that is too long |
| `SolarEdgeAuthError` | 401 / 403: credentials invalid or expired, missing scope, or the operation is not in your plan |
| `SolarEdgeOAuthError` | The token endpoint rejected a code or refresh token. Carries `error` and `error_description`; an expired grant means running `login` again |
| `SolarEdgeNotFoundError` | 404: no such site, device or operation |
| `SolarEdgeRateLimitError` | 429: per-minute or monthly quota exceeded. Carries `retry_after` and `limits` (the `x-ratelimit-*` headers) |
| `SolarEdgeServerError` | 5xx: the API failed to handle a valid request |
| `SolarEdgeResponseError` | Success status, but the body could not be parsed |

`SolarEdgeAPIError` and its subclasses carry `status_code`, `response_body` and
`url`.

## Rate Limits

Every call costs one credit. Plans set a monthly credit quota and a
calls-per-minute limit; the Free tier allows 2,000 credits a month and 10 calls
a minute.

This client caps itself at 3 concurrent requests but does not retry or throttle
for you. A client that polled several endpoints every 15 minutes under V1 will
run through the Free tier's monthly quota. To stay within it:

- Prefer the bulk telemetry methods over per-device ones.
- Use coarser resolutions where you can.
- Poll less often.

## Migrating from 2.x

| 2.x method | 3.0 replacement |
| --- | --- |
| `get_site_list(...)` | `get_sites(page=..., sites_in_page=..., name=...)` |
| `get_site_details(site_id)` | `get_site_details(site_id)` |
| `get_overview(site_ids)` | `get_overview(site_id)`, one site per call |
| `get_energy(site_ids, start_date, end_date, time_unit)` | `get_energy(site_id, start, end, resolution, unit)` |
| `get_time_frame_energy(...)` | `get_energy(..., resolution="TOTAL")` |
| `get_power(site_id, start_time, end_time)` | `get_power(site_id, start, end, resolution, unit)` |
| `get_power_details(...)`, `get_energy_details(...)` | `get_meters_telemetry(...)`, or `get_power_per_destination` / `get_energy_per_destination` (Advanced) |
| `get_current_power_flow(site_id)` | `get_current_power_flow(site_id)` (Advanced) |
| `get_storage_data(...)` | `get_storage_telemetry(...)`, `get_storage_status(...)` |
| `get_environmental_benefits(site_id, system_units)` | `get_environmental_benefits(site_id, unit="METRIC" or "IMPERIAL")` |
| `get_inventory(site_id)`, `get_components_list(site_id)` | `get_devices(site_id, types=[...])` |
| `get_inverter_technical_data(site_id, serial, ...)` | `get_inverters_telemetry(...)` and `get_inverters_status(...)` with `serial_numbers=[serial]` |
| `get_meters(...)` | `get_meters_lifetime_energy(...)`, `get_meters_telemetry(...)` |
| `get_site_data(site_ids)` | No V2 equivalent |

Other changes:

- **Credentials:** V1 keys are rejected. Homeowners use Site Access (OAuth);
  installers use a V2 Fleet Access API key. See [Credentials](#credentials).
- **One site per call:** V2 has no comma-separated bulk form for sites.
- **Datetimes must be timezone-aware**, and are sent as UTC `from`/`to`.
- **Parameters renamed:** `time_unit` is now `resolution`, and
  `QUARTER_OF_AN_HOUR` is now `QUARTER_HOUR`. Enum values are upper case,
  e.g. `METRIC`, `PRODUCTION`.
- **Response bodies differ**, so code that reads fields needs updating.
- **Data no longer available:** optimizer-level telemetry (optimizers appear
  only in `get_devices`), and per-phase inverter values (V2 averages across
  phases).

## Development

```bash
# Install development dependencies
uv sync
uv run prek install -t commit-msg
```

```bash
# Commiting changes
uv run cz c
```

## API Documentation

- [V2 API reference for this library](docs/SE_monitoring_API.md)
- [SolarEdge Developer Platform documentation](https://api-docs.solaredge.com/)
- [SolarEdge: Migrating from V1 to V2](https://api-docs.solaredge.com/docs/developer-platform/mxj41549n0nxk-migrating-from-v1-to-v2)
