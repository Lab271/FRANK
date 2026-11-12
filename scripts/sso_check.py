#!/usr/bin/env python3
"""Sign in to a running FRANK through the OIDC stub, as a browser would (#238).

Standard library only. Checks the whole flow and the rules of ADR-020:

    GET  /v1/sso                   SSO is on
    GET  /v1/sso/login             -> the stub's authorize page, with PKCE
    POST <stub>/v1/authorize       pick a test user -> back with a code
    GET  /v1/sso/callback          -> frank_session cookie, redirect to /
    GET  /v1/whoami                the cookie names the user
    POST /v1/sso/logout            refused without FRANK's Origin, then ends it

    scripts/sso_check.py --url http://localhost:18080 [--user 00u-stub-alice]
    scripts/sso_check.py --url https://frank.local:8443 --ca target/frank-local-ca.crt
    scripts/sso_check.py --url ... --user 00u-stub-superadmin --email superadmin@sbp.example --role superadmin

The session and the codes are never printed.
"""

from __future__ import annotations

import argparse
import http.client
import json
import ssl
import sys
from urllib.parse import parse_qs, urlencode, urlsplit


def fail(msg: str) -> None:
    print(f"sso-check: FAIL {msg}", file=sys.stderr)
    sys.exit(1)


class Client:
    """One request at a time, no redirects followed, cookies by hand."""

    def __init__(self, ca: str | None) -> None:
        self.ctx = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()

    def request(
        self,
        method: str,
        url: str,
        body: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, list[str]], bytes]:
        u = urlsplit(url)
        conn: http.client.HTTPConnection
        if u.scheme == "https":
            conn = http.client.HTTPSConnection(u.netloc, context=self.ctx, timeout=15)
        else:
            conn = http.client.HTTPConnection(u.netloc, timeout=15)
        data = urlencode(body).encode() if body is not None else None
        h = dict(headers or {})
        if data is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        conn.request(method, u.path + (f"?{u.query}" if u.query else ""), body=data, headers=h)
        r = conn.getresponse()
        out: dict[str, list[str]] = {}
        for k, v in r.getheaders():
            out.setdefault(k.lower(), []).append(v)
        payload = r.read()
        conn.close()
        return r.status, out, payload


def set_cookie(headers: dict[str, list[str]], name: str) -> str | None:
    """The value a Set-Cookie gives `name`; None when absent or empty."""
    for c in headers.get("set-cookie", []):
        k, _, rest = c.partition("=")
        if k == name:
            return rest.split(";", 1)[0] or None
    return None


def attrs(headers: dict[str, list[str]], name: str) -> str:
    return next((c for c in headers.get("set-cookie", []) if c.startswith(f"{name}=")), "")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="FRANK's public URL, as FRANK_SSO_REDIRECT_URL has it")
    ap.add_argument("--user", default="00u-stub-alice", help="the stub user to pick (its sub)")
    ap.add_argument("--email", default="alice@lab271.dev", help="the user name FRANK should show")
    ap.add_argument("--role", help="the role the user must have (admin, superadmin)")
    ap.add_argument("--ca", help="a CA certificate for FRANK's HTTPS")
    a = ap.parse_args()
    frank = a.url.rstrip("/")
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(frank))
    c = Client(a.ca)

    status, _, body = c.request("GET", f"{frank}/v1/sso")
    if status != 200 or json.loads(body).get("enabled") is not True:
        fail(f"GET /v1/sso: {status} {body[:200]!r}: is SSO configured?")

    status, h, _ = c.request("GET", f"{frank}/v1/sso/login")
    if status != 303:
        fail(f"GET /v1/sso/login: {status}")
    authorize = h["location"][0]
    q = {k: v[0] for k, v in parse_qs(urlsplit(authorize).query).items()}
    if q.get("code_challenge_method") != "S256" or not q.get("state") or not q.get("nonce"):
        fail("the authorize URL lacks PKCE S256, state or nonce")
    state_cookie = set_cookie(h, "frank_sso_state")
    if state_cookie != q["state"] or "HttpOnly" not in attrs(h, "frank_sso_state"):
        fail("the state cookie is missing, differs from the state, or is not HttpOnly")

    status, _, page = c.request("GET", authorize)
    if status != 200 or b"Development only" not in page:
        fail(f"GET authorize: {status}: is the stub running?")
    stub = authorize.split("?", 1)[0]
    status, h, _ = c.request("POST", stub, {**q, "sub": a.user})
    if status != 302:
        fail(f"POST authorize: {status}")
    callback = h["location"][0]
    if not callback.startswith(f"{frank}/v1/sso/callback?"):
        fail("the stub did not send the browser back to FRANK's callback")

    path = callback[len(frank) :]
    status, h, _ = c.request("GET", f"{frank}{path}", headers={"Cookie": "frank_sso_state=not-this-browser"})
    if status != 303 or h["location"][0] != "/?sso=refused":
        fail("a callback with another browser's state was not refused")

    # The foreign attempt is refused before the state is used, so it does not
    # spoil the real browser's login.
    status, h, _ = c.request("GET", f"{frank}{path}", headers={"Cookie": f"frank_sso_state={state_cookie}"})
    if status != 303 or h["location"][0] != "/":
        fail(f"GET callback: {status} -> {h.get('location')}: see FRANK's sso_refused audit line")
    session = set_cookie(h, "frank_session")
    a_session = attrs(h, "frank_session")
    if not session or "HttpOnly" not in a_session or "SameSite=Lax" not in a_session:
        fail("no HttpOnly, SameSite=Lax session cookie")
    if origin.startswith("https://") and "Secure" not in a_session:
        fail("the session cookie is not Secure on https")
    cookie = {"Cookie": f"frank_session={session}"}

    status, _, body = c.request("GET", f"{frank}/v1/whoami", headers=cookie)
    me = json.loads(body)
    if status != 200 or me.get("user") != a.email:
        fail(f"whoami with the session: {status} {me}")
    if a.role and me.get("role") != a.role:
        fail(f"{a.email} signed in without the role {a.role}: {me}")
    status, _, _ = c.request("GET", f"{frank}/v1/whoami", headers={**cookie, "Authorization": "Bearer not-a-token"})
    if status != 401:
        fail("a bad bearer token did not win over the session cookie")

    status, _, _ = c.request("POST", f"{frank}/v1/sso/logout", headers=cookie)
    if status != 403:
        fail(f"logout without an Origin: {status}, expected 403")
    status, h, _ = c.request("POST", f"{frank}/v1/sso/logout", headers={**cookie, "Origin": origin})
    if status != 200:
        fail(f"logout: {status}")
    status, _, body = c.request("GET", f"{frank}/v1/whoami", headers=cookie)
    if json.loads(body).get("tier") != "public":
        fail("the session still works after logout")

    role = f", {a.role}" if a.role else ""
    print(f"sso-check: OK, signed in as {a.email} ({me.get('tier')}{role}) through the stub and out again")


if __name__ == "__main__":
    main()
