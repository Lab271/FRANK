#!/usr/bin/env python3
"""
Scenario 2: Evolving Case — "The investigation grows"

What started as a suspicious email is now a full investigation.
As the case develops, FRANK enriches each observable with community intelligence.

Run with: marimo run s2_evolving_case.py
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import httpx
    from datetime import datetime
    return mo, httpx, datetime


@app.cell
def _(mo):
    mo.md("""
    # Scenario 2: Evolving Case

    ## "The investigation grows"

    **The situation:** What started as a suspicious email is now a full investigation.
    You've collected multiple observables:

    - Attack source IP
    - Malware binary (Proton variant)
    - C2 domain

    As the case develops, **FRANK enriches each observable** with community intelligence.

    ---
    """)
    return


@app.cell
def _(mo):
    attack_ip = mo.ui.text(
        value="185.234.72.14",
        placeholder="Attack source IP",
        label="Source IP"
    )
    malware_hash = mo.ui.text(
        value="a1b2c3d4e5f6789...",
        placeholder="SHA256 hash",
        label="Malware hash"
    )
    c2_domain = mo.ui.text(
        value="evil-c2.example.com",
        placeholder="C2 domain",
        label="C2 Domain"
    )
    return attack_ip, malware_hash, c2_domain


@app.cell
def _(mo, attack_ip, malware_hash, c2_domain):
    mo.vstack([
        mo.md("### Submit Investigation Findings"),
        attack_ip,
        malware_hash,
        c2_domain,
        mo.ui.button(label="Submit to FRANK", kind="success")
    ], gap=0.5)
    return


@app.cell
def _(mo, attack_ip, malware_hash, c2_domain):
    # Mock enrichment from FRANK network
    enrichment = {
        "ip": {
            "value": attack_ip.value,
            "network_sightings": 3,
            "first_seen": "2026-05-05T02:15:00Z",
            "tags": ["APT", "C2-infrastructure"],
            "related_campaigns": ["Operation Nightfall"]
        },
        "hash": {
            "value": malware_hash.value,
            "network_sightings": 1,
            "first_seen": "2026-05-04T14:30:00Z",
            "tags": ["Proton", "RAT", "credential-stealer"],
            "detection_name": "Trojan.Proton.Gen"
        },
        "domain": {
            "value": c2_domain.value,
            "network_sightings": 2,
            "first_seen": "2026-05-04T15:00:00Z",
            "tags": ["C2", "DGA-generated"],
            "registrar": "NameCheap (suspicious)"
        }
    }

    mo.md(f"""
    ## FRANK Network Enrichment

    ### 🌐 IP: `{enrichment['ip']['value']}`

    | Field | Value |
    |-------|-------|
    | Network sightings | {enrichment['ip']['network_sightings']} organizations |
    | First seen | {enrichment['ip']['first_seen']} |
    | Tags | {', '.join(enrichment['ip']['tags'])} |
    | Related campaigns | {', '.join(enrichment['ip']['related_campaigns'])} |

    ### 🔒 Hash: `{enrichment['hash']['value'][:20]}...`

    | Field | Value |
    |-------|-------|
    | Network sightings | {enrichment['hash']['network_sightings']} organization (you're first!) |
    | Tags | {', '.join(enrichment['hash']['tags'])} |
    | Detection name | {enrichment['hash']['detection_name']} |

    ### 🌍 Domain: `{enrichment['domain']['value']}`

    | Field | Value |
    |-------|-------|
    | Network sightings | {enrichment['domain']['network_sightings']} organizations |
    | Tags | {', '.join(enrichment['domain']['tags'])} |
    | Registrar | {enrichment['domain']['registrar']} |

    ---

    ### Correlation Graph

    The FRANK network reveals connections between your observables:

    ```
    ┌──────────────────┐
    │  Phishing Email  │
    │   (entry point)  │
    └────────┬─────────┘
             │ downloads
             ▼
    ┌──────────────────┐      resolves to      ┌──────────────────┐
    │  Proton Malware  │ ─────────────────────▶│  185.234.72.14   │
    │  (a1b2c3d4...)   │                       │  (C2 server)     │
    └────────┬─────────┘                       └──────────────────┘
             │ calls                                    ▲
             ▼                                          │
    ┌──────────────────┐      resolves to              │
    │evil-c2.example   │ ──────────────────────────────┘
    │   (C2 domain)    │
    └──────────────────┘
    ```

    **Network insight:** 2 other organizations saw the same IP but different malware variants.
    This suggests a **shared infrastructure** being used by the threat actor.
    """)
    return (enrichment,)


@app.cell
def _(mo):
    mo.md("""
    ---

    ### Value Created

    By submitting your findings:

    - ✅ You contributed **3 new observables** to the network
    - ✅ The IP was **already known** — you got instant context
    - ✅ The hash is **new** — you helped everyone else
    - ✅ The domain correlation was **auto-generated** by FRANK

    ---

    [← Back to Scenarios](/)
    """)
    return


if __name__ == "__main__":
    app.run()
