"""Tests for the typed responses.

Two kinds of check live here. The annotation tests read the overloads in
``_operations.py`` and compare them with each operation's documented response
type, so a method can't be annotated with the wrong TypedDict. The
``assert_type`` tests are checked statically by ``ty check`` in CI; at runtime
``assert_type`` does nothing.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone
from collections.abc import Awaitable

import httpx
import pytest
from typing_extensions import assert_type

import solaredge.types
from solaredge import MonitoringClient, AsyncMonitoringClient, _operations
from solaredge.types import (
    Alert,
    DeviceData,
    Measurements,
    SitePowerFlow,
    StartLivePowerFlow,
    SiteMetadataExtended,
    InverterLifetimeEnergyResponse,
    SiteInverterLifetimeEnergyResponse,
)

from ._spec_responses import SPEC_RESPONSES
from .test_monitoring import ENDPOINTS, _template

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 2, tzinfo=timezone.utc)

# The spec documents a body for this POST, but also says the API sends none,
# in which case the client returns None.
NO_BODY = {"start_live_power_flow"}


def _overload_returns() -> dict[str, dict[str, set[str]]]:
    """Map each method to its overloads' return annotations, keyed by marker."""
    tree = ast.parse(inspect.getsource(_operations))
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Operations"
    )
    result: dict[str, dict[str, set[str]]] = {}
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        if "overload" not in (ast.unparse(d) for d in fn.decorator_list):
            continue
        annotation, returns = fn.args.args[0].annotation, fn.returns
        assert annotation is not None and returns is not None, fn.name
        self_type, returns = ast.unparse(annotation), ast.unparse(returns)
        marker = self_type.removeprefix("Operations[").removesuffix("]")
        result.setdefault(fn.name, {}).setdefault(marker, set()).add(returns)
    return result


def _expected() -> dict[str, set[str]]:
    """Each tested method's documented response type(s), from the specs."""
    expected: dict[str, set[str]] = {"get": {"Any"}}
    for name, _, method, path, _ in ENDPOINTS:
        if name == "get":
            continue
        kind = SPEC_RESPONSES[(method, _template(path))]
        if name in NO_BODY:
            kind = f"{kind} | None"
        expected.setdefault(name, set()).add(kind)
    return expected


class TestAnnotations:
    """Every method is annotated with the response type its spec documents."""

    def test_sync_overloads_match_the_spec(self):
        """Each sync overload returns the spec's type for that operation."""
        returns = _overload_returns()
        actual = {name: by_marker["Sync"] for name, by_marker in returns.items()}
        assert actual == _expected()

    def test_async_overloads_mirror_sync(self):
        """Each async overload returns an awaitable of the sync type."""
        for by_marker in _overload_returns().values():
            assert by_marker["Async"] == {f"Awaitable[{t}]" for t in by_marker["Sync"]}

    def test_types_module_exports_every_type(self):
        """``__all__`` lists every type, and every type referenced exists."""
        exported = set(solaredge.types.__all__)
        for kinds in SPEC_RESPONSES.values():
            for name in kinds.removeprefix("list[").removesuffix("]").split(" | "):
                assert name in exported or name == "None", name


def _client() -> MonitoringClient:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    return MonitoringClient("key", client=httpx.Client(transport=transport))


def _async_client() -> AsyncMonitoringClient:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    return AsyncMonitoringClient("key", client=httpx.AsyncClient(transport=transport))


class TestStaticTypes:
    """What a type checker infers; ``ty check`` fails CI if these drift."""

    def test_sync_returns_typed_dicts(self):
        """The sync client returns each operation's TypedDict directly."""
        client = _client()
        assert_type(client.get_site_details(1), SiteMetadataExtended)
        assert_type(client.get_power(1), Measurements)
        assert_type(client.get_site_alerts(1), list[Alert])
        assert_type(client.get_devices(1), list[DeviceData])
        assert_type(client.get_current_power_flow(1), SitePowerFlow)
        assert_type(client.start_live_power_flow(1), StartLivePowerFlow | None)

    def test_lifetime_energy_type_depends_on_serial_number(self):
        """One inverter and all inverters have different response shapes."""
        client = _client()
        assert_type(
            client.get_inverters_lifetime_energy(1, START, END),
            SiteInverterLifetimeEnergyResponse,
        )
        assert_type(
            client.get_inverters_lifetime_energy(1, START, END, "7E1234AB-01"),
            InverterLifetimeEnergyResponse,
        )

    async def test_async_returns_awaitables(self):
        """The async client returns awaitables of the same TypedDicts."""
        client = _async_client()
        pending = client.get_site_details(1)
        assert_type(pending, Awaitable[SiteMetadataExtended])
        assert_type(await pending, SiteMetadataExtended)
        assert_type(
            await client.get_inverters_lifetime_energy(1, START, END, "7E1234AB-01"),
            InverterLifetimeEnergyResponse,
        )

    def test_unknown_key_is_a_type_error(self):
        """A misspelt field is a static error; ``ty`` warns if it stops being one."""
        details = _client().get_site_details(1)
        with pytest.raises(KeyError):
            details["nmae"]  # ty: ignore[invalid-key]
