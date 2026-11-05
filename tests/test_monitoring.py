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

API_KEY = "test_key"
BASE_PATH = "/v2"

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 2, tzinfo=UTC)
FROM = "2026-01-01T00:00:00+00:00"
TO = "2026-01-02T00:00:00+00:00"
RANGE = [("from", FROM), ("to", TO)]

# (method name, kwargs, expected path under /v2, expected query params in order)
ENDPOINTS: list[tuple[str, dict[str, Any], str, list[tuple[str, str]]]] = [
    ("get_sites", {}, "/sites", []),
    ("get_site_details", {"site_id": 1}, "/sites/1", []),
    ("get_site_details", {"site_id": "42"}, "/sites/42", []),
    ("get_overview", {"site_id": 1}, "/sites/1/overview", []),
    (
        "get_overview",
        {"site_id": 1, "start": START, "end": END},
        "/sites/1/overview",
        RANGE,
    ),
    (
        "get_energy",
        {"site_id": 1, "start": START, "end": END},
        "/sites/1/energy",
        [*RANGE, ("resolution", "DAY"), ("unit", "WH")],
    ),
    (
        "get_energy",
        {
            "site_id": 1,
            "start": START,
            "end": END,
            "resolution": "MONTH",
            "unit": "KWH",
        },
        "/sites/1/energy",
        [*RANGE, ("resolution", "MONTH"), ("unit", "KWH")],
    ),
    (
        "get_power",
        {"site_id": 1, "start": START, "end": END},
        "/sites/1/power",
        [*RANGE, ("resolution", "QUARTER_HOUR"), ("unit", "W")],
    ),
    ("get_lifetime_energy", {"site_id": 1}, "/sites/1/lifetime-energy", []),
    ("get_current_power_flow", {"site_id": 1}, "/sites/1/power-flow", []),
    ("get_devices", {"site_id": 1}, "/sites/1/devices", []),
    (
        "get_devices",
        {"site_id": 1, "types": ["INVERTER", "BATTERY"]},
        "/sites/1/devices",
        [("types", "INVERTER"), ("types", "BATTERY")],
    ),
    (
        "get_storage_lifetime_energy",
        {"site_id": 1, "start": START, "end": END},
        "/sites/1/storage/lifetime-energy",
        RANGE,
    ),
    (
        "get_storage_telemetry",
        {"site_id": 1, "start": START, "end": END},
        "/sites/1/storage/telemetry",
        RANGE,
    ),
    (
        "get_meters_telemetry",
        {"site_id": 1, "start": START, "end": END},
        "/sites/1/meters/telemetry",
        RANGE,
    ),
    (
        "get_inverters_telemetry",
        {"site_id": 1, "start": START, "end": END},
        "/sites/1/inverters/telemetry",
        RANGE,
    ),
    ("get", {"path": "sites/1/alerts"}, "/sites/1/alerts", []),
    (
        "get",
        {"path": "/sites/1/alerts/", "params": {"from": START, "status": None}},
        "/sites/1/alerts",
        [("from", FROM)],
    ),
    (
        "get",
        {"path": "sites/1/devices", "params": {"types": ["METER", "GATEWAY"]}},
        "/sites/1/devices",
        [("types", "METER"), ("types", "GATEWAY")],
    ),
]

IDS = [f"{name}-{i}" for i, (name, *_) in enumerate(ENDPOINTS)]


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
    expected_path: str,
    expected_params: list[tuple[str, str]],
) -> None:
    """Assert host, path, auth header and params."""
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
        with pytest.raises(SolarEdgeValidationError, match="api_key is required"):
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
    """Every endpoint builds the URL and query string the API expects."""

    @pytest.mark.parametrize(("name", "kwargs", "path", "params"), ENDPOINTS, ids=IDS)
    def test_sync_request(self, name, kwargs, path, params):
        """The sync client requests the expected URL with the expected params."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        result = getattr(client, name)(**kwargs)

        assert len(requests) == 1
        _assert_request(requests[0], path, params)
        assert result == {"ok": True}

    @pytest.mark.parametrize(("name", "kwargs", "path", "params"), ENDPOINTS, ids=IDS)
    async def test_async_request(self, name, kwargs, path, params):
        """The async client mirrors the sync client exactly."""
        requests: list[httpx.Request] = []
        client = _async_client(requests)
        result = await getattr(client, name)(**kwargs)

        assert len(requests) == 1
        _assert_request(requests[0], path, params)
        assert result == {"ok": True}

    def test_sync_and_async_expose_the_same_endpoints(self):
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

    def test_timezone_offset_is_url_encoded(self):
        """A '+' offset must be encoded, or the server reads it as a space."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        cet = timezone(timedelta(hours=1))
        client.get_energy(
            site_id=1,
            start=datetime(2026, 1, 1, tzinfo=cet),
            end=datetime(2026, 1, 2, tzinfo=cet),
        )

        raw_query = requests[0].url.query.decode()
        assert "from=2026-01-01T00%3A00%3A00%2B01%3A00" in raw_query
        assert requests[0].url.params["from"] == "2026-01-01T00:00:00+01:00"

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

    @pytest.mark.parametrize(
        "removed",
        [
            "get_site_list",
            "get_site_data",
            "get_time_frame_energy",
            "get_power_details",
            "get_energy_details",
            "get_storage_data",
            "get_environmental_benefits",
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
            ("get_energy", {"start": datetime(2026, 1, 1), "end": END}),
            ("get_power", {"start": START, "end": datetime(2026, 1, 2)}),
            ("get_overview", {"start": datetime(2026, 1, 1), "end": END}),
            ("get_storage_telemetry", {"start": datetime(2026, 1, 1), "end": END}),
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

    @pytest.mark.parametrize("kwargs", [{"start": START}, {"end": END}])
    def test_overview_requires_both_or_neither(self, kwargs):
        """A half-open overview range is ambiguous."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="both start and end"):
            client.get_overview(site_id=1, **kwargs)

    @pytest.mark.parametrize("site_id", ["1/../2", "abc", "", "-1", "\uff11", True])
    def test_malformed_site_id_rejected(self, site_id):
        """A site ID must not be able to change the request path."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        with pytest.raises(SolarEdgeValidationError, match="site_id"):
            client.get_site_details(site_id=site_id)
        assert requests == []

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

    def test_rate_limit_exposes_retry_after(self):
        """Callers can see how long the API asked them to wait."""
        client = self._client_returning(429, {}, headers={"Retry-After": "42"})
        with pytest.raises(SolarEdgeRateLimitError) as excinfo:
            client.get_site_details(site_id=1)
        assert excinfo.value.retry_after == "42"

    def test_rate_limit_without_retry_after(self):
        """retry_after is None when the header is absent."""
        client = self._client_returning(429, {})
        with pytest.raises(SolarEdgeRateLimitError) as excinfo:
            client.get_site_details(site_id=1)
        assert excinfo.value.retry_after is None

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
