#!/usr/bin/env python3
"""Smoke checks against a running FRANK (#208).

    scripts/smoke.py --url http://127.0.0.1:8080 --token frank_…
    scripts/smoke.py --url https://frank.local:8443 --ca target/frank-local-ca.crt --token …
    scripts/smoke.py --url http://127.0.0.1:18080 --token P --token C --token O --writable

Read-only by default: it never submits, so it is safe against a real
deployment. Each `--token` (or TOKEN, space separated) is asked its status
with /v1/whoami and checked for what that status may read and may not.

`--writable` also submits sightings and reads them back, including the
#201 shape: more than 2,000 sightings on one IoC, filtered and paged.
Sightings cannot be deleted, so use it on a throwaway server only
(`make e2e`).

Python 3.9 or later, standard library only: runs on macOS's own python3.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

BATCH = 100  # MAX_BATCH in crates/frank/src/api.rs
PAGE = 500  # MAX_LIMIT in crates/frank/src/records.rs
TIERS = ["public", "observer", "contributor", "partner", "core"]


class Fail(Exception):
    pass


class Down(Exception):
    """The server stopped answering: crashed, or not running."""


class Client:
    def __init__(self, url: str, ca: str | None, timeout: float):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.ctx = (
            ssl.create_default_context(cafile=ca) if url.startswith("https") else None
        )

    def call(self, method: str, path: str, token: str | None = None, body=None):
        """(status, parsed JSON or None). HTTP errors are returned, not raised."""
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, method=method)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout, context=self.ctx
            ) as r:
                return r.status, _json(r.read())
        except urllib.error.HTTPError as e:
            return e.code, _json(e.read())
        except urllib.error.URLError as e:
            if isinstance(e.reason, ssl.SSLError):
                raise Fail(f"TLS: {e.reason} (a private CA needs --ca)") from e
            raise Down(f"{method} {path}: {e.reason}") from e
        except (ConnectionError, TimeoutError) as e:
            raise Down(f"{method} {path}: {e}") from e

    def expect(self, code: int, method: str, path: str, token=None, body=None):
        status, doc = self.call(method, path, token, body)
        if status != code:
            raise Fail(f"{method} {path}: {status}, expected {code}: {_short(doc)}")
        return doc

    def pages(self, path: str, token: str, max_pages: int | None = None) -> list[str]:
        """Every sighting id of a listing, following `next_cursor`."""
        ids: list[str] = []
        sep = "&" if "?" in path else "?"
        cursor = None
        n = 0
        while True:
            q = f"{path}{sep}limit={PAGE}"
            if cursor:
                q += "&cursor=" + urllib.parse.quote(cursor)
            doc = self.expect(200, "GET", q, token)
            ids += [s["sighting_id"] for s in doc["sightings"]]
            cursor = doc.get("next_cursor")
            n += 1
            if not cursor or (max_pages and n >= max_pages):
                return ids


def _json(raw: bytes):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw[:200].decode(errors="replace")


def _short(doc) -> str:
    s = json.dumps(doc) if not isinstance(doc, str) else doc
    return s if len(s) < 200 else s[:200] + "…"


def _once(ids: list[str], what: str) -> None:
    if len(ids) != len(set(ids)):
        raise Fail(f"{what}: {len(ids) - len(set(ids))} sightings listed twice")


# ── read-only checks ──────────────────────────────────────────────────────


def check_health(c: Client, _):
    doc = c.expect(200, "GET", "/health")
    if doc.get("status") != "ok":
        raise Fail(f"/health: {_short(doc)}")
    return f"version {doc.get('version')}"


def check_openapi(c: Client, _):
    doc = c.expect(200, "GET", "/v1/openapi.json")
    if "openapi" not in doc:
        raise Fail("/v1/openapi.json has no openapi field")


def check_unknown_token(c: Client, _):
    c.expect(401, "GET", "/v1/whoami", "frank_not_a_token")


def check_public(c: Client, _):
    c.expect(403, "GET", "/v1/sightings")
    c.expect(200, "GET", "/v1/statistics")


def check_redirect(c: Client, _):
    """http:// on port 80 sends a browser to https://."""
    u = urllib.parse.urlsplit(c.url)
    http = f"http://{u.hostname}/"

    class NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    try:
        urllib.request.build_opener(NoFollow).open(http, timeout=c.timeout)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
        if e.code in (301, 302, 307, 308) and loc.startswith("https://"):
            return f"{http} → {loc}"
        raise Fail(f"{http}: {e.code} {loc!r}, expected a redirect to https://") from e
    except urllib.error.URLError as e:
        raise Fail(f"{http}: {e.reason}") from e
    raise Fail(f"{http}: answered without a redirect")


def check_token(c: Client, token: str, tier: str, max_pages: int):
    """What `tier` may read, and what it may not."""
    rank = TIERS.index(tier)
    c.expect(200, "GET", "/v1/statistics", token)
    if rank < TIERS.index("contributor"):
        c.expect(403, "GET", "/v1/sightings", token)
        c.expect(403, "POST", "/v1/sightings", token, [])
        return
    if rank < TIERS.index("partner"):
        c.expect(403, "GET", "/v1/sightings", token)
        c.expect(403, "GET", "/v1/files", token)
        base = "/v1/sightings?mine=true&"
    else:
        c.expect(200, "GET", "/v1/files", token)
        base = "/v1/sightings?"
    n = 0
    for f in ("ioc_type=ipv4", "ioc_type=domain"):
        ids = c.pages(base + f, token, max_pages)
        _once(ids, f)
        n += len(ids)
    return f"{n} sightings listed by IoC type"


