"""Tests for the monitoring module."""

from typing import Any
from datetime import datetime, timezone, timedelta

import httpx
import pytest

from solaredge import (
    MonitoringClient,
    SolarEdgeAPIError,
    SolarEdgeAuthError,
    SolarEdgeServerError,
    AsyncMonitoringClient,
    SolarEdgeNotFoundError,
    SolarEdgeResponseError,
    SolarEdgeRateLimitError,
    SolarEdgeValidationError,
)
from solaredge.exceptions import error_from_response

API_KEY = "test_key"
BASE_PATH = "/v2"

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 2, tzinfo=UTC)
FROM = "2026-01-01T00:00:00Z"
TO = "2026-01-02T00:00:00Z"
RANGE = [("from", FROM), ("to", TO)]
WIN = {"start": START, "end": END}
SN = "7E1234AB-01"

Params = list[tuple[str, str]]


def _measurement(
    method: str, family: str, metric: str, unit: str | None
) -> list[tuple[str, dict[str, Any], str, str, Params]]:
    """Cases for a per-device measurement: defaults, then every argument."""
    base = {"site_id": 1, "serial_number": SN}
    full = {**base, **WIN, "resolution": "HOUR"}
    full_params = [*RANGE, ("resolution", "HOUR")]
    if unit is not None:
        full["unit"] = unit
        full_params.append(("unit", unit))
    path = f"/sites/1/{family}/{SN}/{metric}"
    return [
        (method, base, "GET", path, []),
        (method, full, "GET", path, full_params),
    ]


