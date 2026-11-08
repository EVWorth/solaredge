"""OAuth 2.0 (Site Access) support for the Monitoring API V2.

Homeowners cannot get a Fleet Access API key, so they reach their own data
through Site Access: an OAuth 2.0 authorization-code flow against SolarEdge
Connect. This module covers the whole flow:

1. :func:`authorization_url` builds the link the site owner opens to consent.
2. :func:`parse_callback` reads ``code`` and ``site_id`` from the redirect.
3. :func:`exchange_code` swaps the code for an :class:`OAuthToken`.
4. :class:`OAuth2` is an ``httpx.Auth`` that sends the bearer token, refreshes
   it shortly before it expires or after a 401, and reports every rotated
   token through ``on_token_update`` so it can be persisted.

Refresh tokens rotate on every use and the old one stops working, so always
store the newest token. A refresh token expires after 14 days without use.

Run ``uv run python -m solaredge login --help`` for an interactive helper that
performs steps 1-3 and writes the token to a file.

See https://api-docs.solaredge.com/docs/developer-platform/g09jmvp5t2cok-authentication
"""

from __future__ import annotations

import time
import asyncio
import inspect
import threading
from typing import Any
from dataclasses import asdict, dataclass
from urllib.parse import quote, urlsplit, parse_qsl, urlencode
from collections.abc import Callable, Iterable, Generator, AsyncGenerator

import httpx

from .exceptions import (
    SolarEdgeAPIError,
    SolarEdgeResponseError,
    SolarEdgeValidationError,
    request_url,
    error_from_response,
)

AUTHORIZE_URL = "https://connect.solaredge.com/authorize"
TOKEN_URL = "https://monitoringapi.solaredge.com/v2/oauth2/token"
REVOKE_URL = "https://monitoringapi.solaredge.com/v2/oauth2/revoke-token"
DEFAULT_SCOPES = ("SITE_DATA", "DEVICE_DATA")
# Refresh this many seconds before the access token's stated expiry, so a
# request never leaves with a token that lapses in flight.
EXPIRY_LEEWAY = 60.0

TokenCallback = Callable[["OAuthToken"], Any]

__all__ = [
    "AUTHORIZE_URL",
    "REVOKE_URL",
    "TOKEN_URL",
    "OAuth2",
    "OAuthCallback",
    "OAuthToken",
    "SolarEdgeOAuthError",
    "async_exchange_code",
    "async_refresh_token",
    "async_revoke_token",
    "authorization_url",
    "exchange_code",
    "parse_callback",
    "refresh_token",
    "revoke_token",
]


