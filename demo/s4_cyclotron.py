#!/usr/bin/env python3
"""
Scenario 4: Cyclotron Exchange — Government ↔ Private Sector

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
    # Scenario 4: Cyclotron Feedback Loop

    ## Government ↔ Private Sector Exchange

    Cyclotron pushes detection rules. FRANK matches against MDR telemetry.
    Anonymized confirmations flow back. **Both sides win.**

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
        "cyclotron_feed": mo.ui.dropdown(
            options=["AIVD - APT Indicators", "NCSC-NL - Ransomware", "Europol EC3 - Fraud"],
            value="AIVD - APT Indicators",
            label="Cyclotron Feed"
        ),
    })
    config
    return (config,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Incoming Rules from Cyclotron

    | Rule ID | Description | Confidence | Source |
    |---------|-------------|------------|--------|
    | CYC-2026-0847 | APT29 infrastructure - beacon | High | AIVD |
    | CYC-2026-0851 | Ransomware staging server | Medium | NCSC-NL |
    | CYC-2026-0855 | Credential harvesting campaign | High | Europol |
    """)
    return


@app.cell
def _(mo):
    selected_rule = mo.ui.dropdown(
        options=["CYC-2026-0847", "CYC-2026-0851", "CYC-2026-0855"],
        value="CYC-2026-0847",
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
        "CYC-2026-0847": {
            "hits": 2,
            "customers": [
                {"name": "Customer 5", "sector": "Finance", "first_seen": "2026-05-05 08:23", "hits": 4, "status": "active"},
                {"name": "Customer 18", "sector": "Logistics", "first_seen": "2026-05-04 14:00", "hits": 1, "status": "single"},
            ]
        },
        "CYC-2026-0851": {
            "hits": 0,
            "customers": []
        },
        "CYC-2026-0855": {
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

        # Anonymized feedback to Cyclotron
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

    **Rule:** `{rule_id}` | **Feed:** {config.value['cyclotron_feed']}

    **Matched {data['hits']} customers** across 35 in SBP MDR portfolio:

    | Customer | Sector | First Seen | Hits | Status |
    |----------|--------|------------|------|--------|
    {table}

    ---
    ### Contributed Back to Cyclotron (Anonymized)

    ```json
{json.dumps(feedback, indent=2)}
    ```

    **What Cyclotron receives:**
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

    **Rule:** `{rule_id}` | **Feed:** {config.value['cyclotron_feed']}

    ✅ **No matches** found across 35 SBP MDR customers.

    This is good news — the threat indicators are not present in our telemetry.

    **Feedback to Cyclotron:** Rule received, 0 matches in private sector (NL).
    """

    mo.md(result_md)
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
