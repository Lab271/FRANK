#!/usr/bin/env python3
"""Stream synthetic sightings into a running FRANK and watch the striped table (#177).

    make stream-setup                 # once: register the test tokens locally
    scripts/stream_sightings.py --rate 60 --duration 90m

Without FRANK_TOKENS / FRANK_WATCH_TOKEN it uses the test tokens checked in
as `scripts/stream_tokens.json`: three senders (contributor, three
reporters) and a watcher (partner). `--setup` registers them with the
`frank` CLI; anyone with the repo has them, so only on a local FRANK.

Sends through the API only (`POST /v1/sightings`), as a participant would:
each token in FRANK_TOKENS (contributor or higher) is one reporter. Every
sighting is stamped now, so it lands in the open hour, moves to an hour
file in `live/` once the hour closes and maintenance runs (each minute),
and into `archive/` once the UTC day closes.

With FRANK_WATCH_TOKEN (partner or core, so every TLP level is counted) it
polls `/v1/statistics` and `/v1/files` and checks that the stored count is
the starting count plus what was created, at every step: no sighting lost
or counted twice when an hour is written or a day merged. Run nothing else
against the server meanwhile, or the counts will not add up.

A share of the sightings is sent again; each must come back as a
duplicate with its original receipt. A batch that fails to arrive (say,
the server restarts) is sent again until it does, which is safe for the
same reason. Exit code 1 on any mismatch.

The content is `demo_sightings.py`'s: campaigns from the abuse.ch exports
in `--lists` (`data/lists`, filled by `make lists`) when they are there,
else documentation addresses (RFC 5737) and `.example` domains.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_sightings import campaigns, submission  # noqa: E402

TOKENS_FILE = Path(__file__).resolve().parent / "stream_tokens.json"
# A partner watcher sees these; AMBER+STRICT may become core-only (#164).
TLP_MIX = (["clear", "green", "amber"], [3, 5, 2])


def test_tokens() -> dict:
    return json.loads(TOKENS_FILE.read_text())


def setup(frank: str) -> int:
    """Registers the test participants, users and token hashes with the
    `frank` CLI (FRANK_DATA, FRANK_PARTICIPANTS); skips what exists."""
    t = test_tokens()

    def run(*args: str) -> str:
        return subprocess.run([frank, *args], check=True, capture_output=True, text=True).stdout

    def first_column(*args: str) -> set:
        return {line.split()[0] for line in run(*args).splitlines() if line.strip()}

    orgs, users, prefixes = first_column("participant", "list"), first_column("user", "list"), first_column("token", "list")
    wanted = [(n, tok, "contributor") for n, tok in t["senders"].items()]
    wanted += [(n, tok, "partner") for n, tok in t["watcher"].items()]
    for name, token, status in wanted:
        if name in orgs:
            run("participant", "set-status", name, status)
        else:
            run("participant", "add", name, "--status", status)
        if name not in users:
            run("user", "add", name, name, "--machine")
        h = hashlib.sha256(token.encode()).hexdigest()
        if h[:12] not in prefixes:
            run("token", "add", name, "--hash", h)
        print(f"{name}: {status}, token {h[:12]}…")
    return 0


def duration(s: str) -> float:
    """`90`, `90s`, `15m`, `2h`, `1d` -> seconds."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd]?)", s.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"duration {s!r}: like 90s, 15m, 2h, 1d")
    return float(m[1]) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m[2]]


class Api:
    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def call(self, method: str, path: str, token: str, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.load(e)
            except ValueError:
                return e.code, {"error": e.reason}


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def stamp() -> str:
    return now_utc().strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"{stamp()} {msg}", flush=True)


