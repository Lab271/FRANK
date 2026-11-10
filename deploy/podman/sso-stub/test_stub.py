"""The SSO stub's endpoints, over HTTP on an ephemeral port (#238)."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import stub as sso

CLIENT = "frank-local"
SECRET = "stub-secret"
REDIRECT = "https://frank.local:8443/v1/sso/callback"
USERS = [
    {"sub": "00u-a", "name": "Alice", "email": "alice@lab271.dev", "email_verified": True},
    {"sub": "00u-e", "name": "Eve", "email": "eve@lab271.dev", "email_verified": False},
]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


OPENER = urllib.request.build_opener(NoRedirect)


@pytest.fixture
def issuer() -> Iterator[str]:
    stub = sso.Stub(
        issuer="",
        client_id=CLIENT,
        client_secret=SECRET,
        redirect_uris=[REDIRECT],
        users=USERS,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), sso.handler(stub))
    stub.issuer = f"http://localhost:{server.server_address[1]}/oauth2/default"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield stub.issuer
    server.shutdown()


def call(
    url: str, data: dict[str, str] | None = None, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, str], bytes]:
    body = urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with OPENER.open(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def basic(user: str, password: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def authorize(issuer: str, sub: str = "00u-a") -> tuple[str, str, str]:
    """A login picked as `sub`: the code, the verifier and the nonce."""
    verifier = b64url(secrets.token_bytes(32))
    q = {
        "response_type": "code",
        "client_id": CLIENT,
        "redirect_uri": REDIRECT,
        "scope": "openid email profile",
        "state": "st-1",
        "nonce": "n-1",
        "code_challenge": b64url(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
    }
    status, _, page = call(f"{issuer}/v1/authorize?{urlencode(q)}")
    assert status == 200
    assert b"Development only" in page
    status, headers, _ = call(f"{issuer}/v1/authorize", {**q, "sub": sub})
    assert status == 302
    back = urlsplit(headers["Location"])
    assert f"{back.scheme}://{back.netloc}{back.path}" == REDIRECT
    p = {k: v[0] for k, v in parse_qs(back.query).items()}
    assert p["state"] == "st-1"
    return p["code"], verifier, "n-1"


def token(issuer: str, code: str, verifier: str, secret: str = SECRET) -> tuple[int, dict[str, Any]]:
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": verifier}
    status, _, body = call(f"{issuer}/v1/token", form, basic(CLIENT, secret))
    return status, json.loads(body)


def test_discovery_names_the_okta_layout(issuer: str) -> None:
    status, _, body = call(f"{issuer}/.well-known/openid-configuration")
    doc = json.loads(body)
    assert status == 200
    assert doc["issuer"] == issuer
    assert doc["token_endpoint"] == f"{issuer}/v1/token"
    assert doc["code_challenge_methods_supported"] == ["S256"]


def test_the_id_token_verifies_against_the_jwks(issuer: str) -> None:
    code, verifier, nonce = authorize(issuer)
    status, body = token(issuer, code, verifier)
    assert status == 200, body
    h, p, s = body["id_token"].split(".")
    header, claims = json.loads(unb64(h)), json.loads(unb64(p))
    assert header["alg"] == "RS256"
    (jwk,) = json.loads(call(f"{issuer}/v1/keys")[2])["keys"]
    assert jwk["kid"] == header["kid"]
    key = rsa.RSAPublicNumbers(
        int.from_bytes(unb64(jwk["e"]), "big"), int.from_bytes(unb64(jwk["n"]), "big")
    ).public_key()
    key.verify(unb64(s), f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256())
    assert claims["iss"] == issuer
    assert claims["aud"] == CLIENT
    assert (claims["sub"], claims["email"], claims["email_verified"]) == ("00u-a", "alice@lab271.dev", True)
    assert claims["nonce"] == nonce
    info = json.loads(call(f"{issuer}/v1/userinfo", headers={"Authorization": f"Bearer {body['access_token']}"})[2])
    assert info["email"] == "alice@lab271.dev"


def test_a_code_works_once_and_only_with_its_verifier_and_secret(issuer: str) -> None:
    code, verifier, _ = authorize(issuer)
    status, body = token(issuer, code, verifier, secret="wrong")
    assert (status, body["error"]) == (401, "invalid_client")
    status, body = token(issuer, code, "not-the-verifier")
    assert (status, body["error"]) == (400, "invalid_grant")
    # The failed PKCE check used the code up.
    status, body = token(issuer, code, verifier)
    assert (status, body["error"]) == (400, "invalid_grant")
    code, verifier, _ = authorize(issuer)
    assert token(issuer, code, verifier)[0] == 200
    assert token(issuer, code, verifier)[0] == 400


def test_authorize_refuses_unknown_clients_and_redirects(issuer: str) -> None:
    base = {
        "response_type": "code",
        "client_id": CLIENT,
        "redirect_uri": REDIRECT,
        "scope": "openid",
        "state": "s",
        "nonce": "n",
        "code_challenge": "c",
        "code_challenge_method": "S256",
    }
    for change in [
        {"client_id": "other"},
        {"redirect_uri": "https://evil.example/cb"},
        {"code_challenge_method": "plain"},
        {"nonce": ""},
        {"scope": "email"},
    ]:
        status, _, _ = call(f"{issuer}/v1/authorize?{urlencode({**base, **change})}")
        assert status == 400, change


def test_deny_goes_back_with_access_denied(issuer: str) -> None:
    q = {
        "response_type": "code",
        "client_id": CLIENT,
        "redirect_uri": REDIRECT,
        "scope": "openid",
        "state": "s9",
        "nonce": "n",
        "code_challenge": "c",
        "code_challenge_method": "S256",
        "deny": "1",
    }
    status, headers, _ = call(f"{issuer}/v1/authorize", q)
    assert status == 302
    assert headers["Location"] == f"{REDIRECT}?error=access_denied&state=s9"
