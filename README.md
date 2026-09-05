# SolarEdge Client (Monitoring API)

<p align="center">
  <a href="https://solaredge.readthedocs.io">
    <img src="https://img.shields.io/readthedocs/solaredge?logo=read-the-docs&logoColor=fff&style=flat-square" alt="Documentation Status">
  </a>
  <a href="https://codecov.io/gh/EVWorth/solaredge">
    <img src="https://img.shields.io/codecov/c/github/EVWorth/solaredge?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://docs.astral.sh/uv/">
    <img src="https://img.shields.io/badge/packaging-UV-299bd7?style=flat-square&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDEiIGhlaWdodD0iNDEiIHZpZXdCb3g9IjAgMCA0MSA0MSIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTS01LjI4NjE5ZS0wNiAwLjE2ODYyOUwwLjA4NDMwOTggMjAuMTY4NUwwLjE1MTc2MiAzNi4xNjgzQzAuMTYxMDc1IDM4LjM3NzQgMS45NTk0NyA0MC4xNjA3IDQuMTY4NTkgNDAuMTUxNEwyMC4xNjg0IDQwLjA4NEwzMC4xNjg0IDQwLjA0MThMMzEuMTg1MiA0MC4wMzc1QzMzLjM4NzcgNDAuMDI4MiAzNS4xNjgzIDM4LjIwMjYgMzUuMTY4MyAzNlYzNkwzNy4wMDAzIDM2TDM3LjAwMDMgMzkuOTk5Mkw0MC4xNjgzIDM5Ljk5OTZMMzkuOTk5NiAtOS45NDY1M2UtMDdMMjEuNTk5OCAwLjA3NzU2ODlMMjEuNjc3NCAxNi4wMTg1TDIxLjY3NzQgMjUuOTk5OEwyMC4wNzc0IDI1Ljk5OThMMTguMzk5OCAyNS45OTk4TDE4LjQ3NzQgMTYuMDMyTDE4LjM5OTggMC4wOTEwNTkzTC01LjI4NjE5ZS0wNiAwLjE2ODYyOVoiIGZpbGw9IiNERTVGRTkiLz4KPC9zdmc+Cg==" alt="UV">
  </a>
  <a href="https://docs.astral.sh/ruff/">
    <img src="https://img.shields.io/badge/code%20style-Ruff-8400ff?style=flat-square" alt="Ruff">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square" alt="pre-commit">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/solaredge/">
    <img src="https://img.shields.io/pypi/v/solaredge?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/solaredge?style=flat-square&logo=python&logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/solaredge?style=flat-square" alt="License">
</p>



A Python client for the SolarEdge Monitoring API, providing both synchronous and asynchronous interfaces for accessing solar energy data.

See https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [Synchronous Usage](#synchronous-usage)
  - [Asynchronous Usage](#asynchronous-usage)
- [Rate Limiting & Best Practices](#rate-limiting--best-practices)
- [Development](#development)
- [API Documentation](#api-documentation)

## Features

- **Sync & Async Support**: Choose between `MonitoringClient` (sync) and `AsyncMonitoringClient` (async)
- **Full API Coverage**: All monitoring endpoints supported
- **Type Hints**: Complete type annotations for better IDE support
- **Rate Limiting**: Built-in awareness of API limits (3 concurrent requests)
- **Context Manager Support**: Automatic resource cleanup

## Installation

```bash
pip install solaredge
poetry add solaredge
uv add solaredge
```

## Quick Start

### Synchronous Usage

```python
from solaredge import MonitoringClient

# Basic usage
client = MonitoringClient(api_key="YOUR_API_KEY")
sites = client.get_site_list()
client.close()

# Context manager (recommended)
with MonitoringClient("YOUR_API_KEY") as client:
    site_details = []
    sites = client.get_site_list()
    for site in sites["sites"]["list"]:
        site_details.append(
            client.get_site_details(
                site_id=site["id"],
            )
        )
```

### Asynchronous Usage

```python
import asyncio
from solaredge import AsyncMonitoringClient


async def main():
    async with AsyncMonitoringClient(api_key="YOUR_API_KEY") as client:
        sites = await client.get_site_list()

        # Concurrent requests (respecting 3 concurrent limit)
        tasks = []
        for site in sites["sites"]["list"]:
            task = client.get_site_details(site_id=site["id"])
            tasks.append(task)

        site_details = await asyncio.gather(*tasks)


asyncio.run(main())
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

with MonitoringClient("YOUR_API_KEY") as client:
    try:
        sites = client.get_site_list()
    except SolarEdgeAuthError:
        ...  # bad or unauthorized API key
    except SolarEdgeRateLimitError as exc:
        ...  # exc.status_code, exc.response_body
    except SolarEdgeError:
        ...  # anything else this library raises
```

The hierarchy:

| Exception | Raised when |
| --- | --- |
| `SolarEdgeError` | Base class for everything below |
| `SolarEdgeValidationError` | Arguments rejected locally, before any request. Also a `ValueError` |
| `SolarEdgeAPIError` | The API returned an error status |
| `SolarEdgeAuthError` | 401 / 403 — key missing, invalid or not permitted |
| `SolarEdgeNotFoundError` | 404 — no such site, equipment or endpoint |
| `SolarEdgeRateLimitError` | 429 — quota or concurrency limit exceeded |
| `SolarEdgeServerError` | 5xx — the API failed to handle a valid request |
| `SolarEdgeResponseError` | Success status, but the body could not be parsed |

`SolarEdgeAPIError` and its subclasses carry `status_code`, `response_body` and
`url`.

> **Note on API keys in URLs.** SolarEdge authenticates via an `api_key` query
> parameter, so the key appears in every request URL. This library redacts it
> from exception messages, but it will still be present in anything else that
> records raw URLs — proxy logs, HTTP debug output, `httpx` event hooks. Take
> care before sharing those.

## Rate Limiting & Best Practices

- **Daily limit**: 300 requests per API Key and per site ID 
- **Concurrency**: Maximum 3 concurrent requests from same IP
- **Bulk operations**: Up to 100 site IDs per bulk request

for more information see [page 8](https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf) of the api documentation 


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

For detailed API documentation including all parameters and response formats, see:
- [SolarEdge Monitoring API Documentation](docs/SE_monitoring_API.md)
- [Official API Reference](https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf)