class Watch:
    """The table as a partner sees it: the stored count and the files."""

    def __init__(self, api: Api, token: str, days: int):
        self.api, self.token, self.days = api, token, days
        self.base = None
        self.hours: set[str] = set()
        self.archives: set[str] = set()
        self.open_rows = 0
        self.mismatches = 0

    def read(self):
        st, stats = self.api.call("GET", f"/v1/statistics?days={self.days}", self.token)
        sf, files = self.api.call("GET", "/v1/files", self.token)
        if st != 200 or sf != 200:
            raise RuntimeError(f"statistics {st}, files {sf}: {stats.get('error') or files.get('error')}")
        live, archive, open_rows = set(), set(), 0
        for f in files["files"]:
            if f.get("open"):
                open_rows = f["rows"]
            elif f["path"].startswith("live/"):
                live.add(f["path"])
            elif f["path"].startswith("archive/"):
                archive.add(f["path"])
        return stats["sightings"], live, archive, open_rows

    def start(self):
        self.base, self.hours, self.archives, self.open_rows = self.read()
        log(f"watch: {self.base} sightings stored, {len(self.hours)} hour files, "
            f"{len(self.archives)} day files, {self.open_rows} open rows")

    def poll(self, created: int, sent: int):
        stored, live, archive, open_rows = self.read()
        for p in sorted(live - self.hours):
            log(f"hour file written: {p} (open rows {self.open_rows} -> {open_rows})")
        for p in sorted(archive - self.archives):
            log(f"day merged: {p}")
        self.hours, self.archives = live, archive
        self.open_rows = open_rows
        expected = self.base + created
        flag = "" if stored == expected else f"  MISMATCH ({stored - expected:+d})"
        if flag:
            self.mismatches += 1
        log(f"sent {sent}  created {created}  stored {stored}  expected {expected}  "
            f"open rows {open_rows}  hour files {len(live)}  day files {len(archive)}{flag}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--url", default=os.environ.get("FRANK_URL", "http://127.0.0.1:8080"))
    p.add_argument("--token", action="append", default=[],
                   help="a sender's token (repeat); default FRANK_TOKENS, comma-separated")
    p.add_argument("--watch-token", default=os.environ.get("FRANK_WATCH_TOKEN"),
                   help="a partner or core token to watch with; default FRANK_WATCH_TOKEN")
    p.add_argument("--rate", type=float, default=60, help="sightings per minute (60)")
    p.add_argument("--batch", type=int, default=5, help="sightings per POST (5, at most 100)")
    p.add_argument("--duration", type=duration, default=duration("1h"), help="how long (1h; 90s, 15m, 2h, 1d)")
    p.add_argument("--resend", type=float, default=0.05, help="share of sightings sent again (0.05)")
    p.add_argument("--poll", type=duration, default=30, help="seconds between watch polls (30)")
    p.add_argument("--seed", type=int, default=None, help="for a repeatable mix of content")
    p.add_argument("--setup", action="store_true",
                   help="register the test tokens of stream_tokens.json with the frank CLI, then stop")
    p.add_argument("--frank", default="target/release/frank", help="the frank binary for --setup")
    p.add_argument("--lists", type=Path, default=Path(os.environ.get("FRANK_DATA", "data")) / "lists",
                   help="the lists the campaigns come from (data/lists; synthetic without them)")
    a = p.parse_args()

    if a.setup:
        return setup(a.frank)
    tokens = a.token or [t.strip() for t in os.environ.get("FRANK_TOKENS", "").split(",") if t.strip()]
    if not tokens:
        tokens = list(test_tokens()["senders"].values())
        log(f"senders: the test tokens of {TOKENS_FILE.name} (make stream-setup registers them)")
    if not a.watch_token and not os.environ.get("FRANK_TOKENS"):
        a.watch_token = next(iter(test_tokens()["watcher"].values()))
    if not 1 <= a.batch <= 100 or a.rate <= 0:
        p.error("--batch 1-100 and --rate > 0")

    api = Api(a.url)
    rng = random.Random(a.seed)
    camps = campaigns(a.lists)
    log("campaigns: " + ", ".join(c[0] for c in camps))
    # The statistics window must cover the whole run.
    watch = Watch(api, a.watch_token, int(a.duration // 86400) + 2) if a.watch_token else None
    if watch:
        watch.start()
    else:
        log("no FRANK_WATCH_TOKEN: sending only, nothing is checked")

    created, duplicates, sent, errors = 0, 0, 0, 0
    per_hour: Counter = Counter()
    receipts: dict[str, dict] = {}
    resend_ok = resend_bad = 0
    pending: list[tuple[str, list]] = []  # batches to send again
    interval = 60.0 * a.batch / a.rate
    end = time.monotonic() + a.duration
    next_send = next_poll = time.monotonic()
    turn = 0

    log(f"streaming {a.rate:g}/min in batches of {a.batch} for {a.duration:g}s "
        f"from {len(tokens)} sender(s) to {api.url}")
    try:
        while time.monotonic() < end or pending:
            now = time.monotonic()
            if now >= next_send:
                next_send += interval
                if pending:
                    token, batch = pending.pop(0)
                elif now < end:
                    token = tokens[turn % len(tokens)]
                    turn += 1
                    batch = []
                    for _ in range(a.batch):
                        s = submission(rng, now_utc(), camps)
                        s["submission"]["sighting"]["timestamp"] = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
                        s["submission"]["tlp_level"] = rng.choices(*TLP_MIX)[0]
                        batch.append(s)
                    # Some of this sender's already-sent sightings again,
                    # unchanged: a sighting_id is the sender's own (#159),
                    # so from another sender it would be a new sighting.
                    sent_before = [r["body"] for r in receipts.values() if r["token"] == token]
                    k = sum(rng.random() < a.resend for _ in batch)
                    batch += rng.sample(sent_before, min(k, len(sent_before)))
                else:
                    batch = None
                if batch:
                    try:
                        code, body = api.call("POST", "/v1/sightings", token, batch)
                    except (urllib.error.URLError, OSError, ValueError) as e:
                        errors += 1
                        log(f"send failed ({e}); will send this batch again")
                        pending.append((token, batch))
                        time.sleep(min(5, interval))
                        continue
                    if code not in (200, 201):
                        errors += 1
                        log(f"POST {code}: {body.get('error')}")
                        if code >= 500:
                            pending.append((token, batch))
                        continue
                    sent += len(batch)
                    hour = now_utc().strftime("%Y-%m-%d %H:00")
                    for item, r in zip(batch, body["receipts"]):
                        sid = r["sighting_id"]
                        if r["status"] == "created":
                            created += 1
                            per_hour[hour] += 1
                            receipts[sid] = {"r": r, "body": item, "token": token}
                        elif sid not in receipts:
                            # Stored by an attempt whose answer was lost (a
                            # retry after a failed send): it counts as created.
                            created += 1
                            per_hour[hour] += 1
                            receipts[sid] = {"r": r, "body": item, "token": token}
                        else:
                            duplicates += 1
                            first = receipts[sid]["r"]
                            if (first["digest"], first["received"]) == (r["digest"], r["received"]):
                                resend_ok += 1
                            else:
                                resend_bad += 1
                                log(f"resend of {sid} got another receipt: {r} vs {first}")
            if watch and now >= next_poll:
                next_poll += a.poll
                try:
                    watch.poll(created, sent)
                except (urllib.error.URLError, OSError, RuntimeError) as e:
                    log(f"watch failed ({e})")
            time.sleep(max(0.05, min(next_send, next_poll if watch else next_send) - time.monotonic()))
    except KeyboardInterrupt:
        log("interrupted")
    if watch:
        try:
            watch.poll(created, sent)
        except (urllib.error.URLError, OSError, RuntimeError) as e:
            log(f"watch failed ({e})")

    print("\nreport")
    print(f"  sent {sent}, created {created}, duplicates {duplicates}, errors {errors}")
    print(f"  resends with their original receipt: {resend_ok}, with another: {resend_bad}")
    for hour, n in sorted(per_hour.items()):
        print(f"  {hour} UTC: {n} created")
    if watch:
        print(f"  hour files {len(watch.hours)}, day files {len(watch.archives)}, "
              f"mismatches {watch.mismatches}")
    return 1 if resend_bad or (watch and watch.mismatches) else 0


if __name__ == "__main__":
    sys.exit(main())
