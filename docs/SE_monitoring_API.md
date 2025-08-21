# SolarEdge Monitoring API — reference

This document collects the monitoring API endpoints referenced in the repository and the high-level rules from the
SolarEdge Monitoring API specification. Use this as a developer reference when implementing client methods.

## Base URL

```
https://monitoringapi.solaredge.com
```

## Authentication

- Every request requires the `api_key` parameter. Example: `?api_key=YOUR_KEY`

## Common notes

- Responses are JSON objects. Client methods should call `response.raise_for_status()` (or handle errors) and parse JSON.
- Rate limits and concurrency are enforced by the server (see Limits section below).
- Several endpoints support bulk requests by accepting comma-separated site IDs (up to 100 IDs).

---

## Endpoints

### 1) Site List
- Path: `/sites/list`
- Method: GET
- Purpose: Returns a paginated list of sites for the account.
- Common query params: `api_key`, `size`, `startIndex`, `searchText`, `sortProperty`, `sortOrder`, `status`
- Example: `/sites/list?api_key=KEY&size=50&startIndex=0&status=Active`

### 2) Site Details
- Path: `/site/{siteId}/details`
- Method: GET
- Purpose: Details for a single site (location, configuration, contact info, etc.).
- Params: `api_key`

### 3) Site Data Period
- Path: `/site/{siteId}/dataPeriod`
- Method: GET
- Purpose: Returns the site energy production `startDate` and `endDate`.
- Params: `api_key`

### 4) Site Energy
- Path: `/site/{siteId}/energy`
- Method: GET
- Purpose: Aggregated energy measurements for a site.
- Params: `api_key`, `startDate`, `endDate`, `timeUnit` (e.g. DAY, WEEK, MONTH)

### 5) Site Energy — Time Frame
- Path: `/site/{siteId}/timeFrameEnergy`
- Method: GET
- Purpose: Energy for a requested time frame (similar to `energy` but used by some clients/tools).
- Params: `api_key`, `startDate`, `endDate`, `timeUnit`

### 6) Site Power
- Path: `/site/{siteId}/power`
- Method: GET
- Purpose: Power measurements in a 15-minute resolution for the requested timeframe.
- Params: `api_key`, `startTime`, `endTime`

### 7) Site Overview
- Path: `/site/{siteId}/overview`
- Method: GET
- Purpose: Current site power and summary metrics (today, month, lifetime energy, revenue where available).
- Params: `api_key`

### 8) Site Power Details
- Path: `/site/{siteId}/powerDetails`
- Method: GET
- Purpose: Detailed power measurements including meters such as consumption, export, import.
- Params: `api_key`, `startTime`, `endTime`, optional `meters` (comma separated)

### 9) Site Energy Details
- Path: `/site/{siteId}/energyDetails`
- Method: GET
- Purpose: Detailed energy breakdown by meter and timeframe.
- Params: `api_key`, `startTime`, `endTime`, optional `meters`, `timeUnit`

### 10) Current Power Flow
- Path: `/site/{siteId}/currentPowerFlow`
- Method: GET
- Purpose: Returns the power flow chart (who is producing/consuming/exporting) of the site.
- Params: `api_key`

### 11) Storage (battery) data
- Path: `/site/{siteId}/storageData`
- Method: GET
- Purpose: Battery state of energy (SoE), power, lifetime energy for storage devices.
- Params: `api_key`, `startTime`, `endTime`, optional `serials` (comma separated)

### 12) Site Image / Installer Logo
- Paths: `/site/{siteId}/image` and `/installer/logo` (paths vary)
- Method: GET
- Purpose: Fetch uploaded images (site image scaled/original, installer logo).
- Params: `api_key`, optional sizing/scaling parameters depending on endpoint.

### 13) Components / Inventory
- Paths: `/site/{siteId}/components`, `/site/{siteId}/inventory` (implementation-specific paths)
- Method: GET
- Purpose: Lists inverters, meters, batteries, gateways, sensors with serials and status.
- Params: `api_key`

### 14) Inverter Technical Data
- Path: `/site/{siteId}/inverterData` (or `inverter/technicalData` depending on exact API)
- Method: GET
- Purpose: Technical performance data for a given inverter for a requested period.
- Params: `api_key`, `startTime`, `endTime`, inverter identifier

### 15) Equipment Change Log
- Path: `/site/{siteId}/equipmentChangeLog`
- Method: GET
- Purpose: Replacements and changes for site components.
- Params: `api_key`

### 16) Sensors / Meters
- Paths: `/site/{siteId}/sensors`, `/site/{siteId}/sensors/data`, `/site/{siteId}/meters`
- Method: GET
- Purpose: List of sensors/meters and their measurement data.
- Params: `api_key`, `startTime`, `endTime`, optional `meters`/`sensors` list

### 17) Account List
- Path: `/accounts/list`
- Method: GET
- Purpose: Returns account-level details and sub-accounts for the provided account token.
- Params: `api_key`

### 18) API Versions
- Path: `/api/versions`
- Method: GET
- Purpose: Provides the current and supported API version numbers.
- Params: none or `api_key` depending on endpoint.

---

## Server limits and best practices

- Daily limit: 300 requests per account token. Some endpoints that are account-level (no siteId) count against this quota.
- Per-site limit: 300 requests per site ID (from same source IP) per day.
- Concurrency: the API allows up to **3 concurrent API calls** from the same source IP. Additional concurrent calls will return HTTP 429.
- Bulk: many endpoints accept multiple site IDs (comma-separated, up to 100). A bulk call consumes one quota entry for each site included.

## Throttling recommendations for clients

- Implement a simple concurrent worker pool limited to 3 concurrent requests.
- On HTTP 429, back off with exponential backoff (start with 1s, multiply by 2, jitter) and retry a small number of times.
- For bulk operations, prefer the bulk endpoint when available to reduce total calls.

## Example usage notes (client implementers)

- Always include `api_key` in params — do not send it in headers unless the API explicitly supports it.
- Use the `timeUnit` parameter where present to control aggregation (DAY/WEEK/MONTH).
- Request/response timestamps are typically strings in `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS` format; convert them to timezone-aware datetimes in your client.

## References

- This document is derived from the included project instructions and the SolarEdge Monitoring API specification (se_monitoring_api.pdf).
