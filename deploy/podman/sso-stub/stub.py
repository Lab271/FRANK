"""A stand-in for Okta's OpenID Connect endpoints, for development and tests.

DEVELOPMENT ONLY (#238, ADR-020): it signs in anyone who clicks a name, and its
signing key is a throwaway generated at every start. Never deploy it.

Endpoints, under the issuer's path (Okta's layout, `/oauth2/default`):

    GET  /.well-known/openid-configuration   discovery
    GET  /v1/keys                            the JWKS
    GET  /v1/authorize                       a page to pick a test user
    POST /v1/authorize                       the pick: back to the client with a code
    POST /v1/token                           code + PKCE verifier -> ID token
    GET  /v1/userinfo                        the claims, for an access token

Settings, from the environment:

    STUB_ISSUER               http://localhost:9400/oauth2/default
    STUB_LISTEN               0.0.0.0:9400
    STUB_CLIENT_ID            frank-local
    STUB_CLIENT_SECRET_FILE   a file holding the client secret (required)
    STUB_REDIRECT_URIS        the allowed redirect URIs, comma separated (required)
    STUB_USERS                users.json next to this file
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urlencode, urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

CODE_SECONDS = 60
TOKEN_SECONDS = 3600


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_int(n: int) -> str:
    return b64url(n.to_bytes((n.bit_length() + 7) // 8, "big"))


@dataclass
class Grant:
    """An issued authorization code, until it is used or expires."""

    sub: str
    client_id: str
    redirect_uri: str
    nonce: str
    challenge: str
    expires: float


@dataclass
class Stub:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uris: list[str]
    users: list[dict[str, Any]]
    key: rsa.RSAPrivateKey = field(
        default_factory=lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )
    kid: str = field(default_factory=lambda: "stub-" + secrets.token_hex(4))
    grants: dict[str, Grant] = field(default_factory=dict)
    access: dict[str, dict[str, Any]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def path(self) -> str:
        return urlsplit(self.issuer).path.rstrip("/")

    def discovery(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/v1/authorize",
            "token_endpoint": f"{self.issuer}/v1/token",
            "jwks_uri": f"{self.issuer}/v1/keys",
            "userinfo_endpoint": f"{self.issuer}/v1/userinfo",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            "scopes_supported": ["openid", "email", "profile"],
        }

    def jwks(self) -> dict[str, Any]:
        pub = self.key.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": self.kid,
                    "use": "sig",
                    "alg": "RS256",
                    "n": b64url_int(pub.n),
                    "e": b64url_int(pub.e),
                }
            ]
        }

    def user(self, sub: str) -> dict[str, Any] | None:
        return next((u for u in self.users if u.get("sub") == sub), None)

    def check_authorize(self, q: dict[str, str]) -> str | None:
        """Why an authorize request is refused, or None."""
        if q.get("client_id") != self.client_id:
            return "unknown client_id"
        if q.get("redirect_uri") not in self.redirect_uris:
            return "redirect_uri is not registered"
        if q.get("response_type") != "code":
            return "response_type must be code"
        if "openid" not in q.get("scope", "").split():
            return "scope must include openid"
        if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
            return "PKCE with S256 is required"
        if not q.get("state") or not q.get("nonce"):
            return "state and nonce are required"
        return None

    def grant(self, q: dict[str, str], sub: str) -> str:
        code = secrets.token_urlsafe(24)
        with self.lock:
            now = time.time()
            self.grants = {c: g for c, g in self.grants.items() if g.expires > now}
            self.grants[code] = Grant(
                sub=sub,
                client_id=q["client_id"],
                redirect_uri=q["redirect_uri"],
                nonce=q["nonce"],
                challenge=q["code_challenge"],
                expires=now + CODE_SECONDS,
            )
        return code

    def client_ok(self, authorization: str | None) -> bool:
        if not authorization or not authorization.startswith("Basic "):
            return False
        try:
            user, _, password = base64.b64decode(authorization[6:]).decode().partition(":")
        except ValueError:
            return False
        return hmac.compare_digest(unquote_plus(user), self.client_id) and hmac.compare_digest(
            unquote_plus(password), self.client_secret
        )

    def token(self, form: dict[str, str]) -> tuple[int, dict[str, Any]]:
        if form.get("grant_type") != "authorization_code":
            return 400, {"error": "unsupported_grant_type"}
        with self.lock:
            g = self.grants.pop(form.get("code", ""), None)
        if g is None or g.expires <= time.time():
            return 400, {"error": "invalid_grant", "error_description": "unknown, used or expired code"}
        if form.get("redirect_uri") != g.redirect_uri:
            return 400, {"error": "invalid_grant", "error_description": "redirect_uri differs"}
        verifier = form.get("code_verifier", "")
        if b64url(hashlib.sha256(verifier.encode()).digest()) != g.challenge:
            return 400, {"error": "invalid_grant", "error_description": "PKCE verification failed"}
        user = self.user(g.sub)
        if user is None:
            return 400, {"error": "invalid_grant", "error_description": "the user is gone"}
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "aud": g.client_id,
            "sub": g.sub,
            "iat": now,
            "exp": now + TOKEN_SECONDS,
            "auth_time": now,
            "nonce": g.nonce,
            "email": user.get("email"),
            "email_verified": bool(user.get("email_verified", False)),
            "name": user.get("name"),
            "groups": user.get("groups", []),
        }
        access = secrets.token_urlsafe(24)
        with self.lock:
            self.access[access] = claims
        return 200, {
            "token_type": "Bearer",
            "expires_in": TOKEN_SECONDS,
            "scope": "openid email profile",
            "access_token": access,
            "id_token": self.sign(claims),
        }

    def sign(self, claims: dict[str, Any]) -> str:
        header = {"alg": "RS256", "kid": self.kid, "typ": "JWT"}
        signing_input = f"{b64url(json.dumps(header).encode())}.{b64url(json.dumps(claims).encode())}"
        sig = self.key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        return f"{signing_input}.{b64url(sig)}"

    def picker(self, q: dict[str, str]) -> str:
        hidden = "".join(
            f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">' for k, v in q.items()
        )
        rows = "".join(
            f'<button name="sub" value="{html.escape(u["sub"])}">{html.escape(u.get("name") or u["sub"])}'
            f" <small>{html.escape(u.get('email') or 'no e-mail')}"
            f"{'' if u.get('email_verified') else ' (unverified)'}</small></button>"
            for u in self.users
        )
        return (
            "<!doctype html><meta charset=utf-8><title>SSO stub</title>"
            "<style>body{font:16px system-ui;max-width:32rem;margin:3rem auto;padding:0 1rem}"
            "button{display:block;width:100%;margin:.4rem 0;padding:.7rem;text-align:left}"
            "p.warn{color:#a00}</style>"
            "<h1>FRANK SSO stub</h1>"
            "<p class=warn>Development only: this is not Okta. Pick a test user.</p>"
            f'<form method=post action="{html.escape(self.path)}/v1/authorize">{hidden}{rows}'
            '<button name="deny" value="1">Deny</button></form>'
        )


def handler(stub: Stub) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "frank-sso-stub"

        def send(self, status: int, body: bytes, kind: str, extra: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def json(self, status: int, value: dict[str, Any]) -> None:
            self.send(status, json.dumps(value).encode(), "application/json")

        def redirect(self, url: str) -> None:
            self.send(302, b"", "text/plain", {"Location": url})

        def route(self) -> tuple[str, dict[str, str]]:
            parts = urlsplit(self.path)
            q = {k: v[0] for k, v in parse_qs(parts.query).items()}
            path = parts.path
            if path.startswith(stub.path):
                path = path[len(stub.path) :]
            return path, q

        def do_GET(self) -> None:  # noqa: N802 (http.server's name)
            path, q = self.route()
            if path == "/.well-known/openid-configuration":
                return self.json(200, stub.discovery())
            if path == "/v1/keys":
                return self.json(200, stub.jwks())
            if path == "/v1/authorize":
                reason = stub.check_authorize(q)
                if reason:
                    return self.send(400, html.escape(reason).encode(), "text/plain; charset=utf-8")
                return self.send(200, stub.picker(q).encode(), "text/html; charset=utf-8")
            if path == "/v1/userinfo":
                auth = self.headers.get("Authorization", "")
                with stub.lock:
                    claims = stub.access.get(auth.removeprefix("Bearer "))
                if claims is None:
                    return self.json(401, {"error": "invalid_token"})
                return self.json(200, {k: claims[k] for k in ("sub", "email", "email_verified", "name", "groups")})
            return self.json(404, {"error": "not_found"})

        def form(self) -> dict[str, str]:
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(min(n, 65536)).decode()
            return {k: v[0] for k, v in parse_qs(body).items()}

        def do_POST(self) -> None:  # noqa: N802
            path, _ = self.route()
            if path == "/v1/authorize":
                f = self.form()
                reason = stub.check_authorize(f)
                if reason:
                    return self.send(400, html.escape(reason).encode(), "text/plain; charset=utf-8")
                back = f["redirect_uri"] + ("&" if "?" in f["redirect_uri"] else "?")
                if f.get("deny"):
                    return self.redirect(back + urlencode({"error": "access_denied", "state": f["state"]}))
                if stub.user(f.get("sub", "")) is None:
                    return self.send(400, b"unknown user", "text/plain")
                code = stub.grant(f, f["sub"])
                return self.redirect(back + urlencode({"code": code, "state": f["state"]}))
            if path == "/v1/token":
                if not stub.client_ok(self.headers.get("Authorization")):
                    return self.json(401, {"error": "invalid_client"})
                status, body = stub.token(self.form())
                return self.json(status, body)
            return self.json(404, {"error": "not_found"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (the base class's name)
            # The path and status only: no query, no headers, so no secret.
            status = args[1] if len(args) > 1 else ""
            sys.stderr.write(f"sso-stub: {self.command} {urlsplit(self.path).path} {status}\n")

    return Handler


def from_env() -> Stub:
    secret_file = os.environ.get("STUB_CLIENT_SECRET_FILE")
    redirects = os.environ.get("STUB_REDIRECT_URIS", "")
    if not secret_file or not redirects:
        sys.exit("sso-stub: set STUB_CLIENT_SECRET_FILE and STUB_REDIRECT_URIS")
    secret = Path(secret_file).read_text().strip()
    if not secret:
        sys.exit(f"sso-stub: {secret_file} is empty")
    users_file = Path(os.environ.get("STUB_USERS", Path(__file__).with_name("users.json")))
    return Stub(
        issuer=os.environ.get("STUB_ISSUER", "http://localhost:9400/oauth2/default").rstrip("/"),
        client_id=os.environ.get("STUB_CLIENT_ID", "frank-local"),
        client_secret=secret,
        redirect_uris=[r.strip() for r in redirects.split(",") if r.strip()],
        users=json.loads(users_file.read_text()),
    )


def main() -> None:
    stub = from_env()
    host, _, port = os.environ.get("STUB_LISTEN", "0.0.0.0:9400").rpartition(":")
    server = ThreadingHTTPServer((host, int(port)), handler(stub))
    sys.stderr.write(
        f"sso-stub: DEVELOPMENT ONLY, issuer {stub.issuer}, client {stub.client_id}, "
        f"{len(stub.users)} users, listening on {host}:{port}\n"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