# (method, kwargs, HTTP method, path under /v2, query params in order).
# Together these cover every operation in SolarEdge's Basic Monitoring API
# 2.1.0 (50) and Advanced Monitoring API 2.0.1 (6) specifications.
ENDPOINTS: list[tuple[str, dict[str, Any], str, str, Params]] = [
    # --- sites
    ("get_sites", {}, "GET", "/sites", []),
    (
        "get_sites",
        {
            "page": 2,
            "sites_in_page": 1000,
            "name": "farm",
            "group": "g-1",
            "state": "CA",
            "city": "Fresno",
        },
        "GET",
        "/sites",
        [
            ("page", "2"),
            ("sites-in-page", "1000"),
            ("name", "farm"),
            ("group", "g-1"),
            ("state", "CA"),
            ("city", "Fresno"),
        ],
    ),
    ("get_site_details", {"site_id": 1}, "GET", "/sites/1", []),
    ("get_site_details", {"site_id": "42"}, "GET", "/sites/42", []),
    ("get_overview", {"site_id": 1}, "GET", "/sites/1/overview", []),
    ("get_overview", {"site_id": 1, **WIN}, "GET", "/sites/1/overview", RANGE),
    (
        "get_overview",
        {"site_id": 1, "start": START},
        "GET",
        "/sites/1/overview",
        [("from", FROM)],
    ),
    ("get_performance", {"site_id": 1}, "GET", "/sites/1/overview/performance", []),
    (
        "get_performance",
        {"site_id": 1, **WIN},
        "GET",
        "/sites/1/overview/performance",
        RANGE,
    ),
    ("get_power", {"site_id": 1}, "GET", "/sites/1/power", []),
    (
        "get_power",
        {"site_id": 1, **WIN, "resolution": "HOUR", "unit": "KW"},
        "GET",
        "/sites/1/power",
        [*RANGE, ("resolution", "HOUR"), ("unit", "KW")],
    ),
    ("get_energy", {"site_id": 1}, "GET", "/sites/1/energy", []),
    (
        "get_energy",
        {"site_id": 1, **WIN, "resolution": "TOTAL", "unit": "KWH"},
        "GET",
        "/sites/1/energy",
        [*RANGE, ("resolution", "TOTAL"), ("unit", "KWH")],
    ),
    (
        "get_environmental_benefits",
        {"site_id": 1},
        "GET",
        "/sites/1/environmental-benefits",
        [],
    ),
    (
        "get_environmental_benefits",
        {"site_id": 1, "unit": "IMPERIAL"},
        "GET",
        "/sites/1/environmental-benefits",
        [("unit", "IMPERIAL")],
    ),
    ("get_lifetime_energy", {"site_id": 1}, "GET", "/sites/1/lifetime-energy", []),
    (
        "get_external_production_energy",
        {"site_id": 1},
        "GET",
        "/sites/1/external-production-energy",
        [],
    ),
    # --- alerts
    ("get_alerts", {}, "GET", "/alerts", []),
    (
        "get_alerts",
        {
            "page": 3,
            "alerts_in_page": 100,
            "group": "g-1",
            "alert_type": "COMMUNICATION",
            "state": "CA",
            "city": "Fresno",
            "only_open": False,
        },
        "GET",
        "/alerts",
        [
            ("page", "3"),
            ("alerts-in-page", "100"),
            ("group", "g-1"),
            ("type", "COMMUNICATION"),
            ("state", "CA"),
            ("city", "Fresno"),
            ("only-open", "false"),
        ],
    ),
    ("get_site_alerts", {"site_id": 1}, "GET", "/sites/1/alerts", []),
    (
        "get_site_alerts",
        {"site_id": 1, "page": 1, "alerts_in_page": 10, "only_open": True},
        "GET",
        "/sites/1/alerts",
        [("page", "1"), ("alerts-in-page", "10"), ("only-open", "true")],
    ),
    # --- inventory
    ("get_devices", {"site_id": 1}, "GET", "/sites/1/devices", []),
    (
        "get_devices",
        {"site_id": 1, "types": ["INVERTER", "BATTERY"]},
        "GET",
        "/sites/1/devices",
        [("types", "INVERTER"), ("types", "BATTERY")],
    ),
    (
        "get_devices",
        {"site_id": 1, "types": "METER"},
        "GET",
        "/sites/1/devices",
        [("types", "METER")],
    ),
    (
        "get_device",
        {"site_id": 1, "serial_number": SN},
        "GET",
        f"/sites/1/devices/{SN}",
        [],
    ),
    # --- bulk telemetry, site-wide and per device
    (
        "get_inverters_telemetry",
        {"site_id": 1},
        "GET",
        "/sites/1/inverters/telemetry",
        [],
    ),
    (
        "get_inverters_telemetry",
        {"site_id": 1, **WIN, "resolution": "DAY", "serial_numbers": [SN, "B-2"]},
        "GET",
        f"/sites/1/inverters/{SN},B-2/telemetry",
        [*RANGE, ("resolution", "DAY")],
    ),
    ("get_meters_telemetry", {"site_id": 1}, "GET", "/sites/1/meters/telemetry", []),
    (
        "get_meters_telemetry",
        {"site_id": 1, "serial_numbers": [SN]},
        "GET",
        f"/sites/1/meters/{SN}/telemetry",
        [],
    ),
    ("get_storage_telemetry", {"site_id": 1}, "GET", "/sites/1/storage/telemetry", []),
    (
        "get_storage_telemetry",
        {"site_id": 1, **WIN, "serial_numbers": SN},
        "GET",
        f"/sites/1/storage/{SN}/telemetry",
        RANGE,
    ),
    (
        "get_ev_chargers_telemetry",
        {"site_id": 1},
        "GET",
        "/sites/1/ev-chargers/telemetry",
        [],
    ),
    (
        "get_ev_chargers_telemetry",
        {"site_id": 1, **WIN, "resolution": "TOTAL", "serial_numbers": [SN, "B-2"]},
        "GET",
        f"/sites/1/ev-chargers/{SN},B-2/telemetry",
        [*RANGE, ("resolution", "TOTAL")],
    ),
    ("get_sensors_telemetry", {"site_id": 1}, "GET", "/sites/1/sensors/telemetry", []),
    (
        "get_sensors_telemetry",
        {"site_id": 1, **WIN, "resolution": "MONTH"},
        "GET",
        "/sites/1/sensors/telemetry",
        [*RANGE, ("resolution", "MONTH")],
    ),
    # --- status
    ("get_inverters_status", {"site_id": 1}, "GET", "/sites/1/inverters/status", []),
    (
        "get_inverters_status",
        {"site_id": 1, **WIN, "resolution": "HOUR", "serial_numbers": [SN]},
        "GET",
        f"/sites/1/inverters/{SN}/status",
        [*RANGE, ("resolution", "HOUR")],
    ),
    ("get_storage_status", {"site_id": 1}, "GET", "/sites/1/storage/status", []),
    (
        "get_storage_status",
        {"site_id": 1, "serial_numbers": [SN]},
        "GET",
        f"/sites/1/storage/{SN}/status",
        [],
    ),
    # --- lifetime energy counters
    (
        "get_inverters_lifetime_energy",
        {"site_id": 1, **WIN},
        "GET",
        "/sites/1/inverters/lifetime-energy",
        RANGE,
    ),
    (
        "get_inverters_lifetime_energy",
        {"site_id": 1, **WIN, "serial_number": SN},
        "GET",
        f"/sites/1/inverters/{SN}/lifetime-energy",
        RANGE,
    ),
    (
        "get_meters_lifetime_energy",
        {"site_id": 1, **WIN},
        "GET",
        "/sites/1/meters/lifetime-energy",
        RANGE,
    ),
    (
        "get_meters_lifetime_energy",
        {
            "site_id": 1,
            **WIN,
            "serial_numbers": [SN],
            "meters": ["PRODUCTION", "PURCHASED"],
        },
        "GET",
        f"/sites/1/meters/{SN}/lifetime-energy",
        [*RANGE, ("meters", "PRODUCTION,PURCHASED")],
    ),
    (
        "get_storage_lifetime_energy",
        {"site_id": 1, **WIN},
        "GET",
        "/sites/1/storage/lifetime-energy",
        RANGE,
    ),
    (
        "get_storage_lifetime_energy",
        {"site_id": 1, **WIN, "serial_numbers": [SN]},
        "GET",
        f"/sites/1/storage/{SN}/lifetime-energy",
        RANGE,
    ),
    # --- per-device measurements
    *_measurement("get_inverter_power", "inverters", "power", "KW"),
    *_measurement("get_inverter_energy", "inverters", "energy", "KWH"),
    *_measurement(
        "get_inverter_consumed_ac_power", "inverters", "consumed-ac-power", "W"
    ),
    *_measurement(
        "get_inverter_consumed_ac_energy", "inverters", "consumed-ac-energy", "WH"
    ),
    *_measurement("get_inverter_voltage", "inverters", "voltage", None),
    *_measurement("get_inverter_current", "inverters", "current", None),
    *_measurement("get_inverter_frequency", "inverters", "frequency", None),
    *_measurement("get_meter_production_power", "meters", "production-power", "W"),
    *_measurement("get_meter_production_energy", "meters", "production-energy", "WH"),
    *_measurement("get_meter_consumption_power", "meters", "consumption-power", "W"),
    *_measurement("get_meter_consumption_energy", "meters", "consumption-energy", "WH"),
    *_measurement("get_meter_import_power", "meters", "import-power", "W"),
    *_measurement("get_meter_import_energy", "meters", "import-energy", "WH"),
    *_measurement("get_meter_export_power", "meters", "export-power", "W"),
    *_measurement("get_meter_export_energy", "meters", "export-energy", "WH"),
    *_measurement("get_battery_charge_power", "storage", "charge-power", "W"),
    *_measurement("get_battery_discharge_power", "storage", "discharge-power", "W"),
    *_measurement("get_battery_charge_energy", "storage", "charge-energy", "WH"),
    *_measurement("get_battery_discharge_energy", "storage", "discharge-energy", "WH"),
    *_measurement(
        "get_battery_state_of_energy", "storage", "state-of-energy", "PERCENTAGE"
    ),
    *_measurement("get_battery_remaining_energy", "storage", "remaining-energy", "WH"),
    # --- Advanced Monitoring
    (
        "get_power_per_destination",
        {"site_id": 1},
        "GET",
        "/sites/1/power/per-destination",
        [],
    ),
    (
        "get_power_per_destination",
        {"site_id": 1, **WIN, "resolution": "HOUR"},
        "GET",
        "/sites/1/power/per-destination",
        [*RANGE, ("resolution", "HOUR")],
    ),
    (
        "get_energy_per_destination",
        {"site_id": 1, **WIN, "resolution": "MONTH"},
        "GET",
        "/sites/1/energy/per-destination",
        [*RANGE, ("resolution", "MONTH")],
    ),
    ("get_current_power_flow", {"site_id": 1}, "GET", "/sites/1/power-flow", []),
    ("start_live_power_flow", {"site_id": 1}, "POST", "/sites/1/power-flow", []),
    ("get_weather_guard", {"site_id": 1}, "GET", "/sites/1/weather-guard", []),
    ("get_backup_reserve", {"site_id": 1}, "GET", "/sites/1/backup-reserve", []),
    # --- escape hatch
    ("get", {"path": "sites/1/alerts"}, "GET", "/sites/1/alerts", []),
    (
        "get",
        {"path": "/sites/1/alerts/", "params": {"from": START, "status": None}},
        "GET",
        "/sites/1/alerts",
        [("from", FROM)],
    ),
    (
        "get",
        {"path": "sites/1/devices", "params": {"types": ["METER", "GATEWAY"]}},
        "GET",
        "/sites/1/devices",
        [("types", "METER"), ("types", "GATEWAY")],
    ),
]

