#!/usr/bin/env python3
"""Synthetic FRANK submissions for demos: `demo_sightings.py [N] > file.json`.

Dated over the last 7 days, so they show up in the default statistics
window and stay inside retention. Only documentation addresses
(RFC 5737) and `.example` domains (RFC 2606): no real indicators.
"""
import datetime as dt
import hashlib
import json
import random
import sys

CAMPAIGNS = [  # name, SIGMA rule, ATT&CK technique, severity, IPs, domains, weight
    ("npm_worm_2026_q4", "sigma-rule-npm-postinstall-exfil", "T1195.001", "high",
     [f"198.51.100.{i}" for i in range(10, 16)], ["pkg-telemetry.example", "webhook-relay.example"], 4),
    ("banking_phish_2026_q4", "sigma-rule-credential-harvest-login", "T1566.002", "medium",
     [f"203.0.113.{i}" for i in range(40, 48)], ["secure-bank-verify.example", "login-update.example"], 3),
    ("ransomware_loader_2026", "sigma-rule-lsass-access", "T1003.001", "critical",
     [f"192.0.2.{i}" for i in range(100, 104)], ["c2-update.example"], 1),
    ("rdp_bruteforce", "sigma-rule-rdp-many-failures", "T1110.001", "low",
     [f"198.51.100.{i}" for i in range(200, 220)], [], 4),
]
SECTORS = ["energy"] * 5 + ["financial_services"] * 4 + ["healthcare"] * 2 + ["government", "water", "logistics"]


def submission(rng: random.Random, now: dt.datetime) -> dict:
    name, rule, tech, sev, ips, domains, _ = rng.choices(CAMPAIGNS, weights=[c[6] for c in CAMPAIGNS])[0]
    ts = now - dt.timedelta(days=rng.uniform(0, 7), minutes=5)
    net = [{"type": "ipv4", "value": ip} for ip in rng.sample(ips, k=rng.randint(1, min(3, len(ips))))]
    net += [{"type": "domain", "value": d} for d in rng.sample(domains, k=rng.randint(0, len(domains)))]
    obs = {"network": net}
    if name == "ransomware_loader_2026":
        digest = hashlib.sha256(f"loader-{rng.randint(1, 3)}".encode()).hexdigest()
        obs["files"] = [{"type": "executable", "hash_sha256": digest}]
    return {"submission": {
        "submitter": {"organisation_id": f"identity-mdr-{rng.randint(1, 3)}", "sector": "cybersecurity_services"},
        "hit_target": {"organisation_id": f"identity-cust-{rng.randint(1, 40)}", "sector": rng.choice(SECTORS),
                       "organisation_size": rng.choice(["small", "medium", "large"])},
        "sighting": {
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "confidence": rng.randint(55, 95), "severity": sev,
            "observation_count": rng.randint(1, 25),
            "sigma_detection": {"rule_id": rule},
            "threat_context": {"campaign": {"name": name}, "mitre_attack": {"techniques": [{"technique": tech}]}},
            "observables": obs}}}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    rng = random.Random(42)
    now = dt.datetime.now(dt.timezone.utc)
    json.dump([submission(rng, now) for _ in range(n)], sys.stdout, indent=1)
