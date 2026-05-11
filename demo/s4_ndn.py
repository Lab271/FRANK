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
    a platform for sharing threat intelligence with critical infrastructure operators. 
    NCSC-NL, and European partners like Europol contribute indicators and detection rules
    based on their unique visibility into nation-state and organized crime activities.

    **The traditional problem:** Government agencies have strategic intelligence but
    limited visibility into whether their indicators are actually hitting targets in
    the private sector. Meanwhile, private sector MDR providers like SBP have deep
    telemetry across dozens of customers but lack the attribution context that
    government agencies possess.

    **The solution — the NDN feedback loop:**
    1. **NDN → MDRs:** Government publishes SIGMA detection rules directly to
       participating MDR providers (SBP, Northwave,Mnemonic, etc.)
    2. **MDRs deploy:** Each MDR deploys the rules in their customer environments
       and monitors for matches across their portfolio
    3. **MDRs → FRANK:** When rules match, MDRs submit anonymized sightings to FRANK
    4. **FRANK → NDN:** FRANK aggregates across all MDRs and reports back to NDN:
       "Rule X confirmed active — 3 organisations, 2 sectors, first seen at T"

    **The value exchange:** Government gets ground-truth confirmation that their
    intelligence is hitting real targets. MDRs get detection rules they couldn't
    develop alone. FRANK provides the aggregation layer — one connection to NDN
    instead of each MDR maintaining their own. No customer identities flow anywhere.

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
            options=["NCSC - APT Indicators", "NCSC-NL - Ransomware", "Europol EC3 - Fraud"],
            value="NCSC - APT Indicators",
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
    | NDN-2026-0847 | APT29 infrastructure - beacon | High | NCSC |
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

    # Mock match results per rule (anonymized - no customer names in FRANK)
    match_data = {
        "NDN-2026-0847": {
            "organisations": 2,
            "sightings": [
                {"sector": "financial_services", "first_seen": "2026-05-04T14:00:00Z", "hits": 4, "status": "active"},
                {"sector": "logistics", "first_seen": "2026-05-05T08:23:00Z", "hits": 1, "status": "single"},
            ]
        },
        "NDN-2026-0851": {
            "organisations": 0,
            "sightings": []
        },
        "NDN-2026-0855": {
            "organisations": 1,
            "sightings": [
                {"sector": "energy", "first_seen": "2026-05-03T11:15:00Z", "hits": 2, "status": "active"},
            ]
        }
    }

    data = match_data.get(rule_id, {"organisations": 0, "sightings": []})
    sectors = list(set(s["sector"] for s in data["sightings"]))

    # Map rule IDs to proper STIX UUIDs
    rule_uuids = {
        "NDN-2026-0847": "indicator--a1b2c3d4-0847-4e5f-8a9b-c0d1e2f3a4b5",
        "NDN-2026-0851": "indicator--b2c3d4e5-0851-4f6a-9b0c-d1e2f3a4b5c6",
        "NDN-2026-0855": "indicator--c3d4e5f6-0855-4a7b-0c1d-e2f3a4b5c6d7",
    }

    if data["organisations"] > 0:
        rows = []
        for i, s in enumerate(data["sightings"], 1):
            status = "🚨 Active" if s["status"] == "active" else "⚠️ Single hit"
            rows.append(f"| Organisation {i} | {s['sector']} | {s['first_seen'][:10]} | {s['hits']} | {status} |")
        table = "\n".join(rows)

        # Formatted view
        formatted_view = mo.md(f"""
**Rule:** `{rule_id}` | **Feed:** {config.value['ndn_feed']}

**Matched {data['organisations']} organisations** across FRANK network:

| Organisation | Sector | First Seen | Hits | Status |
|--------------|--------|------------|------|--------|
{table}

---
### What flows back to NDN

- ✅ Confirmation that indicators are active in NL private sector
- ✅ Sector breakdown (anonymized)
- ✅ Timeline (first seen)
- ❌ No organisation identities
- ❌ No IP addresses or sensitive telemetry
        """)

        # YAML response view
        first_seen = min(s["first_seen"] for s in data["sightings"])
        yaml_lines = [
            "# FRANK → NDN Feedback (Anonymized)",
            "ndn_feedback:",
            f'  rule_id: "{rule_uuids.get(rule_id, "indicator--unknown")}"',
            f'  rule_name: "{rule_id}"',
            f'  source_feed: "{config.value["ndn_feed"]}"',
            "",
            "  confirmation:",
            '    status: "confirmed_active"',
            "    confidence: 95",
            "",
            "  aggregated_sightings:",
            f"    total_organisations: {data['organisations']}",
            f"    total_hits: {sum(s['hits'] for s in data['sightings'])}",
            f'    first_seen: "{first_seen}"',
            '    last_seen: "2026-05-11T02:15:00Z"',
            "",
            "  sectors_affected:",
        ]
        yaml_lines.extend([f'    - "{s}"' for s in sectors])
        yaml_lines.extend([
            "",
            "  # What is NOT shared:",
            "  # - Organisation identities",
            "  # - Customer names",
            "  # - Source IP addresses",
            "  # - Raw log data",
        ])
        yaml_response = "\n".join(yaml_lines)

        yaml_view = mo.md(f"**FRANK → NDN Response**\n\n```yaml\n{yaml_response}\n```")

    else:
        formatted_view = mo.md(f"""
**Rule:** `{rule_id}` | **Feed:** {config.value['ndn_feed']}

✅ **No matches** found across FRANK network.

This is valuable intelligence — the threat indicators are not hitting the Dutch private sector (yet).
        """)

        yaml_lines = [
            "# FRANK → NDN Feedback (No matches)",
            "ndn_feedback:",
            f'  rule_id: "{rule_uuids.get(rule_id, "indicator--unknown")}"',
            f'  rule_name: "{rule_id}"',
            f'  source_feed: "{config.value["ndn_feed"]}"',
            "",
            "  confirmation:",
            '    status: "not_observed"',
            "    confidence: null",
            "",
            "  aggregated_sightings:",
            "    total_organisations: 0",
            "    total_hits: 0",
            "    first_seen: null",
            "    last_seen: null",
            "",
            "  sectors_affected: []",
        ]
        yaml_response = "\n".join(yaml_lines)

        yaml_view = mo.md(f"**FRANK → NDN Response**\n\n```yaml\n{yaml_response}\n```")

    # Tabbed interface
    mo.vstack([
        mo.md("---\n### Match Results"),
        mo.ui.tabs({
            "📊 Formatted": formatted_view,
            "📄 YAML Response": yaml_view
        })
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Architecture

    ```
    ┌────────────────────────────────────────────────────────────────┐
    │                           NDN                                  │
    │              (Nationaal Detectie Netwerk)                      │
    │                  AIVD · NCSC-NL · Europol                      │
    └──────────┬──────────────────────────────────────────┬──────────┘
               │                                          ▲
               │ 1. Publish SIGMA rules                   │ 4. Aggregated
               ▼                                          │    feedback
    ┌──────────┴──────────────────────────────────────────┴──────────┐
    │                                                                │
    │  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐       │
    │  │  MDR: SBP   │    │MDR: Northwave│    │MDR: Mnemonic │       │
    │  │ 35 customers│    │ 50 customers │    │40 customers  │       │
    │  └──────┬──────┘    └──────┬───────┘    └──────┬───────┘       │
    │         │                  │                   │               │
    │         │ 2. Deploy rules, monitor for matches                 │
    │         │                  │                   │               │
    │         └────────────┬─────┴─────┬─────────────┘               │
    │                      │           │                             │
    │                      ▼           ▼                             │
    │              ┌───────────────────────────┐                     │
    │              │          FRANK            │ 3. Aggregate        │
    │              │    (Central aggregator)   │    sightings        │
    │              └───────────────────────────┘                     │
    │                                                                │
    └────────────────────────────────────────────────────────────────┘

    NDN publishes → MDRs deploy & detect → FRANK aggregates → NDN gets confirmation
    ```

    ---
    [← Back to Scenarios](/)

    <div style="text-align: center; margin-top: 40px; padding: 20px; border-top: 1px solid #ddd;">
    <strong>FRANK — Threat Intelligence Sharing</strong><br>
    <small>Schuberg Philis · SBIR Grant SB1CD24006</small>
    </div>
    """)
    return


if __name__ == "__main__":
    app.run()