IDS = [f"{name}-{i}" for i, (name, *_) in enumerate(ENDPOINTS)]

# One (HTTP method, path template) per operation in the two specifications.
SPEC_OPERATIONS = {
    ("GET", "/sites"),
    ("GET", "/sites/{id}"),
    ("GET", "/sites/{id}/overview"),
    ("GET", "/sites/{id}/overview/performance"),
    ("GET", "/sites/{id}/power"),
    ("GET", "/sites/{id}/energy"),
    ("GET", "/sites/{id}/environmental-benefits"),
    ("GET", "/sites/{id}/lifetime-energy"),
    ("GET", "/sites/{id}/external-production-energy"),
    ("GET", "/alerts"),
    ("GET", "/sites/{id}/alerts"),
    ("GET", "/sites/{id}/devices"),
    ("GET", "/sites/{id}/devices/{sn}"),
    ("GET", "/sites/{id}/ev-chargers/telemetry"),
    ("GET", "/sites/{id}/ev-chargers/{sn}/telemetry"),
    ("GET", "/sites/{id}/sensors/telemetry"),
    *(
        ("GET", f"/sites/{{id}}/{family}{sn}/{kind}")
        for family in ("inverters", "meters", "storage")
        for kind in ("telemetry", "lifetime-energy")
        for sn in ("", "/{sn}")
    ),
    *(
        ("GET", f"/sites/{{id}}/{family}{sn}/status")
        for family in ("inverters", "storage")
        for sn in ("", "/{sn}")
    ),
    *(
        ("GET", f"/sites/{{id}}/inverters/{{sn}}/{metric}")
        for metric in (
            "power",
            "energy",
            "consumed-ac-power",
            "consumed-ac-energy",
            "voltage",
            "current",
            "frequency",
        )
    ),
    *(
        ("GET", f"/sites/{{id}}/meters/{{sn}}/{direction}-{kind}")
        for direction in ("production", "consumption", "import", "export")
        for kind in ("power", "energy")
    ),
    *(
        ("GET", f"/sites/{{id}}/storage/{{sn}}/{metric}")
        for metric in (
            "charge-power",
            "discharge-power",
            "charge-energy",
            "discharge-energy",
            "state-of-energy",
            "remaining-energy",
        )
    ),
    ("GET", "/sites/{id}/power/per-destination"),
    ("GET", "/sites/{id}/energy/per-destination"),
    ("GET", "/sites/{id}/power-flow"),
    ("POST", "/sites/{id}/power-flow"),
    ("GET", "/sites/{id}/weather-guard"),
    ("GET", "/sites/{id}/backup-reserve"),
}


