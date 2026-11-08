"""Command-line helpers: ``python -m solaredge login``.

``login`` runs the Site Access (OAuth) consent flow for your own site and
saves the resulting token as JSON, ready for :meth:`OAuthToken.from_dict`.
It replaces the manual "open the URL, copy ``code`` from the address bar,
POST it with curl" steps in SolarEdge's homeowner guide.
"""

from __future__ import annotations

import os
import sys
import json
import time
import getpass
import secrets
import argparse
import webbrowser
from typing import Any
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit
from collections.abc import Sequence

from .oauth import (
    DEFAULT_SCOPES,
    OAuthCallback,
    exchange_code,
    parse_callback,
    authorization_url,
)
from .exceptions import SolarEdgeError

DEFAULT_REDIRECT_URI = "http://localhost:8080/oauth/callback"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

_PAGE = (
    b"<!doctype html><meta charset=utf-8><title>SolarEdge</title>"
    b"<p>Authorization received. You can close this window and return to the "
    b"terminal.</p>"
)


def capture_redirect(redirect_uri: str, timeout: float) -> str | None:
    """Serve ``redirect_uri`` locally and return the first callback URL.

    Returns None when the URI is not a local ``http`` address, the port
    cannot be opened, or nothing arrives within ``timeout`` seconds; the
    caller then asks for the URL to be pasted instead.
    """
    parts = urlsplit(redirect_uri)
    if parts.scheme != "http" or parts.hostname not in LOCAL_HOSTS:
        return None
    path = parts.path or "/"
    captured: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if urlsplit(self.path).path != path:
                self.send_error(404)
                return
            captured.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_PAGE)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            # Keep the terminal quiet.
            pass

    try:
        server = HTTPServer((parts.hostname, parts.port or 80), Handler)
    except OSError:
        return None
    deadline = time.monotonic() + timeout
    with server:
        # Requests to other paths (e.g. /favicon.ico) are answered and ignored.
        while not captured:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            server.timeout = remaining
            server.handle_request()
    return captured[0] if captured else None


def _write_token(path: Path, data: dict[str, Any]) -> None:
    """Write the token file readable only by the current user."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def login(args: argparse.Namespace) -> int:
    """Run the consent flow and save the token."""
    client_id = args.client_id or os.environ.get("SOLAREDGE_CLIENT_ID")
    if not client_id:
        print("error: pass --client-id or set SOLAREDGE_CLIENT_ID", file=sys.stderr)
        return 2
    client_secret = os.environ.get("SOLAREDGE_CLIENT_SECRET") or getpass.getpass(
        "Client secret (input hidden): "
    )

    state = secrets.token_urlsafe(16)
    url = authorization_url(
        client_id,
        redirect_uri=args.redirect_uri,
        scopes=args.scopes,
        state=state,
        access_duration=args.access_duration,
    )
    print("Open this URL, sign in with your mySolarEdge account and approve:\n")
    print(f"  {url}\n")
    if not args.no_browser:
        webbrowser.open(url)

    callback_url = capture_redirect(args.redirect_uri, args.timeout)
    if callback_url is None:
        print(
            "After approving, your browser is sent to the redirect URL (it may "
            "show a connection error; that is fine)."
        )
        callback_url = input("Paste the full URL from the address bar: ").strip()

    try:
        callback: OAuthCallback = parse_callback(callback_url, expected_state=state)
        token = exchange_code(
            client_id,
            client_secret,
            callback.code,
            redirect_uri=args.redirect_uri,
            site_id=callback.site_id,
        )
    except SolarEdgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = Path(args.output)
    _write_token(output, token.to_dict())
    print(f"\nSaved the token for site {token.site_id} to {output} (mode 600).")
    print(
        "Load it with OAuthToken.from_dict(json.load(...)) and save every "
        "refreshed token via on_token_update; each refresh replaces the "
        "refresh token."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(prog="python -m solaredge")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "login",
        help="Authorize a Site Access (OAuth) app for your site and save the token.",
        description=(
            "Authorize a Site Access application against your own SolarEdge site "
            "and save the token as JSON. The client secret is read from "
            "SOLAREDGE_CLIENT_SECRET or prompted for; it is never a command-line "
            "argument."
        ),
    )
    p.add_argument(
        "--client-id", help="Application client ID (or SOLAREDGE_CLIENT_ID)."
    )
    p.add_argument(
        "--redirect-uri",
        default=DEFAULT_REDIRECT_URI,
        help="Must match the application's Redirect URI exactly "
        f"(default: {DEFAULT_REDIRECT_URI}).",
    )
    p.add_argument(
        "--scopes",
        nargs="+",
        default=list(DEFAULT_SCOPES),
        help="Scopes to request (default: SITE_DATA DEVICE_DATA).",
    )
    p.add_argument(
        "--access-duration",
        type=int,
        default=24,
        help="Grant length in months (default: 24, the maximum).",
    )
    p.add_argument(
        "--output",
        default="solaredge-token.json",
        help="Where to write the token (default: solaredge-token.json).",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for the browser redirect (default: 300).",
    )
    p.add_argument(
        "--no-browser", action="store_true", help="Print the URL without opening it."
    )
    p.set_defaults(func=login)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m solaredge``."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
