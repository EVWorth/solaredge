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



A Python client for the SolarEdge Monitoring API (V2), providing both synchronous and asynchronous interfaces for accessing solar energy data.

> **Upgrading from 2.x?** SolarEdge retired Monitoring API V1 on November 3,
> 2026, and every request from 2.x now fails with HTTP 410. 3.0 talks to V2,
> which needs new credentials and has different endpoints and response shapes.
> See [Migrating from 2.x](#migrating-from-2x).

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Credentials](#credentials)
- [Quick Start](#quick-start)
  - [Synchronous Usage](#synchronous-usage)
  - [Asynchronous Usage](#asynchronous-usage)
  - [Methods](#methods)
  - [Other Endpoints](#other-endpoints)
  - [Error Handling](#error-handling)
- [Rate Limits](#rate-limits)
- [Migrating from 2.x](#migrating-from-2x)
- [Development](#development)
- [API Documentation](#api-documentation)

## Features

- **Sync & Async Support**: Choose between `MonitoringClient` (sync) and `AsyncMonitoringClient` (async)
- **Monitoring API V2**: Dedicated methods for the common V2 endpoints, plus `get()` for the rest
- **Type Hints**: Complete type annotations for better IDE support
- **Context Manager Support**: Automatic resource cleanup

## Installation

```bash
pip install solaredge
poetry add solaredge
uv add solaredge
```

## Credentials

V1 API keys do not work with V2. Create an account on the
[SolarEdge Developer Platform](https://developer.solaredge.com/) and get a V2
credential. V2 offers two kinds:

| Access type | How it authenticates | Supported here |
| --- | --- | --- |
| **Fleet Access** | Static API key in the `X-API-Key` header | Yes |
| **Site Access** | OAuth2 client ID/secret, then short-lived bearer tokens | Not yet: see [#122](https://github.com/EVWorth/solaredge/issues/122) |

Fleet Access keys are reportedly offered only to installer/fleet accounts. If
you can only get Site Access, please comment on
[#122](https://github.com/EVWorth/solaredge/issues/122) so we can gauge demand.

## Quick Start

All time ranges take **timezone-aware** `datetime`s. V2 rejects timestamps
without an offset, so a naive `datetime` raises `SolarEdgeValidationError`
before any request is sent.

### Synchronous Usage

```python
from datetime import datetime, timedelta, timezone

from solaredge import MonitoringClient

SITE_ID = 1234567
now = datetime.now(timezone.utc)

with MonitoringClient("YOUR_FLEET_API_KEY") as client:
    details = client.get_site_details(SITE_ID)
    lifetime = client.get_lifetime_energy(SITE_ID)
    energy = client.get_energy(
        SITE_ID,
        start=now - timedelta(days=30),
        end=now,
        resolution="DAY",
        unit="KWH",
    )
```

### Asynchronous Usage

```python
import asyncio
from datetime import datetime, timedelta, timezone

from solaredge import AsyncMonitoringClient


async def main():
    now = datetime.now(timezone.utc)
    async with AsyncMonitoringClient(api_key="YOUR_FLEET_API_KEY") as client:
        details, power = await asyncio.gather(
            client.get_site_details(1234567),
            client.get_power(1234567, start=now - timedelta(hours=2), end=now),
        )


asyncio.run(main())
```

### Methods

| Method | V2 endpoint |
| --- | --- |
| `get_sites()` | `GET /sites` (Fleet Access) |
| `get_site_details(site_id)` | `GET /sites/{id}` |
| `get_overview(site_id, start=None, end=None)` | `GET /sites/{id}/overview` |
| `get_energy(site_id, start, end, resolution="DAY", unit="WH")` | `GET /sites/{id}/energy` |
| `get_power(site_id, start, end, resolution="QUARTER_HOUR", unit="W")` | `GET /sites/{id}/power` |
| `get_lifetime_energy(site_id)` | `GET /sites/{id}/lifetime-energy` |
| `get_current_power_flow(site_id)` | `GET /sites/{id}/power-flow` (Advanced Monitoring plans only) |
| `get_devices(site_id, types=None)` | `GET /sites/{id}/devices` |
| `get_storage_lifetime_energy(site_id, start, end)` | `GET /sites/{id}/storage/lifetime-energy` |
| `get_storage_telemetry(site_id, start, end)` | `GET /sites/{id}/storage/telemetry` |
| `get_meters_telemetry(site_id, start, end)` | `GET /sites/{id}/meters/telemetry` |
| `get_inverters_telemetry(site_id, start, end)` | `GET /sites/{id}/inverters/telemetry` |
| `get(path, params=None)` | Any other V2 path |

Methods return the parsed JSON unchanged. V2 reports units in upper case
(`"WH"`, `"KWH"`, `"W"`, `"KW"`), so compare them case-insensitively.

### Other Endpoints

`get()` reaches any V2 path that lacks a dedicated method. It applies the same
authentication, error handling and timestamp formatting. List values are sent
as a repeated key.

```python
alerts = client.get("sites/1234567/alerts", {"from": start, "to": end})
```

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

with MonitoringClient("YOUR_FLEET_API_KEY") as client:
    try:
        flow = client.get_current_power_flow(1234567)
    except SolarEdgeAuthError:
        ...  # bad key, or an endpoint your plan does not include
    except SolarEdgeRateLimitError as exc:
        ...  # exc.retry_after, exc.status_code, exc.response_body
    except SolarEdgeError:
        ...  # anything else this library raises
```

The hierarchy:

| Exception | Raised when |
| --- | --- |
| `SolarEdgeError` | Base class for everything below |
| `SolarEdgeValidationError` | Arguments rejected locally, before any request. Also a `ValueError` |
| `SolarEdgeAPIError` | The API returned an error status |
| `SolarEdgeAuthError` | 401 / 403: key missing or invalid, or the endpoint is not in your plan |
| `SolarEdgeNotFoundError` | 404: no such site or endpoint |
| `SolarEdgeRateLimitError` | 429: per-minute or monthly quota exceeded. `retry_after` holds the `Retry-After` header |
| `SolarEdgeServerError` | 5xx: the API failed to handle a valid request |
| `SolarEdgeResponseError` | Success status, but the body could not be parsed |

`SolarEdgeAPIError` and its subclasses carry `status_code`, `response_body` and
`url`. The API key travels in a header, so it never appears in a URL or an
error message.

## Rate Limits

V2 meters usage in credits, and plans differ. On the free tier:

- **10 requests per minute**, reported in the `x-ratelimit-*-minute` response headers
- **2,000 requests per month**, with no overage

This client caps itself at 3 concurrent requests but does not retry or throttle
for you. On a 429, check `SolarEdgeRateLimitError.retry_after`. A client that
polled every 15 minutes under V1 will exhaust the free tier's monthly quota, so
poll less often or fetch wider ranges per call.

## Migrating from 2.x

| 2.x method | 3.0 replacement |
| --- | --- |
| `get_site_list(...)` | `get_sites()` |
| `get_site_details(site_id)` | `get_site_details(site_id)` (new response shape) |
| `get_overview(site_ids)` | `get_overview(site_id, start=None, end=None)` (one site per call) |
| `get_energy(site_ids, start_date, end_date, time_unit)` | `get_energy(site_id, start, end, resolution, unit)` |
| `get_power(site_id, start_time, end_time)` | `get_power(site_id, start, end, resolution, unit)` |
| `get_current_power_flow(site_id)` | `get_current_power_flow(site_id)` (Advanced Monitoring plans only) |
| `get_inventory(site_id)`, `get_components_list(site_id)` | `get_devices(site_id, types=...)` |
| `get_storage_data(...)` | `get_storage_telemetry(...)`, `get_storage_lifetime_energy(...)` |
| `get_meters(...)`, `get_power_details(...)`, `get_energy_details(...)` | `get_meters_telemetry(...)` |
| `get_inverter_technical_data(site_id, serial, ...)` | `get_inverters_telemetry(site_id, ...)` |
| `get_site_data`, `get_time_frame_energy`, `get_environmental_benefits` | No known V2 equivalent; try `get()` |

Other changes:

- **Credentials:** pass a V2 Fleet Access key; V1 keys are rejected.
- **One site per call:** V2 has no comma-separated bulk form.
- **Datetimes must be timezone-aware**, and are sent as ISO 8601 `from`/`to`.
- **`time_unit` is now `resolution`**, and `QUARTER_OF_AN_HOUR` is now `QUARTER_HOUR`.
- **Response bodies differ**, so code that reads fields needs updating.
- **Some V1 data is gone or reduced in V2.** Optimizer-level telemetry, and some
  inverter and battery fields such as temperature, mode and per-phase values,
  are reported missing.

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

- [V2 endpoint notes for this library](docs/SE_monitoring_API.md)
- [SolarEdge Developer Platform documentation](https://api-docs.solaredge.com/)
- [SolarEdge: Migrating from V1 to V2](https://api-docs.solaredge.com/docs/developer-platform/mxj41549n0nxk-migrating-from-v1-to-v2)
