"""Tests for the monitoring module."""

from typing import Any
from datetime import datetime

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
BASE = "https://monitoringapi.solaredge.com"

# Within every timeframe limit (1 week, 1 month, 1 year), so a single pair of
# dates can drive every method that validates a range.
START = datetime(2024, 1, 1)
END = datetime(2024, 1, 5)

DATE_START = "2024-01-01"
DATE_END = "2024-01-05"
TIME_START = "2024-01-01 00:00:00"
TIME_END = "2024-01-05 00:00:00"

# (method name, kwargs, expected path, expected query params minus api_key)
ENDPOINTS: list[tuple[str, dict[str, Any], str, dict[str, str]]] = [
    (
        "get_site_list",
        {},
        "/sites/list",
        {
            "size": "100",
            "startIndex": "0",
            "sortOrder": "ASC",
            "status": "Active,Pending",
        },
    ),
    (
        "get_site_list",
        {"search_text": "farm", "sort_property": "Name", "status": "All"},
        "/sites/list",
        {
            "size": "100",
            "startIndex": "0",
            "sortOrder": "ASC",
            "status": "All",
            "searchText": "farm",
            "sortProperty": "Name",
        },
    ),
    ("get_site_details", {"site_id": 1}, "/site/1/details", {}),
    ("get_site_data", {"site_ids": [1, 2]}, "/site/1,2/dataPeriod", {}),
    (
        "get_energy",
        {"site_ids": [1, 2], "start_date": START, "end_date": END},
        "/site/1,2/energy",
        {"startDate": DATE_START, "endDate": DATE_END, "timeUnit": "DAY"},
    ),
    (
        "get_time_frame_energy",
        {"site_ids": [1], "start_date": START, "end_date": END},
        "/site/1/timeFrameEnergy",
        {"startDate": DATE_START, "endDate": DATE_END, "timeUnit": "DAY"},
    ),
    (
        "get_power",
        {"site_id": 1, "start_time": START, "end_time": END},
        "/site/1/power",
        {"startTime": TIME_START, "endTime": TIME_END},
    ),
    ("get_overview", {"site_ids": [1, 2]}, "/site/1,2/overview", {}),
    (
        "get_power_details",
        {"site_id": 1, "start_time": START, "end_time": END},
        "/site/1/powerDetails",
        {"startTime": TIME_START, "endTime": TIME_END},
    ),
    (
        "get_power_details",
        {
            "site_id": 1,
            "start_time": START,
            "end_time": END,
            "meters": ["Production", "Consumption"],
        },
        "/site/1/powerDetails",
        {
            "startTime": TIME_START,
            "endTime": TIME_END,
            "meters": "Production,Consumption",
        },
    ),
    (
        "get_energy_details",
        {"site_id": 1, "start_time": START, "end_time": END},
        "/site/1/energyDetails",
        {"startTime": TIME_START, "endTime": TIME_END, "timeUnit": "DAY"},
    ),
    ("get_current_power_flow", {"site_id": 1}, "/site/1/currentPowerFlow", {}),
    (
        "get_storage_data",
        {"site_id": 1, "start_time": START, "end_time": END},
        "/site/1/storageData",
        {"startTime": TIME_START, "endTime": TIME_END},
    ),
    (
        "get_storage_data",
        {"site_id": 1, "start_time": START, "end_time": END, "serials": ["A", "B"]},
        "/site/1/storageData",
        {"startTime": TIME_START, "endTime": TIME_END, "serials": "A,B"},
    ),
    (
        "get_environmental_benefits",
        {"site_id": 1},
        "/site/1/envBenefits",
        {},
    ),
    (
        "get_environmental_benefits",
        {"site_id": 1, "system_units": "Imperial"},
        "/site/1/envBenefits",
        {"systemUnits": "Imperial"},
    ),
    ("get_components_list", {"site_id": 1}, "/equipment/1/list", {}),
    ("get_inventory", {"site_id": 1}, "/site/1/inventory", {}),
    (
        "get_inverter_technical_data",
        {"site_id": 1, "serial_number": "SN1", "start_time": START, "end_time": END},
        "/site/1/inverter/SN1/data",
        {"startTime": TIME_START, "endTime": TIME_END},
    ),
    (
        "get_meters",
        {"site_id": 1, "start_time": START, "end_time": END},
        "/site/1/meters",
        {"startTime": TIME_START, "endTime": TIME_END, "timeUnit": "DAY"},
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
    request: httpx.Request, expected_path: str, expected_params: dict[str, str]
) -> None:
    """Assert URL, params and the absence of empty query values."""
    assert request.url.path == expected_path
    assert request.url.params["api_key"] == API_KEY

    actual = {k: v for k, v in request.url.params.items() if k != "api_key"}
    assert actual == expected_params

    # Unset optional params must be omitted, not sent as `key=`.
    assert not [k for k, v in request.url.params.items() if v == ""]


class TestClientLifecycle:
    """Construction and resource-ownership semantics."""

    def test_init(self):
        """Client can be instantiated and closed."""
        client = MonitoringClient(api_key=API_KEY)
        assert client is not None
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
        assert str(requests[0].url).startswith(
            "https://example.test/api/site/1/details"
        )

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


class TestTimeframeValidation:
    """Timeframe limits produce readable errors."""

    def test_end_before_start(self):
        """An inverted range is rejected."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(ValueError, match=r"End date must be after start date\."):
            client._validate_timeframe("DAY", END, START)

    @pytest.mark.parametrize(
        ("time_unit", "end", "expected"),
        [
            (
                "_ONE_WEEK_MAX",
                datetime(2024, 2, 1),
                "The maximum date range is 1 week (7 days).",
            ),
            (
                "HOUR",
                datetime(2024, 3, 1),
                "For time_unit HOUR, the maximum date range is 1 month (31 days).",
            ),
            (
                "QUARTER_OF_AN_HOUR",
                datetime(2024, 3, 1),
                "For time_unit QUARTER_OF_AN_HOUR, "
                "the maximum date range is 1 month (31 days).",
            ),
            (
                "DAY",
                datetime(2026, 1, 1),
                "For time_unit DAY, the maximum date range is 1 year (365 days).",
            ),
        ],
    )
    def test_range_limits(self, time_unit, end, expected):
        """Exceeding a limit raises ValueError with a plain-string message."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(ValueError) as excinfo:
            client._validate_timeframe(time_unit, START, end)

        # A tuple-wrapped message would render as "('...', '...')".
        assert str(excinfo.value) == expected

    def test_endpoint_propagates_validation_error(self):
        """Validation runs before any request is made."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        with pytest.raises(ValueError):
            client.get_storage_data(
                site_id=1, start_time=START, end_time=datetime(2024, 2, 1)
            )
        assert requests == []


class TestSiteLimits:
    """Documented request-size limits."""

    def test_site_data_rejects_more_than_100_sites(self):
        """get_site_data enforces the 100-site cap."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(ValueError, match="more than 100 sites"):
            client.get_site_data(site_ids=list(range(101)))


class TestErrorTranslation:
    """API failures surface as library-owned exceptions, never httpx ones."""

    @staticmethod
    def _client_returning(status: int, body=None, text: str | None = None):
        def handler(request: httpx.Request) -> httpx.Response:
            if text is not None:
                return httpx.Response(status, text=text)
            return httpx.Response(status, json=body if body is not None else {})

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
            (429, SolarEdgeRateLimitError),
            (500, SolarEdgeServerError),
            (503, SolarEdgeServerError),
        ],
    )
    def test_status_maps_to_exception_type(self, status, expected):
        """Each error status raises its most specific exception class."""
        client = self._client_returning(status, {"String": "nope"})
        with pytest.raises(expected) as excinfo:
            client.get_site_details(site_id=1)

        assert excinfo.value.status_code == status
        assert excinfo.value.response_body == {"String": "nope"}

    def test_every_api_error_is_a_solaredge_error(self):
        """Callers can catch the base class alone."""
        client = self._client_returning(500)
        with pytest.raises(SolarEdgeAPIError):
            client.get_site_details(site_id=1)

    def test_api_key_is_redacted_from_the_message(self):
        """A traceback must never expose a live API key."""
        client = self._client_returning(403, {"String": "Invalid token"})
        with pytest.raises(SolarEdgeAuthError) as excinfo:
            client.get_site_details(site_id=1)

        assert "SECRET" not in str(excinfo.value)
        assert "SECRET" not in (excinfo.value.url or "")
        assert "api_key=REDACTED" in str(excinfo.value)

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
            return httpx.Response(429, json={"String": "slow down"})

        client = AsyncMonitoringClient(
            "SECRET",
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        with pytest.raises(SolarEdgeRateLimitError) as excinfo:
            await client.get_site_details(site_id=1)
        assert excinfo.value.status_code == 429


class TestValidation:
    """Argument limits are enforced locally and consistently."""

    def test_validation_error_is_still_a_value_error(self):
        """Existing `except ValueError` handlers keep working."""
        assert issubclass(SolarEdgeValidationError, ValueError)

    @pytest.mark.parametrize(
        "method",
        ["get_site_data", "get_overview"],
    )
    def test_empty_site_ids_rejected(self, method):
        """An empty list would build a malformed `site//...` path."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="At least one site ID"):
            getattr(client, method)(site_ids=[])

    @pytest.mark.parametrize(
        "method",
        ["get_site_data", "get_overview"],
    )
    def test_site_cap_enforced_consistently(self, method):
        """Every site_ids endpoint enforces the cap, not just get_site_data."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="more than 100"):
            getattr(client, method)(site_ids=list(range(101)))

    def test_energy_enforces_site_cap(self):
        """The cap applies to the dated endpoints as well."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="more than 100"):
            client.get_energy(site_ids=list(range(101)), start_date=START, end_date=END)

    def test_site_list_size_validated(self):
        """get_site_list documented a max of 100 but never enforced it."""
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="size cannot exceed"):
            client.get_site_list(size=500)

    def test_partial_day_over_limit_is_rejected(self):
        """A 7.5-day range exceeds the one-week ceiling.

        The previous whole-day truncation let this through.
        """
        client = MonitoringClient(API_KEY)
        with pytest.raises(SolarEdgeValidationError, match="1 week"):
            client.get_storage_data(
                site_id=1,
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 8, 12),
            )

    def test_exactly_at_limit_is_allowed(self):
        """The boundary itself stays valid."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests)
        client.get_storage_data(
            site_id=1,
            start_time=datetime(2024, 1, 1),
            end_time=datetime(2024, 1, 8),
        )
        assert len(requests) == 1
