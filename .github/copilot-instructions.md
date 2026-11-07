# Copilot instructions

This repository is a Python client for SolarEdge's **Monitoring API V2**
(`https://monitoringapi.solaredge.com/v2`). V1 was retired on 2026-11-03; do
not suggest V1 paths (`/site/{id}/...`), the `api_key` query parameter, or
V1 parameter names such as `startTime` or `timeUnit`.

- **Layout:**
  - `src/solaredge/_endpoints.py` holds pure request builders.
  - `src/solaredge/_operations.py` defines every public method once.
  - `src/solaredge/monitoring.py` supplies the sync and async transports.
  - `src/solaredge/oauth.py` implements Site Access (OAuth 2.0), and
    `src/solaredge/__main__.py` the `python -m solaredge login` helper.
- **New operations:** add a builder to `_endpoints.py` and a method to
  `Operations`. Then add a row to `ENDPOINTS` in `tests/test_monitoring.py`
  and, if it is a new operation, to `SPEC_OPERATIONS`.
- **Requests:**
  - Authenticate with the `X-API-Key` header (Fleet Access) or a bearer
    token (Site Access, which homeowners must use).
  - Datetimes must be timezone-aware and are sent as UTC (`...Z`).
- **Errors:** raise `SolarEdgeError` subclasses, never `httpx` exceptions.
- **Endpoint reference:** see `docs/SE_monitoring_API.md`.
- **Tooling:** the project uses uv only. Docs and examples use `uv add` and
  `uv run`, never pip or poetry.
