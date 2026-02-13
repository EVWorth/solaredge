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
    <img src="https://img.shields.io/badge/packaging-UV-299bd7?style=flat-square&logo=data:image/svg+xml;base64,"PHN2ZyB3aWR0aD0iNDEiIGhlaWdodD0iNDEiIHZpZXdCb3g9IjAgMCA0MSA0MSIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTS01LjI4NjE5ZS0wNiAwLjE2ODYyOUwwLjA4NDMwOTggMjAuMTY4NUwwLjE1MTc2MiAzNi4xNjgzQzAuMTYxMDc1IDM4LjM3NzQgMS45NTk0NyA0MC4xNjA3IDQuMTY4NTkgNDAuMTUxNEwyMC4xNjg0IDQwLjA4NEwzMC4xNjg0IDQwLjA0MThMMzEuMTg1MiA0MC4wMzc1QzMzLjM4NzcgNDAuMDI4MiAzNS4xNjgzIDM4LjIwMjYgMzUuMTY4MyAzNlYzNkwzNy4wMDAzIDM2TDM3LjAwMDMgMzkuOTk5Mkw0MC4xNjgzIDM5Ljk5OTZMMzkuOTk5NiAtOS45NDY1M2UtMDdMMjEuNTk5OCAwLjA3NzU2ODlMMjEuNjc3NCAxNi4wMTg1TDIxLjY3NzQgMjUuOTk5OEwyMC4wNzc0IDI1Ljk5OThMMTguMzk5OCAyNS45OTk4TDE4LjQ3NzQgMTYuMDMyTDE4LjM5OTggMC4wOTEwNTkzTC01LjI4NjE5ZS0wNiAwLjE2ODYyOVoiIGZpbGw9IiNERTVGRTkiLz4KPC9zdmc+Cg==" alt="UV">
  </a>
  <a href="https://docs.astral.sh/ruff/">
    <img src="https://img.shields.io/badge/code%20style-Ruff-299bd7?style=flat-square&logo=data:image/svg+xml;base64,"PHN2ZyB3aWR0aD0iNDQ2IiBoZWlnaHQ9IjU0NSIgdmlld0JveD0iMCAwIDQ0NiA1NDUiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGZpbGwtcnVsZT0iZXZlbm9kZCIgY2xpcC1ydWxlPSJldmVub2RkIiBkPSJNMTgwLjUxNiAwLjVDMTc1LjUwNyAwLjUgMTcxLjQ0NSA0LjU1OTI4IDE3MS40NDUgOS41NjY2N1YzNi43NjY3QzE3MS40NDUgNDEuNzc0IDE2Ny4zODQgNDUuODMzMyAxNjIuMzc0IDQ1LjgzMzNIMTM2Ljk3NUMxMzEuOTY1IDQ1LjgzMzMgMTI3LjkwNCA0OS44OTI2IDEyNy45MDQgNTQuOVYxMjcuNDMzQzEyNy45MDQgMTMyLjQ0MSAxMjMuODQyIDEzNi41IDExOC44MzIgMTM2LjVIOTMuNDMzMUM4OC40MjMyIDEzNi41IDg0LjM2MTkgMTQwLjU1OSA4NC4zNjE5IDE0NS41NjdWMTk1LjQzM0M4NC4zNjE5IDIwMC40NDEgODAuMzAwNiAyMDQuNSA3NS4yOTA3IDIwNC41SDQ5Ljg5MTVDNDQuODgxNiAyMDQuNSA0MC44MjAzIDIwOC41NTkgNDAuODIwMyAyMTMuNTY3VjI2My40MzNDNDAuODIwMyAyNjguNDQxIDM2Ljc1OSAyNzIuNSAzMS43NDkxIDI3Mi41SDkuMDcxMTdDNC4wNjEzIDI3Mi41IDAgMjc2LjU1OSAwIDI4MS41NjdWMzA4Ljc2N0MwIDMxMy43NzQgNC4wNjEzIDMxNy44MzMgOS4wNzExNyAzMTcuODMzSDEyNi45OTZDMTMyLjAwNiAzMTcuODMzIDEzNi4wNjggMzIxLjg5MyAxMzYuMDY4IDMyNi45VjM3Ni43NjdDMTM2LjA2OCAzODEuNzc0IDEzMi4wMDYgMzg1LjgzMyAxMjYuOTk2IDM4NS44MzNIMTAxLjU5N0M5Ni41ODczIDM4NS44MzMgOTIuNTI2IDM4OS44OTMgOTIuNTI2IDM5NC45VjQ0NC43NjdDOTIuNTI2IDQ0OS43NzQgODguNDY0NyA0NTMuODMzIDgzLjQ1NDggNDUzLjgzM0g1OC4wNTU1QzUzLjA0NTYgNDUzLjgzMyA0OC45ODQzIDQ1Ny44OTMgNDguOTg0MyA0NjIuOVY1MzUuNDMzQzQ4Ljk4NDMgNTQwLjQ0MSA1My4wNDU2IDU0NC41IDU4LjA1NTUgNTQ0LjVIMTMwLjYyNUMxMzUuNjM1IDU0NC41IDEzOS42OTYgNTQwLjQ0MSAxMzkuNjk2IDUzNS40MzNWNDk5LjE2N0gxNzUuOTgxQzE4MC45OTEgNDk5LjE2NyAxODUuMDUyIDQ5NS4xMDcgMTg1LjA1MiA0OTAuMVY0NjIuOUMxODUuMDUyIDQ1Ny44OTMgMTg5LjExMyA0NTMuODMzIDE5NC4xMjMgNDUzLjgzM0gyMTkuNTIyQzIyNC41MzIgNDUzLjgzMyAyMjguNTk0IDQ0OS43NzQgMjI4LjU5NCA0NDQuNzY3VjQxNy41NjdDMjI4LjU5NCA0MTIuNTU5IDIzMi42NTUgNDA4LjUgMjM3LjY2NSA0MDguNUgyNjMuMDY0QzI2OC4wNzQgNDA4LjUgMjcyLjEzNSA0MDQuNDQxIDI3Mi4xMzUgMzk5LjQzM1YzNzIuMjMzQzI3Mi4xMzUgMzY3LjIyNiAyNzYuMTk3IDM2My4xNjcgMjgxLjIwNiAzNjMuMTY3SDMwNi42MDZDMzExLjYxNiAzNjMuMTY3IDMxNS42NzcgMzU5LjEwNyAzMTUuNjc3IDM1NC4xVjMyNi45QzMxNS42NzcgMzIxLjg5MyAzMTkuNzM4IDMxNy44MzMgMzI0Ljc0OCAzMTcuODMzSDM1MC4xNDdDMzU1LjE1NyAzMTcuODMzIDM1OS4yMTkgMzEzLjc3NCAzNTkuMjE5IDMwOC43NjdWMjgxLjU2N0MzNTkuMjE5IDI3Ni41NTkgMzYzLjI4IDI3Mi41IDM2OC4yOSAyNzIuNUgzOTMuNjg5QzM5OC42OTkgMjcyLjUgNDAyLjc2IDI2OC40NDEgNDAyLjc2IDI2My40MzNWMTkwLjlDNDAyLjc2IDE4NS44OTMgMzk4LjY5OSAxODEuODMzIDM5My42ODkgMTgxLjgzM0gzNjcuMzgzQzM2Mi4zNzMgMTgxLjgzMyAzNTguMzExIDE3Ny43NzQgMzU4LjMxMSAxNzIuNzY3VjE0NS41NjdDMzU4LjMxMSAxNDAuNTU5IDM2Mi4zNzMgMTM2LjUgMzY3LjM4MyAxMzYuNUgzOTIuNzgyQzM5Ny43OTIgMTM2LjUgNDAxLjg1MyAxMzIuNDQxIDQwMS44NTMgMTI3LjQzM1YxMDAuMjMzQzQwMS44NTMgOTUuMjI2IDQwNS45MTQgOTEuMTY2NyA0MTAuOTI0IDkxLjE2NjdINDM2LjMyNEM0NDEuMzMzIDkxLjE2NjcgNDQ1LjM5NSA4Ny4xMDc0IDQ0NS4zOTUgODIuMVY5LjU2NjY3QzQ0NS4zOTUgNC41NTkyOSA0NDEuMzMzIDAuNSA0MzYuMzI0IDAuNUgxODAuNTE2Wk0xNDYuOTUzIDM4NS44MzNDMTQxLjk0MyAzODUuODMzIDEzNy44ODIgMzg5Ljg5MyAxMzcuODgyIDM5NC45VjQ0NC43NjdDMTM3Ljg4MiA0NDkuNzc0IDEzMy44MjEgNDUzLjgzMyAxMjguODExIDQ1My44MzNIMTAzLjQxMUM5OC40MDE1IDQ1My44MzMgOTQuMzQwMiA0NTcuODkzIDk0LjM0MDIgNDYyLjlWNDkwLjFDOTQuMzQwMiA0OTUuMTA3IDk4LjQwMTUgNDk5LjE2NyAxMDMuNDExIDQ5OS4xNjdIMTM5LjY5NlY0NjIuOUMxMzkuNjk2IDQ1Ny44OTMgMTQzLjc1NyA0NTMuODMzIDE0OC43NjcgNDUzLjgzM0gxNzQuMTY3QzE3OS4xNzYgNDUzLjgzMyAxODMuMjM4IDQ0OS43NzQgMTgzLjIzOCA0NDQuNzY3VjQxNy41NjdDMTgzLjIzOCA0MTIuNTU5IDE4Ny4yOTkgNDA4LjUgMTkyLjMwOSA0MDguNUgyMTcuNzA4QzIyMi43MTggNDA4LjUgMjI2Ljc3OSA0MDQuNDQxIDIyNi43NzkgMzk5LjQzM1YzNzIuMjMzQzIyNi43NzkgMzY3LjIyNiAyMzAuODQxIDM2My4xNjcgMjM1Ljg1MSAzNjMuMTY3SDI2MS4yNUMyNjYuMjYgMzYzLjE2NyAyNzAuMzIxIDM1OS4xMDcgMjcwLjMyMSAzNTQuMVYzMjYuOUMyNzAuMzIxIDMyMS44OTMgMjc0LjM4MiAzMTcuODMzIDI3OS4zOTIgMzE3LjgzM0gzMDQuNzkxQzMwOS44MDEgMzE3LjgzMyAzMTMuODYzIDMxMy43NzQgMzEzLjg2MyAzMDguNzY3VjI4MS41NjdDMzEzLjg2MyAyNzYuNTU5IDMxNy45MjQgMjcyLjUgMzIyLjkzNCAyNzIuNUgzNDguMzMzQzM1My4zNDMgMjcyLjUgMzU3LjQwNCAyNjguNDQxIDM1Ny40MDQgMjYzLjQzM1YyMzYuMjMzQzM1Ny40MDQgMjMxLjIyNiAzNTMuMzQzIDIyNy4xNjcgMzQ4LjMzMyAyMjcuMTY3SDI3OC40ODVDMjczLjQ3NSAyMjcuMTY3IDI2OS40MTQgMjIzLjEwNyAyNjkuNDE0IDIxOC4xVjE5MC45QzI2OS40MTQgMTg1Ljg5MyAyNzMuNDc1IDE4MS44MzMgMjc4LjQ4NSAxODEuODMzSDMwMy44ODRDMzA4Ljg5NCAxODEuODMzIDMxMi45NTYgMTc3Ljc3NCAzMTIuOTU2IDE3Mi43NjdWMTQ1LjU2N0MzMTIuOTU2IDE0MC41NTkgMzE3LjAxNyAxMzYuNSAzMjIuMDI3IDEzNi41SDM0Ny40MjZDMzUyLjQzNiAxMzYuNSAzNTYuNDk3IDEzMi40NDEgMzU2LjQ5NyAxMjcuNDMzVjEwMC4yMzNDMzU2LjQ5NyA5NS4yMjYgMzYwLjU1OCA5MS4xNjY3IDM2NS41NjggOTEuMTY2N0gzOTAuOTY4QzM5NS45NzggOTEuMTY2NyA0MDAuMDM5IDg3LjEwNzQgNDAwLjAzOSA4Mi4xVjU0LjlDNDAwLjAzOSA0OS44OTI2IDM5NS45NzggNDUuODMzMyAzOTAuOTY4IDQ1LjgzMzNIMTgyLjMzMUMxNzcuMzIxIDQ1LjgzMzMgMTczLjI1OSA0OS44OTI2IDE3My4yNTkgNTQuOVYxMjcuNDMzQzE3My4yNTkgMTMyLjQ0MSAxNjkuMTk4IDEzNi41IDE2NC4xODggMTM2LjVIMTM4Ljc4OUMxMzMuNzc5IDEzNi41IDEyOS43MTggMTQwLjU1OSAxMjkuNzE4IDE0NS41NjdWMTk1LjQzM0MxMjkuNzE4IDIwMC40NDEgMTI1LjY1NiAyMDQuNSAxMjAuNjQ3IDIwNC41SDk1LjI0NzNDOTAuMjM3NSAyMDQuNSA4Ni4xNzYyIDIwOC41NTkgODYuMTc2MiAyMTMuNTY3VjI2My40MzNDODYuMTc2MiAyNjguNDQxIDkwLjIzNzUgMjcyLjUgOTUuMjQ3MyAyNzIuNUgxNzIuMzUyQzE3Ny4zNjIgMjcyLjUgMTgxLjQyMyAyNzYuNTU5IDE4MS40MjMgMjgxLjU2N1YzNzYuNzY3QzE4MS40MjMgMzgxLjc3NCAxNzcuMzYyIDM4NS44MzMgMTcyLjM1MiAzODUuODMzSDE0Ni45NTNaIiBmaWxsPSIjRDdGRjY0Ii8+Cjwvc3ZnPgo=" alt="Ruff">
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