class SolarEdgeOAuthError(SolarEdgeAPIError):
    """The token endpoint rejected a request (RFC 6749 error response).

    These are deterministic: an ``invalid_client`` means the client ID or
    secret is wrong, and ``invalid_request`` / ``invalid_grant`` usually
    means the code or refresh token was already used or has expired, so the
    site owner must authorize again.

    Attributes:
        error: The OAuth ``error`` code, e.g. ``"invalid_client"``.
        error_description: The human-readable ``error_description``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: Any = None,
        url: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> None:
        super().__init__(
            message, status_code=status_code, response_body=response_body, url=url
        )
        self.error = error
        self.error_description = error_description


@dataclass(frozen=True)
class OAuthToken:
    """An access token and the refresh token that renews it.

    Use :meth:`to_dict` / :meth:`from_dict` to persist it, e.g. as JSON.

    Attributes:
        access_token: Sent as ``Authorization: Bearer ...``.
        refresh_token: Exchanged for a new token pair; single-use.
        expires_at: Unix time at which the access token expires, if known.
        token_type: As returned by the API, normally ``"Bearer"``.
        site_id: The site this grant covers, when known from the callback.
    """

    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    token_type: str = "Bearer"
    site_id: int | None = None

    @classmethod
    def from_response(
        cls, body: Any, *, site_id: int | None = None, now: float | None = None
    ) -> OAuthToken:
        """Build a token from a ``/oauth2/token`` response body."""
        if not isinstance(body, dict) or not body.get("access_token"):
            raise SolarEdgeResponseError("The token endpoint returned no access_token.")
        expires_in = body.get("expires_in")
        expires_at = None
        if isinstance(expires_in, (int, float)) and not isinstance(expires_in, bool):
            expires_at = (time.time() if now is None else now) + float(expires_in)
        return cls(
            access_token=str(body["access_token"]),
            refresh_token=body.get("refresh_token"),
            expires_at=expires_at,
            token_type=str(body.get("token_type") or "Bearer"),
            site_id=site_id,
        )

    def is_expired(
        self, leeway: float = EXPIRY_LEEWAY, now: float | None = None
    ) -> bool:
        """Whether the access token has expired, or will within ``leeway`` s."""
        if self.expires_at is None:
            return False
        return (time.time() if now is None else now) >= self.expires_at - leeway

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OAuthToken:
        """Rebuild a token saved with :meth:`to_dict`."""
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        if not known.get("access_token"):
            raise SolarEdgeValidationError("Saved token has no access_token.")
        return cls(**known)

    def __repr__(self) -> str:
        """Describe the token without exposing secrets."""
        return (
            f"OAuthToken(expires_at={self.expires_at!r}, site_id={self.site_id!r}, "
            f"has_refresh_token={self.refresh_token is not None})"
        )


@dataclass(frozen=True)
class OAuthCallback:
    """The parameters SolarEdge appends to the redirect URL."""

    code: str
    site_id: int | None = None
    state: str | None = None
    external_id: str | None = None


# --- step 1 and 2: authorize and read the callback ----------------------------


def authorization_url(
    client_id: str,
    *,
    redirect_uri: str | None = None,
    scopes: Iterable[str] = DEFAULT_SCOPES,
    state: str | None = None,
    access_duration: int | None = None,
    external_id: str | None = None,
) -> str:
    """Build the SolarEdge Connect URL the site owner opens to grant access.

    Args:
        client_id: The Site Access application's client ID.
        redirect_uri: Where SolarEdge sends the browser afterwards. Must match
            the application's configured Redirect URI exactly.
        scopes: ``SITE_DATA`` for site-level data, ``DEVICE_DATA`` for devices.
        state: Optional value echoed back on the callback.
        access_duration: Grant length in months; 24 is the documented maximum.
        external_id: Your own identifier, echoed back on the callback.
    """
    if not client_id:
        raise SolarEdgeValidationError("client_id is required.")
    params = {
        "client_id": client_id,
        "scope": " ".join(scopes),
        "redirect_uri": redirect_uri,
        "state": state,
        "access_duration": access_duration,
        "external_id": external_id,
    }
    query = urlencode(
        {k: v for k, v in params.items() if v not in (None, "")},
        # Spaces as %20 rather than "+", matching SolarEdge's documented URLs.
        quote_via=quote,
    )
    return f"{AUTHORIZE_URL}?{query}"


def parse_callback(url: str, *, expected_state: str | None = None) -> OAuthCallback:
    """Read ``code`` and ``site_id`` from the URL SolarEdge redirected to.

    Accepts the full redirect URL or just its query string.

    Raises:
        SolarEdgeValidationError: If there is no code, the redirect carries an
            OAuth ``error``, or ``state`` does not match ``expected_state``.
    """
    query = urlsplit(url).query if "?" in url or "://" in url else url
    params = dict(parse_qsl(query.lstrip("?")))
    if "error" in params:
        raise SolarEdgeValidationError(
            f"Authorization failed: {params['error']}"
            + (
                f" ({params['error_description']})"
                if "error_description" in params
                else ""
            )
        )
    code = params.get("code")
    if not code:
        raise SolarEdgeValidationError("The callback URL has no code parameter.")
    state = params.get("state")
    # SolarEdge does not always echo state back, so only a mismatch is an error.
    if expected_state is not None and state is not None and state != expected_state:
        raise SolarEdgeValidationError("The callback's state does not match.")
    site = params.get("site_id")
    return OAuthCallback(
        code=code,
        site_id=int(site) if site and site.isdecimal() else None,
        state=state,
        external_id=params.get("external_id"),
    )


# --- step 3 and refresh: the token endpoint ------------------------------------


def _code_body(
    client_id: str, client_secret: str, code: str, redirect_uri: str | None
) -> dict[str, str]:
    if not (client_id and client_secret and code):
        raise SolarEdgeValidationError(
            "client_id, client_secret and code are required."
        )
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if redirect_uri:
        body["redirect_uri"] = redirect_uri
    return body


def _refresh_body(client_id: str, client_secret: str, token: str) -> dict[str, str]:
    if not (client_id and client_secret and token):
        raise SolarEdgeValidationError(
            "client_id, client_secret and a refresh token are required."
        )
    return {
        "grant_type": "refresh_token",
        "refresh_token": token,
        "client_id": client_id,
        "client_secret": client_secret,
    }


def _token_request(url: str, body: dict[str, str]) -> httpx.Request:
    return httpx.Request("POST", url, json=body, headers={"Accept": "application/json"})


def _oauth_error(response: httpx.Response) -> SolarEdgeAPIError:
    """Turn a failed token-endpoint response into the most useful error."""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and "error" in body:
        error = str(body.get("error"))
        description = body.get("error_description")
        message = f"OAuth token request failed (HTTP {response.status_code}): {error}"
        if description:
            message = f"{message}: {description}"
        return SolarEdgeOAuthError(
            message,
            status_code=response.status_code,
            response_body=body,
            url=request_url(response),
            error=error,
            error_description=description,
        )
    return error_from_response(response)


def _token_from(response: httpx.Response, site_id: int | None = None) -> OAuthToken:
    if response.is_error:
        raise _oauth_error(response)
    try:
        body = response.json()
    except ValueError as exc:
        raise SolarEdgeResponseError(
            "The token endpoint returned a non-JSON body "
            f"(HTTP {response.status_code})."
        ) from exc
    return OAuthToken.from_response(body, site_id=site_id)


def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    *,
    redirect_uri: str | None = None,
    site_id: int | None = None,
    client: httpx.Client | None = None,
    token_url: str = TOKEN_URL,
) -> OAuthToken:
    """Exchange an authorization code for a token pair. Codes are single-use."""
    request = _token_request(
        token_url, _code_body(client_id, client_secret, code, redirect_uri)
    )
    with _sync_http(client) as http:
        return _token_from(http.send(request), site_id)


async def async_exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    *,
    redirect_uri: str | None = None,
    site_id: int | None = None,
    client: httpx.AsyncClient | None = None,
    token_url: str = TOKEN_URL,
) -> OAuthToken:
    """Async version of :func:`exchange_code`."""
    request = _token_request(
        token_url, _code_body(client_id, client_secret, code, redirect_uri)
    )
    async with _async_http(client) as http:
        return _token_from(await http.send(request), site_id)


def refresh_token(
    client_id: str,
    client_secret: str,
    token: OAuthToken | str,
    *,
    client: httpx.Client | None = None,
    token_url: str = TOKEN_URL,
) -> OAuthToken:
    """Exchange a refresh token for a new pair. The old refresh token dies."""
    rt, site = _refresh_inputs(token)
    request = _token_request(token_url, _refresh_body(client_id, client_secret, rt))
    with _sync_http(client) as http:
        return _token_from(http.send(request), site)


async def async_refresh_token(
    client_id: str,
    client_secret: str,
    token: OAuthToken | str,
    *,
    client: httpx.AsyncClient | None = None,
    token_url: str = TOKEN_URL,
) -> OAuthToken:
    """Async version of :func:`refresh_token`."""
    rt, site = _refresh_inputs(token)
    request = _token_request(token_url, _refresh_body(client_id, client_secret, rt))
    async with _async_http(client) as http:
        return _token_from(await http.send(request), site)


def revoke_token(
    token: OAuthToken | str,
    *,
    client: httpx.Client | None = None,
    revoke_url: str = REVOKE_URL,
) -> None:
    """Revoke a token. The site owner must authorize again to reconnect."""
    request = _token_request(revoke_url, {"token": _token_value(token)})
    with _sync_http(client) as http:
        response = http.send(request)
    if response.is_error:
        raise _oauth_error(response)


async def async_revoke_token(
    token: OAuthToken | str,
    *,
    client: httpx.AsyncClient | None = None,
    revoke_url: str = REVOKE_URL,
) -> None:
    """Async version of :func:`revoke_token`."""
    request = _token_request(revoke_url, {"token": _token_value(token)})
    async with _async_http(client) as http:
        response = await http.send(request)
    if response.is_error:
        raise _oauth_error(response)


def _refresh_inputs(token: OAuthToken | str) -> tuple[str, int | None]:
    if isinstance(token, OAuthToken):
        if not token.refresh_token:
            raise SolarEdgeValidationError("This token has no refresh_token.")
        return token.refresh_token, token.site_id
    return token, None


def _token_value(token: OAuthToken | str) -> str:
    return token.access_token if isinstance(token, OAuthToken) else token


class _sync_http:
    """Use the caller's client, or a short-lived one closed afterwards."""

    def __init__(self, client: httpx.Client | None) -> None:
        self._client = client
        self._owned: httpx.Client | None = None

    def __enter__(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        self._owned = httpx.Client(timeout=10.0)
        return self._owned

    def __exit__(self, *exc: object) -> None:
        if self._owned is not None:
            self._owned.close()


class _async_http:
    def __init__(self, client: httpx.AsyncClient | None) -> None:
        self._client = client
        self._owned: httpx.AsyncClient | None = None

    async def __aenter__(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        self._owned = httpx.AsyncClient(timeout=10.0)
        return self._owned

    async def __aexit__(self, *exc: object) -> None:
        if self._owned is not None:
            await self._owned.aclose()


# --- step 4: authenticate API calls, refreshing as needed -----------------------


class OAuth2(httpx.Auth):
    """``httpx.Auth`` that sends a bearer token and keeps it fresh.

    Pass it to a client as ``MonitoringClient(oauth=...)``. Before each request
    it refreshes an access token that is about to expire, and after a 401 it
    refreshes once and retries. Each refresh rotates the refresh token, so
    ``on_token_update`` is called with every new token: persist it there, or
    the next start will hold a refresh token that no longer works.

    Refreshes are serialised, so concurrent requests never spend the same
    refresh token twice. Works with both the sync and async clients.

    Without ``client_id``/``client_secret`` it only sends the token it was
    given, for callers who manage refresh themselves.

    Args:
        token: The current token, e.g. from :func:`exchange_code` or loaded
            with :meth:`OAuthToken.from_dict`.
        client_id: The Site Access application's client ID.
        client_secret: Its client secret.
        on_token_update: Called with each refreshed :class:`OAuthToken`. May
            be a coroutine function when used with the async client.
    """

    requires_response_body = True

    def __init__(
        self,
        token: OAuthToken | str,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        on_token_update: TokenCallback | None = None,
        token_url: str = TOKEN_URL,
    ) -> None:
        if isinstance(token, str):
            token = OAuthToken(access_token=token)
        if not token.access_token:
            raise SolarEdgeValidationError("An access token is required.")
        if bool(client_id) != bool(client_secret):
            raise SolarEdgeValidationError(
                "Pass both client_id and client_secret, or neither."
            )
        self._token = token
        self._client_id = client_id
        self._client_secret = client_secret
        self._on_token_update = on_token_update
        self._token_url = token_url
        self._sync_lock = threading.Lock()
        self._async_lock: asyncio.Lock | None = None

    @property
    def token(self) -> OAuthToken:
        """The token currently in use."""
        return self._token

    @property
    def can_refresh(self) -> bool:
        """Whether this auth holds what a refresh needs."""
        return bool(self._client_id and self._token.refresh_token)

    def __repr__(self) -> str:
        """Describe the auth without exposing secrets."""
        return f"OAuth2(token={self._token!r}, can_refresh={self.can_refresh})"

    # The request/response plumbing shared by both flows.

    def _authorize(self, request: httpx.Request) -> None:
        request.headers["Authorization"] = f"Bearer {self._token.access_token}"

    def _refresh_request(self) -> httpx.Request:
        assert self._client_id and self._client_secret and self._token.refresh_token
        return _token_request(
            self._token_url,
            _refresh_body(
                self._client_id, self._client_secret, self._token.refresh_token
            ),
        )

    def _needs_refresh(self, used: str | None) -> bool:
        """Whether to refresh, given the access token a request was sent with.

        If another request already refreshed while this one waited for the
        lock, the token has moved on and no further refresh is needed.
        """
        if used is not None and used != self._token.access_token:
            return False
        return used is not None or self._token.is_expired()

    def _store(self, response: httpx.Response) -> OAuthToken:
        response.read()
        token = _token_from(response, self._token.site_id)
        if token.refresh_token is None:
            token = OAuthToken(
                access_token=token.access_token,
                refresh_token=self._token.refresh_token,
                expires_at=token.expires_at,
                token_type=token.token_type,
                site_id=token.site_id,
            )
        self._token = token
        return token

    def sync_auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Authenticate a request sent by ``httpx.Client``."""
        if self.can_refresh and self._token.is_expired():
            with self._sync_lock:
                if self._needs_refresh(None):
                    token = self._store((yield self._refresh_request()))
                    self._notify_sync(token)
        self._authorize(request)
        used = self._token.access_token
        response = yield request
        if response.status_code == 401 and self.can_refresh:
            with self._sync_lock:
                if self._needs_refresh(used):
                    token = self._store((yield self._refresh_request()))
                    self._notify_sync(token)
            # Always retry once: with the token another request refreshed, or
            # with ours. Ending here instead would hand the caller the token
            # endpoint's response rather than the API's.
            self._authorize(request)
            yield request

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """Authenticate a request sent by ``httpx.AsyncClient``."""
        lock = self._get_async_lock()
        if self.can_refresh and self._token.is_expired():
            async with lock:
                if self._needs_refresh(None):
                    response = yield self._refresh_request()
                    await response.aread()
                    await self._notify_async(self._store(response))
        self._authorize(request)
        used = self._token.access_token
        response = yield request
        if response.status_code == 401 and self.can_refresh:
            async with lock:
                if self._needs_refresh(used):
                    refreshed = yield self._refresh_request()
                    await refreshed.aread()
                    await self._notify_async(self._store(refreshed))
            # Always retry once; see sync_auth_flow.
            self._authorize(request)
            yield request

    def _get_async_lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    def _notify_sync(self, token: OAuthToken) -> None:
        if self._on_token_update is None:
            return
        result = self._on_token_update(token)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()  # never awaited; close it so it does not leak
            raise SolarEdgeValidationError(
                "on_token_update returned an awaitable; use a regular function "
                "with the sync client."
            )

    async def _notify_async(self, token: OAuthToken) -> None:
        if self._on_token_update is None:
            return
        result = self._on_token_update(token)
        if inspect.isawaitable(result):
            await result
