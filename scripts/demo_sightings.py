#!/usr/bin/env python3
"""Synthetic FRANK submissions for demos: `demo_sightings.py [N] [DIR] [LISTS]`.

Writes one file per synthetic MDR (`DIR/mdr-<n>.json`, default `target/demo`):
`frank ingest` counts each file as one reporter, so the statistics see three
reporters, as k-anonymity needs (#148).

Dated over the last 7 days, so they show up in the default statistics
window and stay inside retention. A mix of TLP levels, so every tier sees
something.

With LISTS (`data/lists`, filled by `make lists`) the campaigns are built
from what abuse.ch publishes: ThreatFox's busiest malware families (C2
addresses, domains, URLs and payload hashes), URLhaus's online Mirai
downloads and Feodo Tracker's C2s. Those IoCs are real and listed, so they
carry a country, a network and abuse.ch's listing. Next to them a campaign
on public DNS resolvers and one on private and documentation addresses
show how warning lists grey out what is not an indicator (#192). Real
addresses come only from abuse.ch: none are made up. Without LISTS, only
documentation addresses (RFC 5737) and `.example` domains (RFC 2606).
"""
import csv
import datetime as dt
import hashlib
import ipaddress
import json
import pathlib
import random
import re
import sys
import urllib.parse
import uuid

LOADER = [hashlib.sha256(f"loader-{i}".encode()).hexdigest() for i in (1, 2, 3)]
SYNTHETIC = [  # name, SIGMA rule, ATT&CK technique, severity, IPs, domains, URLs, hashes, weight
    ("npm_worm_2026_q4", "sigma-rule-npm-postinstall-exfil", "T1195.001", "high",
     [f"198.51.100.{i}" for i in range(10, 16)], ["pkg-telemetry.example", "webhook-relay.example"], [], [], 4),
    ("banking_phish_2026_q4", "sigma-rule-credential-harvest-login", "T1566.002", "medium",
     [f"203.0.113.{i}" for i in range(40, 48)], ["secure-bank-verify.example", "login-update.example"], [], [], 3),
    ("ransomware_loader_2026", "sigma-rule-lsass-access", "T1003.001", "critical",
     [f"192.0.2.{i}" for i in range(100, 104)], ["c2-update.example"], [], LOADER, 1),
    ("rdp_bruteforce", "sigma-rule-rdp-many-failures", "T1110.001", "low",
     [f"198.51.100.{i}" for i in range(200, 220)], [], [], [], 4),
]
# For ThreatFox's families, busiest first: SIGMA rule, technique, severity, weight.
FAMILY_RULES = [
    ("sigma-rule-c2-beacon", "T1071.001", "high", 4),
    ("sigma-rule-browser-credential-access", "T1555.003", "high", 3),
    ("sigma-rule-payload-download", "T1105", "critical", 2),
]
# Well-known resolvers, used when the public DNS warning list has them.
RESOLVERS = ["8.8.8.8", "1.1.1.1", "9.9.9.9", "208.67.222.222"]
# Private (RFC 1918) and documentation (RFC 5737) addresses: what a
# misconfigured sensor reports. On the special-purpose warning lists.
RESERVED = ["10.20.30.40", "192.168.1.10", "172.16.5.4", "192.0.2.15", "198.51.100.77"]
SECTORS = ["energy"] * 5 + ["financial_services"] * 4 + ["healthcare"] * 2 + ["government", "water", "logistics"]


def rows(path: pathlib.Path):
    """The data rows of an abuse.ch CSV export: `#` lines are comments."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="replace") as f:
        return list(csv.reader((l for l in f if not l.startswith("#") and l.strip()), skipinitialspace=True))


def is_ipv4(v: str) -> bool:
    try:
        return ipaddress.ip_address(v).version == 4
    except ValueError:
        return False


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def threatfox(lists: pathlib.Path) -> list:
    """ThreatFox's three malware families with the most C2 addresses, the
    most recent IoCs of each (the export is newest first)."""
    fams: dict[str, dict[str, dict]] = {}
    for r in rows(lists / "reference" / "threatfox_recent.csv"):
        if len(r) < 8:
            continue
        value, kind, family = r[2], r[3], r[7]
        if not family or family in ("None", "Unknown malware"):
            continue
        # Dicts as ordered sets: first seen is most recent.
        f = fams.setdefault(family, {"ips": {}, "domains": {}, "urls": {}, "hashes": {}})
        if kind == "ip:port" and is_ipv4(value.rsplit(":", 1)[0]):
            f["ips"][value.rsplit(":", 1)[0]] = None
        elif kind == "domain":
            f["domains"][value.lower()] = None
        elif kind == "url":
            f["urls"][value] = None
        elif kind == "sha256_hash":
            f["hashes"][value.lower()] = None
    busiest = sorted((f for f in fams if len(fams[f]["ips"]) >= 3), key=lambda f: (-len(fams[f]["ips"]), f))
    return [(f"{slug(family)}_c2", rule, tech, sev,
             list(fams[family]["ips"])[:8], list(fams[family]["domains"])[:3],
             list(fams[family]["urls"])[:2], list(fams[family]["hashes"])[:3], weight)
            for family, (rule, tech, sev, weight) in zip(busiest, FAMILY_RULES)]


def urlhaus(lists: pathlib.Path) -> list:
    """URLhaus's online Mirai downloads, with the addresses serving them."""
    urls = [r[2] for r in rows(lists / "reference" / "urlhaus.csv")
            if len(r) > 6 and r[3] == "online" and "mirai" in r[6].split(",")][:12]
    if not urls:
        return []
    hosts = list(dict.fromkeys(h for u in urls if (h := urllib.parse.urlsplit(u).hostname) and is_ipv4(h)))[:8]
    return [("mirai_downloads", "sigma-rule-iot-wget-pipe-shell", "T1105", "medium", hosts, [], urls, [], 3)]


