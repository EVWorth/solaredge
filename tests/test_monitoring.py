"""Tests for the monitoring module."""

from typing import Any
from datetime import datetime

import httpx
import pytest

from solaredge import MonitoringClient, AsyncMonitoringClient

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

IMAGE_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

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
        "get_equipment_change_log",
        {"site_id": 1, "serial_number": "SN1"},
        "/site/1/SN1/changeLog",
        {},
    ),
    (
        "get_account_list",
        {},
        "/accounts/list",
        {"pageSize": "100", "startIndex": "0", "sortOrder": "ASC"},
    ),
    (
        "get_meters",
        {"site_id": 1, "start_time": START, "end_time": END},
        "/site/1/meters",
        {"startTime": TIME_START, "endTime": TIME_END, "timeUnit": "DAY"},
    ),
    ("get_sensor_list", {"site_id": 1}, "/equipment/1/sensors", {}),
    (
        "get_sensor_data",
        {"site_id": 1, "start_date": START, "end_date": END},
        "/equipment/1/sensors",
        {"startTime": "2024-01-01T00:00:00", "endTime": "2024-01-05T00:00:00"},
    ),
    ("get_current_api_version", {}, "/version/current", {}),
    ("get_supported_api_versions", {}, "/version/supported", {}),
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

    def test_close_refuses_external_client(self):
        """close() refuses to close a client it does not own."""
        external = httpx.Client()
        client = MonitoringClient(api_key=API_KEY, client=external)
        with pytest.raises(ValueError, match="externally provided"):
            client.close()
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

    async def test_aclose_refuses_external_client(self):
        """aclose() refuses to close a client it does not own."""
        external = httpx.AsyncClient()
        client = AsyncMonitoringClient(api_key=API_KEY, client=external)
        with pytest.raises(ValueError, match="externally provided"):
            await client.aclose()
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


class TestImageEndpoints:
    """Image endpoints return raw bytes rather than parsed JSON."""

    def test_sync_user_image_returns_bytes(self):
        """get_site_user_image returns the response body untouched."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests, content=IMAGE_BYTES)
        result = client.get_site_user_image(site_id=1, max_width=100)

        assert result == IMAGE_BYTES
        _assert_request(requests[0], "/site/1/image", {"maxWidth": "100"})

    def test_sync_user_image_with_name(self):
        """A named image is requested from the /image/{name} path."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests, content=IMAGE_BYTES)
        client.get_site_user_image(site_id=1, name="front")
        _assert_request(requests[0], "/site/1/image/front", {})

    def test_sync_installer_image_returns_bytes(self):
        """get_site_installer_image returns the response body untouched."""
        requests: list[httpx.Request] = []
        client = _sync_client(requests, content=IMAGE_BYTES)
        result = client.get_site_installer_image(site_id=1)

        assert result == IMAGE_BYTES
        _assert_request(requests[0], "/site/1/installerImage", {})

    async def test_async_user_image_returns_bytes(self):
        """The async image endpoint also returns raw bytes."""
        requests: list[httpx.Request] = []
        client = _async_client(requests, content=IMAGE_BYTES)
        result = await client.get_site_user_image(site_id=1)

        assert result == IMAGE_BYTES
        _assert_request(requests[0], "/site/1/image", {})

    async def test_async_installer_image_returns_bytes(self):
        """The async installer image endpoint also returns raw bytes."""
        requests: list[httpx.Request] = []
        client = _async_client(requests, content=IMAGE_BYTES)
        result = await client.get_site_installer_image(site_id=1, name="logo")

        assert result == IMAGE_BYTES
        _assert_request(requests[0], "/site/1/installerImage/logo", {})


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
