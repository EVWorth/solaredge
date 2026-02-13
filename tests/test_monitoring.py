"""Tests for the monitoring module."""

from solaredge import MonitoringClient


def test_monitoring_client_init():
    """Test that MonitoringClient can be instantiated."""
    client = MonitoringClient(api_key="test_key")
    assert client is not None
    client.close()


def test_monitoring_client_context_manager():
    """Test MonitoringClient as a context manager."""
    with MonitoringClient(api_key="test_key") as client:
        assert client is not None
