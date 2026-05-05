#!/usr/bin/env python3
"""
Scenario 2: Evolving Case — "The investigation grows"

Run with: uv run python serve.py
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Scenario 2: Evolving Case

    ## "The investigation grows"

    **The situation:** Three days ago, a phishing email slipped past the spam filter
    at one of your customers. The user clicked. Now you're knee-deep in forensics.

    **What you've found so far:**
    - The email contained a link to a credential harvesting page
    - The user entered their password (confirmed via web proxy logs)
    - An hour later, a new executable appeared on their workstation
    - That executable is beaconing to an external IP every 60 seconds

    **The problem:** You have three observables: an IP address, a malware hash, and
    a C2 domain extracted from the binary. Each one is a puzzle piece. But you're
    working in isolation — you don't know if these indicators are part of a known
    campaign, if other organizations have seen them, or if there's related intelligence
    that could accelerate your investigation.

    **What FRANK provides:** As you submit each observable, FRANK enriches it with
    community context. The IP might already be flagged by two other organizations.
    The hash might be brand new — making you the first reporter. The domain might
    correlate with a known APT campaign. This bidirectional flow — you contribute,
    you receive — is the core of the FRANK value proposition.

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("### Configuration")
    config = mo.ui.dictionary({
        "frank_instance": mo.ui.dropdown(
            options=["FRANK-SBP (Production)", "FRANK-SBP (Staging)"],
            value="FRANK-SBP (Production)",
            label="FRANK Instance"
        ),
        "customer": mo.ui.dropdown(
            options=[f"Customer {i}" for i in range(1, 36)],
            value="Customer 7",
            label="Affected Customer"
        ),
    })
    config
    return (config,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Submit Investigation Findings
    """)
    return


@app.cell
def _(mo):
    attack_ip = mo.ui.text(value="185.234.72.14", label="Source IP")
    malware_hash = mo.ui.text(value="a1b2c3d4e5f6789...", label="Malware hash (SHA256)")
    c2_domain = mo.ui.text(value="evil-c2.example.com", label="C2 Domain")
    return attack_ip, malware_hash, c2_domain


@app.cell
def _(mo, attack_ip, malware_hash, c2_domain):
    submit_button = mo.ui.run_button(label="Submit to FRANK")
    mo.vstack([attack_ip, malware_hash, c2_domain, submit_button], gap=0.5)
    return (submit_button,)


@app.cell
def _(mo, submit_button, attack_ip, malware_hash, c2_domain, config):
    mo.stop(not submit_button.value)

    # Mock enrichment from FRANK network
    enrichment = {
        "ip": {
            "value": attack_ip.value,
            "network_sightings": 3,
            "first_seen": "2026-05-05T02:15:00Z",
            "tags": ["APT", "C2-infrastructure"],
            "related_campaigns": ["Operation Nightfall"],
            "status": "known"
        },
        "hash": {
            "value": malware_hash.value,
            "network_sightings": 1,
            "first_seen": "2026-05-04T14:30:00Z",
            "tags": ["Proton", "RAT", "credential-stealer"],
            "detection_name": "Trojan.Proton.Gen",
            "status": "new"
        },
        "domain": {
            "value": c2_domain.value,
            "network_sightings": 2,
            "first_seen": "2026-05-04T15:00:00Z",
            "tags": ["C2", "DGA-generated"],
            "registrar": "NameCheap (suspicious)",
            "status": "known"
        }
    }

    mo.md(f"""
    ---
    ### FRANK Network Enrichment

    **Customer:** {config.value['customer']} | **Instance:** {config.value['frank_instance']}

    #### 🌐 IP: `{enrichment['ip']['value']}`
    | Field | Value |
    |-------|-------|
    | Status | **Known** — 3 other orgs reported |
    | First seen | {enrichment['ip']['first_seen']} |
    | Tags | {', '.join(enrichment['ip']['tags'])} |
    | Related campaigns | {', '.join(enrichment['ip']['related_campaigns'])} |

    #### 🔒 Hash: `{enrichment['hash']['value'][:20]}...`
    | Field | Value |
    |-------|-------|
    | Status | **New** — you're the first reporter! |
    | Tags | {', '.join(enrichment['hash']['tags'])} |
    | Detection name | {enrichment['hash']['detection_name']} |

    #### 🌍 Domain: `{enrichment['domain']['value']}`
    | Field | Value |
    |-------|-------|
    | Status | **Known** — 2 other orgs reported |
    | Tags | {', '.join(enrichment['domain']['tags'])} |
    | Registrar | {enrichment['domain']['registrar']} |

    ---
    ### Value Created

    - ✅ IP was **already known** — you got instant context
    - ✅ Hash is **new** — you helped the network
    - ✅ Domain correlation was **auto-generated** by FRANK
    - ✅ 2 other organizations now see your hash contribution
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    [← Back to Scenarios](./)
    """)
    return


if __name__ == "__main__":
    app.run()
