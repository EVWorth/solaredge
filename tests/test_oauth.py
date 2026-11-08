"""Tests for Site Access (OAuth 2.0) support."""

import os
import json
import time
import socket
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
    SolarEdgeResponseError,
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


class TestEdgeCases:
    """Paths the main flows above do not reach."""

    def test_refresh_without_new_refresh_token_keeps_the_old_one(self):
        """If the API omits refresh_token on refresh, the current one is kept."""

        def handler(request):
            if str(request.url) == TOKEN_URL:
                return httpx.Response(
                    200, json={"access_token": "access-2", "expires_in": 7200}
                )
            return httpx.Response(200, json={"ok": True})

        auth = _auth(_token(1, expires_in=0))
        client = MonitoringClient(
            oauth=auth, client=httpx.Client(transport=httpx.MockTransport(handler))
        )
        client.get_site_details(42)
        assert auth.token.access_token == "access-2"
        assert auth.token.refresh_token == "refresh-1"
        assert auth.token.site_id == 42

    def test_non_json_token_response(self):
        """A 200 that is not JSON is a response error, not a crash."""

        def handler(request):
            return httpx.Response(200, text="<html>maintenance</html>")

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as http,
            pytest.raises(SolarEdgeResponseError, match="non-JSON"),
        ):
            oauth.exchange_code("cid", "cs", "code", client=http)

    @pytest.mark.parametrize("body", [[], {"token_type": "Bearer"}])
    def test_token_response_without_access_token(self, body):
        """A body without access_token is rejected."""
        with pytest.raises(SolarEdgeResponseError, match="no access_token"):
            OAuthToken.from_response(body)

    def test_token_response_without_expiry(self):
        """No expires_in means the token never counts as expired locally."""
        token = OAuthToken.from_response({"access_token": "a"})
        assert token.expires_at is None
        assert not token.is_expired()

    def test_from_dict_requires_access_token(self):
        """A stored file without an access token is refused."""
        with pytest.raises(SolarEdgeValidationError, match="no access_token"):
            OAuthToken.from_dict({"refresh_token": "r"})

    @pytest.mark.parametrize(
        ("call", "match"),
        [
            (lambda: oauth.exchange_code("", "cs", "code"), "code are required"),
            (
                lambda: oauth.refresh_token("cid", "", "rt"),
                "refresh token are required",
            ),
            (lambda: OAuth2(""), "access token is required"),
        ],
    )
    def test_missing_arguments_rejected(self, call, match):
        """Missing credentials fail locally, before any request."""
        with pytest.raises(SolarEdgeValidationError, match=match):
            call()

    def test_sync_revoke_error(self):
        """The sync revoke raises on an OAuth error, like the async one."""

        def handler(request):
            return httpx.Response(400, json={"error": "invalid_token"})

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as http,
            pytest.raises(SolarEdgeOAuthError),
        ):
            oauth.revoke_token("t", client=http)

    async def test_async_revoke_success(self):
        """A successful async revoke returns quietly."""

        def handler(request):
            return httpx.Response(200)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            assert await oauth.async_revoke_token("t", client=http) is None

    def test_owned_http_clients_are_created_and_closed(self, monkeypatch):
        """Without a client argument, a short-lived one is made and closed."""
        made: list = []

        def handler(request):
            return httpx.Response(200, json=_token_body(1))

        real_sync, real_async = httpx.Client, httpx.AsyncClient

        def sync_factory(**kw):
            made.append(real_sync(transport=httpx.MockTransport(handler)))
            return made[-1]

        def async_factory(**kw):
            made.append(real_async(transport=httpx.MockTransport(handler)))
            return made[-1]

        monkeypatch.setattr(oauth.httpx, "Client", sync_factory)
        monkeypatch.setattr(oauth.httpx, "AsyncClient", async_factory)

        assert oauth.exchange_code("cid", "cs", "code").access_token == "access-1"
        assert (
            asyncio.run(oauth.async_exchange_code("cid", "cs", "code")).access_token
            == "access-1"
        )
        assert [c.is_closed for c in made] == [True, True]

    async def test_async_client_accepts_a_sync_callback(self):
        """on_token_update may be a plain function with the async client too."""
        fake = FakeSolarEdge(current=1)
        saved: list[OAuthToken] = []
        async with AsyncMonitoringClient(
            oauth=_auth(_token(1, expires_in=0), saved),
            client=httpx.AsyncClient(transport=fake.async_transport()),
        ) as client:
            await client.get_site_details(42)
        assert [t.access_token for t in saved] == ["access-2"]

    def test_sync_threads_on_401_refresh_once(self):
        """Threads hitting a 401 on the same stale token refresh only once."""
        fake = FakeSolarEdge(current=2)
        token = OAuthToken("access-1", "refresh-2", time.time() + 7200)
        client = MonitoringClient(
            oauth=_auth(token), client=httpx.Client(transport=fake.transport())
        )
        barrier = threading.Barrier(4)
        results: list = []

        def call(i):
            barrier.wait()
            results.append(client.get_site_details(i))

        threads = [threading.Thread(target=call, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results == [{"ok": True}] * 4
        assert fake.refreshes == 1


class TestLoginEdgeCases:
    """Login helper paths not covered above."""

    def test_capture_redirect_port_in_use(self):
        """A port that cannot be bound falls back to pasting the URL."""
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen()
            port = sock.getsockname()[1]
            assert cli.capture_redirect(f"http://127.0.0.1:{port}/cb", 1) is None

    def test_login_opens_browser_and_uses_captured_redirect(
        self, tmp_path, monkeypatch
    ):
        """The default path opens the browser and needs no pasting."""
        opened: list[str] = []
        monkeypatch.setenv("SOLAREDGE_CLIENT_SECRET", "cs")
        monkeypatch.setattr(cli.webbrowser, "open", opened.append)
        monkeypatch.setattr(cli.secrets, "token_urlsafe", lambda n: "st")
        monkeypatch.setattr(
            cli,
            "capture_redirect",
            lambda uri, timeout: "/cb?code=c&site_id=5&state=st",
        )

        def no_input(prompt):  # pragma: no cover - must not be called
            raise AssertionError("asked to paste despite a captured redirect")

        monkeypatch.setattr("builtins.input", no_input)
        monkeypatch.setattr(
            cli,
            "exchange_code",
            lambda *a, **kw: OAuthToken("a", "r", site_id=kw["site_id"]),
        )

        out = tmp_path / "t.json"
        assert cli.main(["login", "--client-id", "cid", "--output", str(out)]) == 0
        assert len(opened) == 1 and opened[0].startswith(oauth.AUTHORIZE_URL)
        assert json.loads(out.read_text())["site_id"] == 5


class _HookLock:
    """A lock that runs a hook on acquire, to replay a race deterministically.

    The hook stands in for another thread or task that refreshed the token
    while this one waited for the lock.
    """

    def __init__(self, hook):
        self.hook = hook

    def __enter__(self):
        self.hook()

    def __exit__(self, *exc):
        return False

    async def __aenter__(self):
        self.hook()

    async def __aexit__(self, *exc):
        return False


class TestRefreshRaces:
    """The 'someone else already refreshed' branches, replayed exactly."""

    def test_expiry_refreshed_by_another_thread(self):
        """If the token was renewed while waiting, no second refresh happens."""
        fake = FakeSolarEdge(current=2)
        auth = _auth(_token(1, expires_in=0))
        renewed_elsewhere = _HookLock(lambda: setattr(auth, "_token", _token(2)))
        auth._sync_lock = renewed_elsewhere  # ty: ignore[invalid-assignment]
        client = MonitoringClient(
            oauth=auth, client=httpx.Client(transport=fake.transport())
        )
        assert client.get_site_details(42) == {"ok": True}
        assert fake.refreshes == 0

    def test_401_refreshed_by_another_thread(self):
        """After a 401, a token renewed elsewhere is retried without refreshing."""
        fake = FakeSolarEdge(current=2)
        token = OAuthToken("access-1", "refresh-1", time.time() + 7200)
        auth = _auth(token)
        renewed_elsewhere = _HookLock(lambda: setattr(auth, "_token", _token(2)))
        auth._sync_lock = renewed_elsewhere  # ty: ignore[invalid-assignment]
        client = MonitoringClient(
            oauth=auth, client=httpx.Client(transport=fake.transport())
        )
        assert client.get_site_details(42) == {"ok": True}
        assert fake.refreshes == 0
        assert len(fake.requests) == 2  # the 401, then the retry

    async def test_async_expiry_refreshed_by_another_task(self):
        """The async flow skips a refresh another task already did."""
        fake = FakeSolarEdge(current=2)
        auth = _auth(_token(1, expires_in=0))
        renewed_elsewhere = _HookLock(lambda: setattr(auth, "_token", _token(2)))
        auth._async_lock = renewed_elsewhere  # ty: ignore[invalid-assignment]
        async with AsyncMonitoringClient(
            oauth=auth, client=httpx.AsyncClient(transport=fake.async_transport())
        ) as client:
            assert await client.get_site_details(42) == {"ok": True}
        assert fake.refreshes == 0

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_refresh_returning_same_token_raises_the_401(self, use_async):
        """If a refresh changes nothing, the caller gets the API's 401.

        Regression: the flow used to stop after the refresh, so httpx handed
        back the token endpoint's 200 as if it were the API's answer.
        """

        def handler(request):
            if str(request.url) == TOKEN_URL:
                return httpx.Response(
                    200, json={"access_token": "access-1", "refresh_token": "r2"}
                )
            return httpx.Response(401, json={})

        token = OAuthToken("access-1", "refresh-1", time.time() + 7200)
        transport = httpx.MockTransport(handler)
        with pytest.raises(SolarEdgeAuthError):
            if use_async:
                async with AsyncMonitoringClient(
                    oauth=_auth(token), client=httpx.AsyncClient(transport=transport)
                ) as client:
                    await client.get_site_details(42)
            else:
                MonitoringClient(
                    oauth=_auth(token), client=httpx.Client(transport=transport)
                ).get_site_details(42)

    def test_sync_client_rejects_any_awaitable_callback(self):
        """A non-coroutine awaitable from the callback is refused too."""

        class Pending:
            def __await__(self):  # pragma: no cover - never awaited
                yield

        fake = FakeSolarEdge(current=1)
        auth = OAuth2(
            _token(1, expires_in=0),
            client_id="cid",
            client_secret="cs",
            on_token_update=lambda token: Pending(),
        )
        client = MonitoringClient(
            oauth=auth, client=httpx.Client(transport=fake.transport())
        )
        with pytest.raises(SolarEdgeValidationError, match="awaitable"):
            client.get_site_details(42)
