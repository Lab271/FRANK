#!/usr/bin/env python3
"""
Scenario 1: Active Incident — "Is this happening elsewhere?"

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
    # Scenario 1: Active Incident

    ## "Is this happening elsewhere?"

    **The situation:** It's 2 AM. Your Security Operations Center just detected
    a suspicious IP address in the firewall logs of one of your MDR customers.
    The connection was outbound, repeated every 5 minutes — classic C2 beacon behavior.

    **The problem:** You're about to wake up the customer's CISO and trigger a full
    incident response. But first you need context:

    - Is this a targeted attack on this specific customer?
    - Or is this IP part of a broader campaign hitting multiple organizations?
    - Has anyone else in the FRANK network seen this indicator?

    **What FRANK provides:** Instead of manually reaching out to peers or searching
    public threat feeds, you query FRANK. Within seconds, you get an anonymized view
    of whether other organizations — across different sectors — have reported the same
    indicator. This transforms your incident from "isolated event" to "coordinated response."

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ### Configuration
    """)
    config = mo.ui.dictionary({
        "frank_instance": mo.ui.dropdown(
            options=["FRANK-SBP (Production)", "FRANK-SBP (Staging)", "FRANK-Central"],
            value="FRANK-SBP (Production)",
            label="FRANK Instance"
        ),
        "org_id": mo.ui.dropdown(
            options=["org-sbp", "org-customer-alpha", "org-customer-beta"],
            value="org-sbp",
            label="Your Organization"
        ),
    })
    config
    return (config,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Query
    """)
    return


@app.cell
def _(mo):
    ioc_input = mo.ui.text(
        value="185.234.72.14",
        placeholder="Enter IP, hash, or domain...",
        label="IoC to check",
        full_width=True
    )
    return (ioc_input,)


@app.cell
def _(mo, ioc_input):
    check_button = mo.ui.run_button(label="Check FRANK")
    mo.hstack([ioc_input, check_button], widths=[3, 1], align="end")
    return (check_button,)


@app.cell
def _(mo, check_button, ioc_input, config):
    mo.stop(not check_button.value)

    # Simulate FRANK API call
    ioc_value = ioc_input.value or "185.234.72.14"

    # Mock response based on IoC
    if "185.234" in ioc_value:
        result = {
            "ioc": ioc_value,
            "seen_by": 3,
            "total_orgs": 12,
            "sectors": ["Finance", "Finance", "Logistics"],
            "first_seen": "2026-05-11T00:15:00Z",
            "trend": "increasing",
            "your_org_first": False,
            "confidence_avg": 0.90
        }
    else:
        result = {
            "ioc": ioc_value,
            "seen_by": 0,
            "total_orgs": 12,
            "sectors": [],
            "first_seen": None,
            "trend": "unknown",
            "your_org_first": True,
            "confidence_avg": None
        }

    unique_sectors = list(set(result['sectors']))

    if result['seen_by'] > 0:
        interpretation = f"""
        🚨 **You are NOT alone.** This IoC is active across **{result['seen_by']} organizations**.

        **Recommended actions:**
        1. Check shared SIGMA rules for this IoC
        2. Coordinate response with affected parties
        3. Submit additional observables you discover
        """
    else:
        interpretation = """
        ✅ **First sighting.** No other organization has reported this IoC yet.

        **You are the first reporter** — your submission will help others.
        """

    # Formatted results view
    formatted_view = mo.md(f"""
    **Query:** `{result['ioc']}` via `{config.value['frank_instance']}`

    | Metric | Value |
    |--------|-------|
    | **Organizations reporting** | {result['seen_by']} of {result['total_orgs']} |
    | **Sectors affected** | {', '.join(unique_sectors) if unique_sectors else '—'} |
    | **First seen in network** | {result['first_seen'] or '—'} |
    | **Trend** | {'↑ ' + result['trend'] if result['trend'] != 'unknown' else '—'} |
    | **Average confidence** | {f"{result['confidence_avg']:.0%}" if result['confidence_avg'] else '—'} |
    | **You are first reporter** | {'✅ Yes' if result['your_org_first'] else '❌ No'} |

    ---
    ### Interpretation
    {interpretation}
    """)

    # YAML response view
    yaml_response = f"""# FRANK API Response — Observable Query
query_result:
  indicator_id: "indicator--e7b3c2a1-4f5d-4e6a-8b9c-1d2e3f4a5b6c"
  observable: "{result['ioc']}"
  type: "ipv4-addr"

  network_visibility:
    total_organisations: {result['total_orgs']}
    organisations_reporting: {result['seen_by']}
    you_are_first_reporter: {str(result['your_org_first']).lower()}

  sighting_summary:
    sighting_id: "sighting--a1b2c3d4-5e6f-7a8b-9c0d-e1f2a3b4c5d6"
    first_seen: {f'"{result["first_seen"]}"' if result['first_seen'] else 'null'}
    last_seen: "2026-05-11T02:15:00Z"
    trend: "{result['trend']}"
    confidence_avg: {result['confidence_avg'] if result['confidence_avg'] else 'null'}

  sectors_affected:
{chr(10).join(f'    - "{s}"' for s in unique_sectors) if unique_sectors else '    []'}

  sigma_matches:
    - rule_id: "indicator--f8d9e0a1-2b3c-4d5e-6f7a-8b9c0d1e2f3a"
      rule_name: "APT29 Infrastructure Beacon"
      confidence: "high"
"""

    yaml_view = mo.md(f"""
**FRANK API Response**

```yaml
{yaml_response}
```
    """)

    # Tabbed interface
    mo.vstack([
        mo.md("---\n### Results"),
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
                              ┌─────────────┐
                              │    FRANK    │
                              │   Central   │
                              └──────┬──────┘
                                     │
             ┌───────────────────────┼───────────────────────┐
             │                       │                       │
        ┌────▼────┐             ┌────▼────┐             ┌────▼────┐
        │  Bank   │             │Insurance│             │  Port   │
        │  Alpha  │             │  Beta   │             │Rotterdam│
        │(Finance)│             │(Finance)│             │(Logist.)│
        └─────────┘             └─────────┘             └─────────┘
             ▲                       ▲                       ▲
             │                       │                       │
          Sighting               Sighting                Sighting
          02:15 UTC              03:42 UTC               04:10 UTC

    Your query → FRANK aggregates → You see: 3 orgs, 2 sectors
    ```

    ---
    [← Back to Scenarios](/) · [Next: Evolving Case →](/s2)

    <div style="text-align: center; margin-top: 40px; padding: 20px; border-top: 1px solid #ddd;">
    <strong>FRANK — Threat Intelligence Sharing</strong><br>
    <small>Schuberg Philis · SBIR Grant SB1CD24006</small>
    </div>
    """)
    return


if __name__ == "__main__":
    app.run()