def feodo(lists: pathlib.Path) -> list:
    """Feodo Tracker's botnet C2 addresses, when there are a few."""
    ips = sorted({r[1] for r in rows(lists / "reference" / "feodo_ipblocklist.csv")
                  if len(r) > 5 and is_ipv4(r[1])})
    if len(ips) < 2:
        return []
    return [("feodo_botnet_c2", "sigma-rule-c2-beacon", "T1071.001", "high", ips[:8], [], [], [], 1)]


def resolvers(lists: pathlib.Path) -> list:
    """Traffic to public DNS resolvers: on a warning list, greyed out."""
    path = lists / "warning" / "public-dns-v4.json"
    if not path.exists():
        return []
    listed = set(json.loads(path.read_text()).get("list", []))
    ips = [ip for ip in RESOLVERS if ip in listed or f"{ip}/32" in listed]
    if not ips:
        return []
    return [("dns_to_public_resolvers", "sigma-rule-dns-public-resolver", "T1071.004", "low", ips, [], [], [], 2)]


def campaigns(lists: pathlib.Path | None) -> list:
    if lists is None or not lists.is_dir():
        return SYNTHETIC
    real = threatfox(lists) + urlhaus(lists) + feodo(lists)
    if not real:
        print(f"{lists}: no abuse.ch exports (make lists), synthetic campaigns only", file=sys.stderr)
        return SYNTHETIC
    reserved = ("misconfigured_sensor", "sigma-rule-outbound-scan", "T1046", "low", RESERVED, [], [], [], 1)
    return real + resolvers(lists) + [reserved]


def pick(rng: random.Random, values: list, most: int, least: int = 0) -> list:
    return rng.sample(values, k=rng.randint(min(least, len(values)), min(most, len(values))))


def submission(rng: random.Random, now: dt.datetime, camps: list) -> dict:
    name, rule, tech, sev, ips, domains, urls, hashes, _ = rng.choices(camps, weights=[c[8] for c in camps])[0]
    ts = now - dt.timedelta(days=rng.uniform(0, 7), minutes=5)
    net = [{"type": "ipv4", "value": ip} for ip in pick(rng, ips, 3, 1)]
    net += [{"type": "domain", "value": d} for d in pick(rng, domains, 2)]
    net += [{"type": "url", "value": u} for u in pick(rng, urls, 2, 0 if net else 1)]
    obs = {"network": net}
    if files := [{"type": "executable", "hash_sha256": h} for h in pick(rng, hashes, 1)]:
        obs["files"] = files
    return {"submission": {
        "tlp_level": rng.choices(["clear", "green", "amber", "amber+strict"], weights=[3, 5, 2, 1])[0],
        "submitter": {"organisation_id": f"identity-mdr-{rng.randint(1, 3)}", "sector": "cybersecurity_services"},
        "hit_target": {"organisation_id": f"identity-cust-{rng.randint(1, 40)}", "sector": rng.choice(SECTORS),
                       "organisation_size": rng.choice(["small", "medium", "large"])},
        "sighting": {
            # The sender's id (#159). Random, not from the seeded rng: the
            # times move with the clock, so a rerun is new sightings.
            "sighting_id": str(uuid.uuid4()),
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "confidence": rng.randint(55, 95), "severity": sev,
            "observation_count": rng.randint(1, 25),
            "sigma_detection": {"rule_id": rule},
            "threat_context": {"campaign": {"name": name}, "mitre_attack": {"techniques": [{"technique": tech}]}},
            "observables": obs}}}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "target/demo")
    camps = campaigns(pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else None)
    print("campaigns: " + ", ".join(c[0] for c in camps))
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("mdr-*.json"):
        old.unlink()
    rng = random.Random(42)
    now = dt.datetime.now(dt.timezone.utc)
    by_mdr: dict[str, list] = {}
    for _ in range(n):
        s = submission(rng, now, camps)
        mdr = s["submission"]["submitter"]["organisation_id"].removeprefix("identity-")
        by_mdr.setdefault(mdr, []).append(s)
    for mdr, subs in sorted(by_mdr.items()):
        (out / f"{mdr}.json").write_text(json.dumps(subs, indent=1))
        print(f"{out / mdr}.json: {len(subs)}")
