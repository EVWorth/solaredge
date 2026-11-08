"""Tests for Site Access (OAuth 2.0) support."""

import os
import json
import time
import asyncio
import threading
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from solaredge import (
    OAuth2,
    OAuthToken,
    MonitoringClient,
    SolarEdgeAuthError,
    SolarEdgeOAuthError,
    SolarEdgeServerError,
    AsyncMonitoringClient,
    SolarEdgeValidationError,
    oauth,
)
from solaredge import __main__ as cli

API = "https://monitoringapi.solaredge.com/v2"
TOKEN_URL = oauth.TOKEN_URL


def _token_body(n: int, expires_in: int = 7200) -> dict:
    return {
        "access_token": f"access-{n}",
        "token_type": "Bearer",
        "expires_in": expires_in,
        "refresh_token": f"refresh-{n}",
    }


class FakeSolarEdge:
    """A mock transport for the token endpoint and the API.

    The API accepts only the newest access token, and the token endpoint
    accepts only the newest refresh token, as SolarEdge's rotation does.
    """

    def __init__(self, current: int = 1) -> None:
        self.current = current
        self.requests: list[httpx.Request] = []
        self.refreshes = 0
        self.fail_refresh: dict | None = None
        self.api_status: int | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Answer a token-endpoint or API request."""
        self.requests.append(request)
        if str(request.url) == TOKEN_URL:
            body = json.loads(request.content)
            if self.fail_refresh is not None:
                return httpx.Response(400, json=self.fail_refresh)
            if body.get("refresh_token") != f"refresh-{self.current}":
                return httpx.Response(
                    400, json={"error": "invalid_grant", "error_description": "stale"}
                )
            self.refreshes += 1
            self.current += 1
            return httpx.Response(200, json=_token_body(self.current))
        if self.api_status is not None:
            return httpx.Response(self.api_status, json={})
        if request.headers.get("Authorization") != f"Bearer access-{self.current}":
            return httpx.Response(401, json={"message": "Unauthorized"})
        return httpx.Response(200, json={"ok": True})

    def transport(self) -> httpx.MockTransport:
        """A sync transport backed by this fake."""
        return httpx.MockTransport(self.handler)

    def async_transport(self) -> httpx.MockTransport:
        """An async transport that yields between requests."""

        async def handler(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0)  # let concurrent requests interleave
            return self.handler(request)

        return httpx.MockTransport(handler)


def _token(n: int = 1, expires_in: float = 7200) -> OAuthToken:
    return OAuthToken(
        access_token=f"access-{n}",
        refresh_token=f"refresh-{n}",
        expires_at=time.time() + expires_in,
        site_id=42,
    )


def _auth(token: OAuthToken, updates: list | None = None) -> OAuth2:
    return OAuth2(
        token,
        client_id="cid",
        client_secret="csecret",
        on_token_update=None if updates is None else updates.append,
    )


class TestAuthorizationUrl:
    """Step 1: the consent URL."""

    def test_defaults(self):
        """Client ID and both scopes, with spaces encoded as %20."""
        url = oauth.authorization_url("cid")
        assert url == (
            "https://connect.solaredge.com/authorize"
            "?client_id=cid&scope=SITE_DATA%20DEVICE_DATA"
        )

    def test_all_parameters(self):
        """Every optional parameter is sent when given."""
        url = oauth.authorization_url(
            "cid",
            redirect_uri="http://localhost:8080/oauth/callback",
            scopes=["SITE_DATA"],
            state="xyz",
            access_duration=24,
            external_id="user-7",
        )
        query = parse_qs(urlsplit(url).query)
        assert query == {
            "client_id": ["cid"],
            "scope": ["SITE_DATA"],
            "redirect_uri": ["http://localhost:8080/oauth/callback"],
            "state": ["xyz"],
            "access_duration": ["24"],
            "external_id": ["user-7"],
        }

    def test_client_id_required(self):
        """An empty client ID is refused locally."""
        with pytest.raises(SolarEdgeValidationError):
            oauth.authorization_url("")


class TestParseCallback:
    """Step 2: reading the redirect."""

    def test_full_url(self):
        """code, site_id, state and external_id are extracted."""
        cb = oauth.parse_callback(
            "http://localhost:8080/oauth/callback"
            "?code=abc&site_id=2951500&state=s1&external_id=u7",
            expected_state="s1",
        )
        assert cb == oauth.OAuthCallback("abc", 2951500, "s1", "u7")

    def test_query_string_only(self):
        """A bare query string works too."""
        assert oauth.parse_callback("?code=abc&site_id=1").code == "abc"
        assert oauth.parse_callback("code=abc").site_id is None

    def test_missing_state_is_accepted(self):
        """SolarEdge does not always echo state back."""
        assert oauth.parse_callback("?code=abc", expected_state="s1").code == "abc"

    def test_state_mismatch_rejected(self):
        """A different state means the callback is not ours."""
        with pytest.raises(SolarEdgeValidationError, match="state"):
            oauth.parse_callback("?code=abc&state=evil", expected_state="s1")

    def test_missing_code_rejected(self):
        """Without a code there is nothing to exchange."""
        with pytest.raises(SolarEdgeValidationError, match="no code"):
            oauth.parse_callback("http://localhost/cb?site_id=1")

    def test_error_redirect(self):
        """A denied consent surfaces the OAuth error."""
        with pytest.raises(SolarEdgeValidationError, match="access_denied"):
            oauth.parse_callback("?error=access_denied&error_description=nope")


class TestTokenEndpoint:
    """Step 3 and refresh: the token endpoint."""

    def test_exchange_code(self):
        """The code is posted as JSON and the response becomes a token."""
        seen: list[httpx.Request] = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=_token_body(1))

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            before = time.time()
            token = oauth.exchange_code(
                "cid",
                "csecret",
                "the-code",
                redirect_uri="http://localhost:8080/oauth/callback",
                site_id=42,
                client=http,
            )

        request = seen[0]
        assert request.method == "POST"
        assert str(request.url) == TOKEN_URL
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.content) == {
            "grant_type": "authorization_code",
            "code": "the-code",
            "client_id": "cid",
            "client_secret": "csecret",
            "redirect_uri": "http://localhost:8080/oauth/callback",
        }
        assert token.access_token == "access-1"
        assert token.refresh_token == "refresh-1"
        assert token.site_id == 42
        assert token.expires_at is not None
        assert before + 7200 <= token.expires_at <= time.time() + 7200

    def test_refresh_token(self):
        """Refresh posts the refresh token and keeps the site ID."""
        fake = FakeSolarEdge(current=1)
        with httpx.Client(transport=fake.transport()) as http:
            token = oauth.refresh_token("cid", "csecret", _token(1), client=http)
        assert json.loads(fake.requests[0].content) == {
            "grant_type": "refresh_token",
            "refresh_token": "refresh-1",
            "client_id": "cid",
            "client_secret": "csecret",
        }
        assert token.access_token == "access-2"
        assert token.refresh_token == "refresh-2"
        assert token.site_id == 42

    async def test_async_exchange_and_refresh(self):
        """The async variants send the same requests."""
        fake = FakeSolarEdge(current=0)

        def handler(request):
            body = json.loads(request.content)
            if body["grant_type"] == "authorization_code":
                return httpx.Response(200, json=_token_body(1))
            fake.current = 1
            return fake.handler(request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            first = await oauth.async_exchange_code("cid", "cs", "c", client=http)
            second = await oauth.async_refresh_token("cid", "cs", first, client=http)
        assert second.access_token == "access-2"

    def test_oauth_error_is_parsed(self):
        """RFC 6749 errors become SolarEdgeOAuthError with their fields."""

        def handler(request):
            return httpx.Response(
                400,
                json={"error": "invalid_request", "error_description": "Invalid code"},
            )

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as http,
            pytest.raises(SolarEdgeOAuthError) as excinfo,
        ):
            oauth.exchange_code("cid", "secret-value", "used-code", client=http)

        err = excinfo.value
        assert err.status_code == 400
        assert err.error == "invalid_request"
        assert err.error_description == "Invalid code"
        assert "secret-value" not in str(err)

    def test_non_oauth_error_uses_api_errors(self):
        """A 5xx from the token endpoint is a server error, not an OAuth one."""

        def handler(request):
            return httpx.Response(503, text="down")

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as http,
            pytest.raises(SolarEdgeServerError),
        ):
            oauth.refresh_token("cid", "cs", "rt", client=http)

    def test_refresh_needs_a_refresh_token(self):
        """A token without a refresh token cannot be refreshed."""
        with pytest.raises(SolarEdgeValidationError, match="no refresh_token"):
            oauth.refresh_token("cid", "cs", OAuthToken("only-access"))

    def test_revoke(self):
        """Revoke posts the token to the revoke endpoint."""
        seen: list[httpx.Request] = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200)

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            oauth.revoke_token(_token(1), client=http)
        assert str(seen[0].url) == oauth.REVOKE_URL
        assert json.loads(seen[0].content) == {"token": "access-1"}

    async def test_async_revoke_error(self):
        """Revoke failures raise too."""

        def handler(request):
            return httpx.Response(400, json={"error": "invalid_token"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(SolarEdgeOAuthError):
                await oauth.async_revoke_token("t", client=http)


class TestOAuthToken:
    """Persisting and inspecting tokens."""

    def test_round_trip(self):
        """to_dict output rebuilds the same token, via JSON."""
        token = _token(3)
        assert OAuthToken.from_dict(json.loads(json.dumps(token.to_dict()))) == token

    def test_from_dict_ignores_unknown_keys(self):
        """Extra keys in a stored file do not break loading."""
        assert OAuthToken.from_dict({"access_token": "a", "x": 1}).access_token == "a"

    def test_repr_hides_secrets(self):
        """Logging a token must not leak it."""
        text = repr(_token(1)) + repr(_auth(_token(1)))
        assert "access-1" not in text
        assert "refresh-1" not in text

    def test_expiry(self):
        """is_expired honours the leeway; unknown expiry never expires."""
        now = 1000.0
        assert OAuthToken("a", expires_at=now + 30).is_expired(leeway=60, now=now)
        assert not OAuthToken("a", expires_at=now + 120).is_expired(leeway=60, now=now)
        assert not OAuthToken("a").is_expired()


class TestClientAuthentication:
    """How the monitoring clients authenticate."""

    def test_access_token_is_sent_as_bearer(self):
        """A plain access token is sent as a bearer header, not X-API-Key."""
        fake = FakeSolarEdge(current=1)
        client = MonitoringClient(
            access_token="access-1", client=httpx.Client(transport=fake.transport())
        )
        assert client.get_site_details(42) == {"ok": True}
        request = fake.requests[0]
        assert request.headers["Authorization"] == "Bearer access-1"
        assert "X-API-Key" not in request.headers

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"api_key": "k", "access_token": "t"},
            {"api_key": "k", "oauth": OAuth2("t")},
        ],
    )
    def test_exactly_one_credential(self, kwargs):
        """Mixing credential types is refused."""
        with pytest.raises(SolarEdgeValidationError, match="exactly one of"):
            MonitoringClient(**kwargs)

    def test_partial_client_credentials_rejected(self):
        """A client ID without a secret cannot refresh, so it is refused."""
        with pytest.raises(SolarEdgeValidationError, match="both client_id"):
            OAuth2(_token(), client_id="cid")

    def test_expired_token_is_refreshed_first(self):
        """An expiring token is refreshed before the request goes out."""
        fake = FakeSolarEdge(current=1)
        updates: list[OAuthToken] = []
        auth = _auth(_token(1, expires_in=10), updates)
        client = MonitoringClient(
            oauth=auth, client=httpx.Client(transport=fake.transport())
        )

        assert client.get_site_details(42) == {"ok": True}
        assert [str(r.url) for r in fake.requests] == [TOKEN_URL, f"{API}/sites/42"]
        assert [t.refresh_token for t in updates] == ["refresh-2"]
        assert updates[0].site_id == 42
        assert auth.token.access_token == "access-2"

    def test_401_triggers_one_refresh_and_retry(self):
        """A token revoked early is refreshed once and the call retried."""
        fake = FakeSolarEdge(current=2)  # server already moved on
        updates: list[OAuthToken] = []
        token = OAuthToken("access-1", "refresh-2", time.time() + 7200)
        client = MonitoringClient(
            oauth=_auth(token, updates), client=httpx.Client(transport=fake.transport())
        )

        assert client.get_site_details(42) == {"ok": True}
        assert fake.refreshes == 1
        assert len(updates) == 1

    def test_401_without_refresh_credentials_raises(self):
        """A bare access token cannot recover from a 401."""
        fake = FakeSolarEdge(current=2)
        client = MonitoringClient(
            access_token="access-1", client=httpx.Client(transport=fake.transport())
        )
        with pytest.raises(SolarEdgeAuthError):
            client.get_site_details(42)
        assert fake.refreshes == 0

    def test_persistent_401_is_not_retried_forever(self):
        """A 401 after a successful refresh is returned, not looped on."""
        fake = FakeSolarEdge(current=1)
        fake.api_status = 401
        client = MonitoringClient(
            oauth=_auth(_token(1)), client=httpx.Client(transport=fake.transport())
        )
        with pytest.raises(SolarEdgeAuthError):
            client.get_site_details(42)
        assert fake.refreshes == 1
        assert len(fake.requests) == 3  # call, refresh, retried call

    def test_failed_refresh_raises_oauth_error(self):
        """An expired grant surfaces as SolarEdgeOAuthError."""
        fake = FakeSolarEdge(current=1)
        fake.fail_refresh = {"error": "invalid_grant", "error_description": "expired"}
        client = MonitoringClient(
            oauth=_auth(_token(1, expires_in=0)),
            client=httpx.Client(transport=fake.transport()),
        )
        with pytest.raises(SolarEdgeOAuthError) as excinfo:
            client.get_site_details(42)
        assert excinfo.value.error == "invalid_grant"

    def test_sync_client_rejects_async_callback(self):
        """An async callback would never run under the sync client."""

        async def save(token):
            return None

        fake = FakeSolarEdge(current=1)
        auth = OAuth2(
            _token(1, expires_in=0),
            client_id="cid",
            client_secret="cs",
            on_token_update=save,
        )
        client = MonitoringClient(
            oauth=auth, client=httpx.Client(transport=fake.transport())
        )
        with pytest.raises(SolarEdgeValidationError, match="awaitable"):
            client.get_site_details(42)

    async def test_async_concurrent_requests_refresh_once(self):
        """Concurrent calls with an expired token spend the refresh token once."""
        fake = FakeSolarEdge(current=1)
        saved: list[OAuthToken] = []

        async def save(token):
            await asyncio.sleep(0)
            saved.append(token)

        auth = OAuth2(
            _token(1, expires_in=0),
            client_id="cid",
            client_secret="cs",
            on_token_update=save,
        )
        async with AsyncMonitoringClient(
            oauth=auth, client=httpx.AsyncClient(transport=fake.async_transport())
        ) as client:
            results = await asyncio.gather(
                *(client.get_site_details(i) for i in range(5))
            )

        assert results == [{"ok": True}] * 5
        assert fake.refreshes == 1
        assert [t.access_token for t in saved] == ["access-2"]

    async def test_async_401_refreshes_once_for_concurrent_calls(self):
        """Concurrent 401s on the same stale token trigger a single refresh."""
        fake = FakeSolarEdge(current=2)
        token = OAuthToken("access-1", "refresh-2", time.time() + 7200)
        async with AsyncMonitoringClient(
            oauth=_auth(token),
            client=httpx.AsyncClient(transport=fake.async_transport()),
        ) as client:
            results = await asyncio.gather(
                *(client.get_site_details(i) for i in range(4))
            )
        assert results == [{"ok": True}] * 4
        assert fake.refreshes == 1

    def test_sync_threads_refresh_once(self):
        """Threads sharing one client also refresh only once."""
        fake = FakeSolarEdge(current=1)
        client = MonitoringClient(
            oauth=_auth(_token(1, expires_in=0)),
            client=httpx.Client(transport=fake.transport()),
        )
        errors: list[BaseException] = []

        def call(i):
            try:
                client.get_site_details(i)
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=call, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert fake.refreshes == 1


class TestLoginCommand:
    """``python -m solaredge login``."""

    def test_capture_redirect_serves_the_callback(self):
        """The local server returns the callback path and ignores other paths."""
        result: list = []
        uri = "http://127.0.0.1:18765/oauth/callback"
        t = threading.Thread(target=lambda: result.append(cli.capture_redirect(uri, 5)))
        t.start()
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:18765/favicon.ico", timeout=1)
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
                break
            except OSError:
                time.sleep(0.05)
        with urllib.request.urlopen(
            "http://127.0.0.1:18765/oauth/callback?code=abc&site_id=7", timeout=2
        ) as resp:
            assert b"close this window" in resp.read()
        t.join(5)
        assert result == ["/oauth/callback?code=abc&site_id=7"]

    @pytest.mark.parametrize(
        "uri", ["https://localhost:8080/cb", "http://example.com/cb"]
    )
    def test_capture_redirect_skips_non_local(self, uri):
        """Only plain-http local redirects can be served."""
        assert cli.capture_redirect(uri, 1) is None

    def test_capture_redirect_times_out(self):
        """Nothing arriving returns None so the user can paste instead."""
        assert cli.capture_redirect("http://127.0.0.1:18766/cb", 0.2) is None

    def test_login_with_pasted_url(self, tmp_path, monkeypatch, capsys):
        """The pasted-URL path exchanges the code and writes a 0600 token file."""
        out = tmp_path / "token.json"
        monkeypatch.setenv("SOLAREDGE_CLIENT_SECRET", "cs")
        monkeypatch.setattr(cli, "capture_redirect", lambda uri, timeout: None)
        monkeypatch.setattr(cli.secrets, "token_urlsafe", lambda n: "st")
        monkeypatch.setattr(
            "builtins.input",
            lambda prompt: (
                "http://localhost:8080/oauth/callback?code=c1&site_id=9&state=st"
            ),
        )
        calls = {}

        def fake_exchange(client_id, client_secret, code, **kw):
            calls.update(client_id=client_id, secret=client_secret, code=code, **kw)
            return OAuthToken("a", "r", 123.0, site_id=kw["site_id"])

        monkeypatch.setattr(cli, "exchange_code", fake_exchange)

        rc = cli.main(
            ["login", "--client-id", "cid", "--no-browser", "--output", str(out)]
        )

        assert rc == 0
        assert calls == {
            "client_id": "cid",
            "secret": "cs",
            "code": "c1",
            "redirect_uri": cli.DEFAULT_REDIRECT_URI,
            "site_id": 9,
        }
        assert json.loads(out.read_text())["refresh_token"] == "r"
        if os.name == "posix":
            assert out.stat().st_mode & 0o777 == 0o600
        printed = capsys.readouterr().out
        assert "access_duration=24" in printed
        assert "site 9" in printed
        assert '"a"' not in printed

    def test_login_reports_errors(self, monkeypatch, capsys, tmp_path):
        """A rejected code prints the error and exits non-zero."""
        monkeypatch.setenv("SOLAREDGE_CLIENT_SECRET", "cs")
        monkeypatch.setattr(cli, "capture_redirect", lambda uri, timeout: None)
        monkeypatch.setattr("builtins.input", lambda prompt: "?code=c1")

        def fail(*a, **kw):
            raise SolarEdgeOAuthError(
                "OAuth token request failed", status_code=400, error="invalid_request"
            )

        monkeypatch.setattr(cli, "exchange_code", fail)
        rc = cli.main(
            [
                "login",
                "--client-id",
                "cid",
                "--no-browser",
                "--output",
                str(tmp_path / "t"),
            ]
        )
        assert rc == 1
        assert "OAuth token request failed" in capsys.readouterr().err

    def test_login_needs_client_id(self, monkeypatch, capsys):
        """Without a client ID there is nothing to authorize."""
        monkeypatch.delenv("SOLAREDGE_CLIENT_ID", raising=False)
        assert cli.main(["login", "--no-browser"]) == 2
        assert "client-id" in capsys.readouterr().err
