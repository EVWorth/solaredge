# SolarEdge Monitoring API Client

A Python client library for the SolarEdge Monitoring API, providing both synchronous and asynchronous interfaces for accessing solar energy data.

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
    for site in sites['sites']['list']:
        site_details.append(
            client.get_site_details(
                site_id=site['id'],
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
        for site in sites['sites']['list']:  
            task = client.get_site_details(site_id=site['id'])
            tasks.append(task)
        
        site_details = await asyncio.gather(*tasks)

asyncio.run(main())
```

## Rate Limiting & Best Practices

- **Daily limit**: 300 requests per API Key and per site ID 
- **Concurrency**: Maximum 3 concurrent requests from same IP
- **Bulk operations**: Up to 100 site IDs per bulk request

for more information see [page 8](https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf) of the api documentation 


## Development

```bash
# Install development dependencies
uv sync
uv run pre-commit install -t commit-msg
```

```bash
# Commiting changes
uv run cz c
```

## API Documentation

For detailed API documentation including all parameters and response formats, see:
- [SolarEdge Monitoring API Documentation](docs/SE_monitoring_API.md)
- [Official API Reference](https://www.solaredge.com/sites/default/files/se_monitoring_api.pdf)
