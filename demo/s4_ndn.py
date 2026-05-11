#!/usr/bin/env python3
"""
Scenario 4: NDN Exchange — Government ↔ Private Sector

NDN = Nationaal Detectie Netwerk (formerly Cyclotron)

Run with: uv run python serve.py
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import json
    return mo, json


@app.cell
def _(mo):
    mo.md("""
    # Scenario 4: NDN Feedback Loop

    ## Government ↔ Private Sector Exchange

    **The situation:** The Dutch government operates the **Nationaal Detectie Netwerk (NDN)**,
    a platform for sharing threat intelligence with critical infrastructure operators. AIVD,
    NCSC-NL, and European partners like Europol contribute indicators and detection rules
    based on their unique visibility into nation-state and organized crime activities.

    **The traditional problem:** Government agencies have strategic intelligence but
    limited visibility into whether their indicators are actually hitting targets in
    the private sector. Meanwhile, private sector MDR providers like SBP have deep
    telemetry across dozens of customers but lack the attribution context that
    government agencies possess.

    **The solution — bidirectional exchange:**
    1. **NDN → FRANK:** Government pushes detection rules (SIGMA format) with
       indicators for APT infrastructure, ransomware staging servers, credential
       harvesting campaigns.
    2. **FRANK matches:** Rules are automatically tested against SBP's MDR telemetry
       covering 35 customers across finance, logistics, energy, and healthcare.
    3. **FRANK → NDN:** Anonymized confirmation flows back: "Rule X matched
       2 organizations in sectors Y and Z, first seen at time T."

    **The value exchange:** Government gets ground-truth confirmation that their
    intelligence is actionable. Private sector gets early warning and detection
    rules they couldn't develop alone. No customer identities are shared — only
    aggregate sector-level statistics.

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("### Configuration")
    config = mo.ui.dictionary({
        "frank_instance": mo.ui.dropdown(
            options=["FRANK-SBP (Production)"],
            value="FRANK-SBP (Production)",
            label="FRANK Instance"
        ),
        "ndn_feed": mo.ui.dropdown(
            options=["AIVD - APT Indicators", "NCSC-NL - Ransomware", "Europol EC3 - Fraud"],
            value="AIVD - APT Indicators",
            label="NDN Feed"
        ),
    })
    config
    return (config,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Incoming Rules from NDN

    | Rule ID | Description | Confidence | Source |
    |---------|-------------|------------|--------|
    | NDN-2026-0847 | APT29 infrastructure - beacon | High | AIVD |
    | NDN-2026-0851 | Ransomware staging server | Medium | NCSC-NL |
    | NDN-2026-0855 | Credential harvesting campaign | High | Europol |
    """)
    return


@app.cell
def _(mo):
    selected_rule = mo.ui.dropdown(
        options=["NDN-2026-0847", "NDN-2026-0851", "NDN-2026-0855"],
        value="NDN-2026-0847",
        label="Select rule to match"
    )
    return (selected_rule,)


@app.cell
def _(mo, selected_rule):
    match_button = mo.ui.run_button(label="Match Against MDR Telemetry")
    mo.hstack([selected_rule, match_button], widths=[2, 1], align="end")
    return (match_button,)


@app.cell
def _(mo, json, match_button, selected_rule, config):
    mo.stop(not match_button.value)

    rule_id = selected_rule.value

    # Mock match results per rule
    match_data = {
        "NDN-2026-0847": {
            "hits": 2,
            "customers": [
                {"name": "Customer 5", "sector": "Finance", "first_seen": "2026-05-05 08:23", "hits": 4, "status": "active"},
                {"name": "Customer 18", "sector": "Logistics", "first_seen": "2026-05-04 14:00", "hits": 1, "status": "single"},
            ]
        },
        "NDN-2026-0851": {
            "hits": 0,
            "customers": []
        },
        "NDN-2026-0855": {
            "hits": 1,
            "customers": [
                {"name": "Customer 31", "sector": "Energy", "first_seen": "2026-05-03 11:15", "hits": 2, "status": "active"},
            ]
        }
    }

    data = match_data.get(rule_id, {"hits": 0, "customers": []})

    if data["hits"] > 0:
        rows = []
        for c in data["customers"]:
            status = "🚨 Active" if c["status"] == "active" else "⚠️ Single hit"
            rows.append(f"| {c['name']} | {c['sector']} | {c['first_seen']} | {c['hits']} | {status} |")
        table = "\n".join(rows)

        # Anonymized feedback to NDN
        feedback = {
            "rule_id": rule_id,
            "private_sector_hits": data["hits"],
            "sectors_affected": list(set(c["sector"] for c in data["customers"])),
            "first_seen": min(c["first_seen"] for c in data["customers"]),
            "confidence": "confirmed"
        }

        result_md = f"""
    ---
    ### Match Results

    **Rule:** `{rule_id}` | **Feed:** {config.value['ndn_feed']}

    **Matched {data['hits']} customers** across 35 in SBP MDR portfolio:

    | Customer | Sector | First Seen | Hits | Status |
    |----------|--------|------------|------|--------|
    {table}

    ---
    ### Contributed Back to NDN (Anonymized)

    ```yaml
    # Anonymized feedback to NDN
    rule_id: {rule_id}
    private_sector_hits: {data['hits']}
    sectors_affected: {feedback['sectors_affected']}
    first_seen: "{feedback['first_seen']}"
    confidence: confirmed
    ```

    **What NDN receives:**
    - ✅ Confirmation that indicators are active in NL private sector
    - ✅ Sector breakdown (without customer names)
    - ✅ Timeline (first seen)
    - ❌ No customer identities
    - ❌ No IP addresses or sensitive telemetry
    """
    else:
        result_md = f"""
    ---
    ### Match Results

    **Rule:** `{rule_id}` | **Feed:** {config.value['ndn_feed']}

    ✅ **No matches** found across 35 SBP MDR customers.

    This is good news — the threat indicators are not present in our telemetry.

    **Feedback to NDN:** Rule received, 0 matches in private sector (NL).
    """

    mo.md(result_md)
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Architecture

    ```
    ┌─────────────────────────────────────────────────────────────────┐
    │                           NDN                                   │
    │              (Nationaal Detectie Netwerk)                       │
    │                  AIVD · NCSC-NL · Europol                       │
    └───────────────────────────┬─────────────────────────────────────┘
                                │
                                │ 1. Push: Detection rules (SIGMA)
                                ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                      FRANK-SBP                                │
    │              (SBP Private FRANK instance)                     │
    │                                                               │
    │  2. Match against MDR telemetry (35 customers)                │
    └───────────────────────────┬───────────────────────────────────┘
                                │
                                │ 3. Return: Anonymized confirmation
                                │    {sectors, hit_count, first_seen}
                                ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                           NDN                                   │
    │              "APT29 confirmed active in NL private sector"      │
    └─────────────────────────────────────────────────────────────────┘

    Government pushes → FRANK matches → Anonymized stats flow back
    ```

    ---
    [← Back to Scenarios](./)
    """)
    return


if __name__ == "__main__":
    app.run()