# ── writing checks (--writable) ───────────────────────────────────────────


def sighting(run: str, i: int) -> dict:
    ip = f"10.{(i >> 16) & 255}.{(i >> 8) & 255}.{i & 255}"
    return {
        "submission": {
            "submitter": {"organisation_id": "identity-smoke", "sector": "msp"},
            "hit_target": {
                "organisation_id": "identity-smoke-target",
                "sector": "energy",
            },
            "sighting": {
                "sighting_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "severity": "high",
                "sigma_detection": {"rule_id": f"smoke-{run}"},
                "observables": {
                    "network": [
                        {"type": "ipv4", "value": ip},
                        {"type": "domain", "value": f"smoke-{run}.example"},
                    ]
                },
            },
        }
    }


def check_volume(c: Client, sender: str, reader: str, mine: bool, volume: int):
    """#201: many sightings on one IoC, filtered and paged, each once."""
    run = uuid.uuid4().hex[:8]
    subs = [sighting(run, i) for i in range(volume)]
    t = time.monotonic()
    for i in range(0, volume, BATCH):
        c.expect(201, "POST", "/v1/sightings", sender, subs[i : i + BATCH])
    sent = time.monotonic() - t
    c.expect(200, "POST", "/v1/sightings", sender, subs[:BATCH])  # a resend is a no-op
    want = {s["submission"]["sighting"]["sighting_id"] for s in subs}

    t = time.monotonic()
    ioc = urllib.parse.quote(f"domain:smoke-{run}.example")
    paths = [
        (f"/v1/sightings?ioc={ioc}", reader),
        ("/v1/sightings?ioc_type=ipv4", reader),
    ]
    if mine:
        paths.append((f"/v1/sightings?mine=true&ioc={ioc}", sender))
    for path, tok in paths:
        ids = c.pages(path, tok)
        _once(ids, path)
        got = {i.split("--")[-1] for i in ids}
        if not want <= got:
            raise Fail(f"{path}: {len(want - got)} of {volume} sightings missing")
        if "ioc=" in path and got != want:
            raise Fail(f"{path}: {len(got - want)} sightings that are not this run's")
    return f"{volume} sent in {sent:.1f}s, listed 3 ways in {time.monotonic() - t:.1f}s"


# ── runner ────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--url", default=os.environ.get("FRANK_URL", "http://127.0.0.1:8080")
    )
    p.add_argument(
        "--token",
        action="append",
        default=[],
        help="repeatable; also TOKEN, space separated",
    )
    p.add_argument(
        "--ca", default=os.environ.get("CA") or None, help="CA certificate for https"
    )
    p.add_argument(
        "--redirect",
        choices=["auto", "yes", "no"],
        default="auto",
        help="check that http:// redirects to https:// (auto: for https URLs)",
    )
    p.add_argument(
        "--writable", action="store_true", help="also submit; throwaway servers only"
    )
    p.add_argument(
        "--volume", type=int, default=2100, help="sightings for the volume check"
    )
    p.add_argument(
        "--max-pages", type=int, default=20, help="pages per read-only listing"
    )
    p.add_argument("--timeout", type=float, default=60)
    a = p.parse_args()
    tokens = a.token + os.environ.get("TOKEN", "").split()
    c = Client(a.url, a.ca, a.timeout)

    failed = 0

    def run(name, fn, *args):
        nonlocal failed
        try:
            note = fn(c, *args)
            print(f"  ok    {name}" + (f"  ({note})" if note else ""))
        except Fail as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")

    print(f"FRANK smoke: {c.url}")
    try:
        run("health", check_health, None)
        run("openapi", check_openapi, None)
        run("unknown token is 401", check_unknown_token, None)
        run("public may not list", check_public, None)
        if a.redirect == "yes" or (a.redirect == "auto" and c.url.startswith("https")):
            run("http redirects to https", check_redirect, None)
        known: list[tuple[str, str, str]] = []  # (token, tier, label)
        for tok in tokens:
            status, who = c.call("GET", "/v1/whoami", tok)
            if status != 200:
                failed += 1
                print(f"  FAIL  token {tok[:12]}…: whoami {status}")
            else:
                known.append((tok, who["tier"], who.get("label", "")))
        if not tokens:
            print("  skip  per-status checks: no --token / TOKEN")
        by_tier = {tier: tok for tok, tier, _ in reversed(known)}
        # Writing first, so the read-only listings below page through data.
        if a.writable:
            reader = by_tier.get("core") or by_tier.get("partner")
            sender = by_tier.get("contributor") or reader
            if not reader:
                failed += 1
                print("  FAIL  --writable needs a partner or core token")
            else:
                run(
                    f"#201 volume: {a.volume} sightings on one IoC",
                    check_volume,
                    sender,
                    reader,
                    sender != reader,
                    a.volume,
                )
        for tok, tier, label in known:
            run(f"{tier} ({label})", check_token, tok, tier, a.max_pages)
    except Down as e:
        print(f"  DOWN  the server stopped answering: {e}")
        return 2
    print("passed" if not failed else f"{failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