def _template(path: str) -> str:
    """Turn a concrete test path back into its spec template."""
    parts = path.split("/")
    if len(parts) > 2 and parts[1] == "sites":
        parts[2] = "{id}"
    if len(parts) > 4 and parts[3] in (
        "inverters",
        "meters",
        "storage",
        "devices",
        "ev-chargers",
        "sensors",
    ):
        if parts[4] not in ("telemetry", "status", "lifetime-energy"):
            parts[4] = "{sn}"
    return "/".join(parts)


def _recording_transport(
    requests: list[httpx.Request],
    content: bytes | None = None,
) -> httpx.MockTransport:
    """Build a transport that records requests and returns a canned response."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if content is not None:
            return httpx.Response(200, content=content)
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(handler)


def _sync_client(requests: list[httpx.Request], content: bytes | None = None):
    return MonitoringClient(
        API_KEY, client=httpx.Client(transport=_recording_transport(requests, content))
    )


def _async_client(requests: list[httpx.Request], content: bytes | None = None):
    return AsyncMonitoringClient(
        API_KEY,
        client=httpx.AsyncClient(transport=_recording_transport(requests, content)),
    )


def _assert_request(
    request: httpx.Request,
    expected_method: str,
    expected_path: str,
    expected_params: Params,
) -> None:
    """Assert method, host, path, auth header and params."""
    assert request.method == expected_method
    assert request.url.host == "monitoringapi.solaredge.com"
    assert request.url.path == BASE_PATH + expected_path
    assert request.headers["X-API-Key"] == API_KEY
    assert list(request.url.params.multi_items()) == expected_params

    # The key must never travel in the URL, as V1's api_key param did.
    assert API_KEY not in str(request.url)
    assert "api_key" not in request.url.params


class TestClientLifecycle:
    """Construction and resource-ownership semantics."""

    def test_init(self):
        """Client can be instantiated and closed."""
        client = MonitoringClient(api_key=API_KEY)
        assert client is not None
        client.close()

    def test_empty_api_key_rejected(self):
        """A missing key fails locally instead of as a 401 later."""
        with pytest.raises(SolarEdgeValidationError, match="exactly one of"):
            MonitoringClient(api_key="")

    def test_repr_hides_api_key(self):
        """Logging a client must not leak the key."""
        client = MonitoringClient(api_key="SECRET")
        assert "SECRET" not in repr(client)
        client.close()

    def test_context_manager_closes_owned_client(self):
        """An internally-created httpx.Client is closed on exit."""
        with MonitoringClient(api_key=API_KEY) as client:
            assert client is not None
        assert client.client.is_closed

    def test_context_manager_leaves_external_client_open(self):
        """An externally-provided httpx.Client is not closed on exit."""
        external = httpx.Client()
        with MonitoringClient(api_key=API_KEY, client=external):
            pass
        assert not external.is_closed
        external.close()

    def test_close_leaves_external_client_open(self):
        """close() is a no-op for a client it does not own, matching __exit__."""
        external = httpx.Client()
        client = MonitoringClient(api_key=API_KEY, client=external)
        client.close()
        assert not external.is_closed
        external.close()

    def test_timeout_is_applied(self):
        """The timeout reaches the internally-created httpx client."""
        client = MonitoringClient(api_key=API_KEY, timeout=3)
        assert client.client.timeout.read == 3
        client.close()

    def test_base_url_override_and_trailing_slash(self):
        """A custom base_url is used, with any trailing slash stripped."""
        requests: list[httpx.Request] = []
        client = MonitoringClient(
            API_KEY,
            base_url="https://example.test/api/",
            client=httpx.Client(transport=_recording_transport(requests)),
        )
        client.get_site_details(site_id=1)
        assert str(requests[0].url) == "https://example.test/api/sites/1"

    async def test_async_context_manager_closes_owned_client(self):
        """The async client closes an httpx.AsyncClient it created."""
        async with AsyncMonitoringClient(api_key=API_KEY) as client:
            assert client is not None
        assert client.client.is_closed

    async def test_aclose_leaves_external_client_open(self):
        """aclose() is a no-op for a client it does not own, matching __aexit__."""
        external = httpx.AsyncClient()
        client = AsyncMonitoringClient(api_key=API_KEY, client=external)
        await client.aclose()
        assert not external.is_closed
        await external.aclose()


class TestEndpoints:
    """Every operation builds the request the specification describes."""

    @pytest.mark.parametrize(
        ("name", "kwargs", "method", "path", "params"), ENDPOINTS, ids=IDS
    )
    def test_sync_request(self, name, kwargs, method, path, params):
        """The sync client sends the expected method, URL and params."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        result = getattr(client, name)(**kwargs)

        assert len(requests) == 1
        _assert_request(requests[0], method, path, params)
        assert result == {"ok": True}

    @pytest.mark.parametrize(
        ("name", "kwargs", "method", "path", "params"), ENDPOINTS, ids=IDS
    )
    async def test_async_request(self, name, kwargs, method, path, params):
        """The async client mirrors the sync client exactly."""
        requests: list[httpx.Request] = []
        client = _async_client(requests)
        result = await getattr(client, name)(**kwargs)

        assert len(requests) == 1
        _assert_request(requests[0], method, path, params)
        assert result == {"ok": True}

    def test_every_spec_operation_is_covered(self):
        """Each of the 59 documented operations has a tested method."""
        assert len(SPEC_OPERATIONS) == 59
        tested = {
            (method, _template(path))
            for name, _, method, path, _ in ENDPOINTS
            if name != "get"
        }
        assert tested == SPEC_OPERATIONS

    def test_every_public_method_is_tested(self):
        """No operation method exists without a request test."""
        public = {
            n
            for n in dir(MonitoringClient)
            if n.startswith(("get", "start_"))
            and callable(getattr(MonitoringClient, n))
        }
        assert public == {name for name, *_ in ENDPOINTS}

    def test_sync_and_async_expose_the_same_methods(self):
        """The two clients must not drift apart in API surface."""
        public = lambda c: {  # noqa: E731
            n for n in dir(c) if not n.startswith("_") and callable(getattr(c, n))
        }
        sync_only = public(MonitoringClient) - public(AsyncMonitoringClient) - {"close"}
        async_only = (
            public(AsyncMonitoringClient) - public(MonitoringClient) - {"aclose"}
        )
        assert not sync_only
        assert not async_only

    def test_non_utc_datetimes_are_sent_as_utc(self):
        """Offsets are normalised to a UTC instant with a Z suffix."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        cet = timezone(timedelta(hours=1))
        client.get_energy(
            site_id=1,
            start=datetime(2026, 1, 1, 1, 0, tzinfo=cet),
            end=datetime(2026, 1, 2, 1, 0, tzinfo=cet),
        )
        assert requests[0].url.params["from"] == FROM
        assert requests[0].url.params["to"] == TO

    def test_microseconds_are_dropped(self):
        """Timestamps are sent at second precision."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        client.get_power(
            site_id=1,
            start=datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC),
            end=END,
        )
        assert requests[0].url.params["from"] == FROM

    def test_empty_success_body_returns_none(self):
        """A 200 with no body (e.g. starting live power flow) is not an error."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests, content=b"")
        assert client.start_live_power_flow(site_id=1) is None

    @pytest.mark.parametrize(
        "removed",
        [
            "get_site_list",
            "get_site_data",
            "get_time_frame_energy",
            "get_power_details",
            "get_energy_details",
            "get_storage_data",
            "get_components_list",
            "get_inventory",
            "get_inverter_technical_data",
            "get_meters",
        ],
    )
    def test_v1_only_methods_are_gone(self, removed):
        """V1 methods with no V2 equivalent fail loudly, not with a 410."""
        assert not hasattr(MonitoringClient, removed)
        assert not hasattr(AsyncMonitoringClient, removed)


class TestValidation:
    """Arguments are checked locally, before anything is sent."""

    def test_validation_error_is_still_a_value_error(self):
        """Existing `except ValueError` handlers keep working."""
        assert issubclass(SolarEdgeValidationError, ValueError)

    @pytest.mark.parametrize(
        ("method", "kwargs"),
        [
            ("get_energy", {"start": datetime(2026, 1, 1)}),
            ("get_power", {"end": datetime(2026, 1, 2)}),
            ("get_overview", {"start": datetime(2026, 1, 1)}),
            ("get_storage_telemetry", {"start": datetime(2026, 1, 1)}),
            (
                "get_storage_lifetime_energy",
                {"start": datetime(2026, 1, 1), "end": END},
            ),
        ],
    )
    def test_naive_datetime_rejected(self, method, kwargs):
        """V2 rejects timestamps without an offset, so refuse them up front."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        with pytest.raises(SolarEdgeValidationError, match="timezone-aware"):
            getattr(client, method)(site_id=1, **kwargs)
        assert requests == []

    def test_naive_datetime_rejected_in_generic_get(self):
        """get() applies the same timestamp rule as the dedicated methods."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        with pytest.raises(SolarEdgeValidationError, match="from must be"):
            client.get("sites/1/alerts", {"from": datetime(2026, 1, 1)})
        assert requests == []

    def test_inverted_range_rejected(self):
        """End before start is caught locally."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        with pytest.raises(SolarEdgeValidationError, match="end must not be before"):
            client.get_energy(site_id=1, start=END, end=START)
        assert requests == []

    @pytest.mark.parametrize(
        "method",
        [
            "get_inverters_lifetime_energy",
            "get_meters_lifetime_energy",
            "get_storage_lifetime_energy",
        ],
    )
    def test_lifetime_energy_requires_window(self, method):
        """The spec marks from/to as required on the lifetime-energy endpoints."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="both required"):
            getattr(client, method)(site_id=1, start=START, end=None)

    @pytest.mark.parametrize("site_id", ["1/../2", "abc", "", "-1", "\uff11", True])
    def test_malformed_site_id_rejected(self, site_id):
        """A site ID must not be able to change the request path."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        with pytest.raises(SolarEdgeValidationError, match="site_id"):
            client.get_site_details(site_id=site_id)
        assert requests == []

    @pytest.mark.parametrize("serial", ["", "..", "a/b", "a,b", "a?b", "-x", "\u00e9"])
    def test_malformed_serial_rejected(self, serial):
        """A serial number must not be able to change the request path."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        with pytest.raises(SolarEdgeValidationError, match="serial numbers"):
            client.get_device(site_id=1, serial_number=serial)
        assert requests == []

    def test_empty_serial_list_rejected(self):
        """An empty list would silently select every device instead."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="must not be empty"):
            client.get_meters_telemetry(site_id=1, serial_numbers=[])

    @pytest.mark.parametrize(
        ("method", "kwargs", "match"),
        [
            ("get_sites", {"sites_in_page": 1001}, "sites_in_page"),
            ("get_sites", {"page": 0}, "page"),
            ("get_alerts", {"alerts_in_page": 101}, "alerts_in_page"),
            ("get_site_alerts", {"site_id": 1, "alerts_in_page": 0}, "alerts_in_page"),
        ],
    )
    def test_page_bounds_enforced(self, method, kwargs, match):
        """Paging arguments outside the documented bounds are refused."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match=match):
            getattr(client, method)(**kwargs)

    @pytest.mark.parametrize("path", ["", "/", "sites/../oauth2/token"])
    def test_generic_get_rejects_bad_paths(self, path):
        """get() refuses empty paths and parent-directory segments."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="Invalid API path"):
            client.get(path)


class TestErrorTranslation:
    """API failures surface as library-owned exceptions, never httpx ones."""

    @staticmethod
    def _client_returning(
        status: int, body=None, text: str | None = None, headers=None
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            if text is not None:
                return httpx.Response(status, text=text, headers=headers)
            return httpx.Response(
                status, json=body if body is not None else {}, headers=headers
            )

        return MonitoringClient(
            "SECRET", client=httpx.Client(transport=httpx.MockTransport(handler))
        )

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (400, SolarEdgeAPIError),
            (401, SolarEdgeAuthError),
            (403, SolarEdgeAuthError),
            (404, SolarEdgeNotFoundError),
            (410, SolarEdgeAPIError),
            (429, SolarEdgeRateLimitError),
            (500, SolarEdgeServerError),
            (503, SolarEdgeServerError),
        ],
    )
    def test_status_maps_to_exception_type(self, status, expected):
        """Each error status raises its most specific exception class."""
        client = self._client_returning(status, {"title": "nope"})
        with pytest.raises(expected) as excinfo:
            client.get_site_details(site_id=1)

        assert excinfo.value.status_code == status
        assert excinfo.value.response_body == {"title": "nope"}

    def test_rate_limit_exposes_retry_after_and_limits(self):
        """Callers can see how long to wait and what quota is left."""
        client = self._client_returning(
            429,
            {},
            headers={
                "Retry-After": "42",
                "x-ratelimit-limit-minute": "10",
                "x-ratelimit-remaining-minute": "0",
                "x-ratelimit-remaining-month": "not-a-number",
            },
        )
        with pytest.raises(SolarEdgeRateLimitError) as excinfo:
            client.get_site_details(site_id=1)
        assert excinfo.value.retry_after == "42"
        assert excinfo.value.limits == {
            "x-ratelimit-limit-minute": 10,
            "x-ratelimit-remaining-minute": 0,
        }

    def test_rate_limit_without_headers(self):
        """retry_after is None and limits empty when the headers are absent."""
        client = self._client_returning(429, {})
        with pytest.raises(SolarEdgeRateLimitError) as excinfo:
            client.get_site_details(site_id=1)
        assert excinfo.value.retry_after is None
        assert excinfo.value.limits == {}

    def test_api_key_never_appears_in_errors(self):
        """A traceback must never expose a live API key."""
        client = self._client_returning(403, {"title": "Forbidden"})
        with pytest.raises(SolarEdgeAuthError) as excinfo:
            client.get_site_details(site_id=1)

        assert "SECRET" not in str(excinfo.value)
        assert "SECRET" not in (excinfo.value.url or "")
        assert excinfo.value.url == "https://monitoringapi.solaredge.com/v2/sites/1"

    def test_httpx_error_is_preserved_as_cause(self):
        """The transport-level error stays reachable for callers who want it."""
        client = self._client_returning(404)
        with pytest.raises(SolarEdgeNotFoundError) as excinfo:
            client.get_site_details(site_id=1)

        assert isinstance(excinfo.value.__cause__, httpx.HTTPStatusError)

    def test_non_json_success_body_raises_response_error(self):
        """A 200 with an unparseable body is a library error, not a ValueError."""
        client = self._client_returning(200, text="<html>not json</html>")
        with pytest.raises(SolarEdgeResponseError) as excinfo:
            client.get_site_details(site_id=1)

        assert "SECRET" not in str(excinfo.value)

    async def test_async_client_translates_errors_too(self):
        """The async client raises the same types as the sync client."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429, json={"title": "slow down"}, headers={"Retry-After": "7"}
            )

        client = AsyncMonitoringClient(
            "SECRET",
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        with pytest.raises(SolarEdgeRateLimitError) as excinfo:
            await client.get_site_details(site_id=1)
        assert excinfo.value.status_code == 429
        assert excinfo.value.retry_after == "7"


def test_error_without_request_has_no_url():
    """A response that was never tied to a request still yields an error."""
    err = error_from_response(httpx.Response(500, text="boom"))
    assert isinstance(err, SolarEdgeServerError)
    assert err.url is None
    assert err.response_body == "boom"
    assert "for " not in str(err)
