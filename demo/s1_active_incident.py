#!/usr/bin/env python3
"""
Scenario 1: Active Incident — "Is this happening elsewhere?"

It's 2 AM. Your SOC just found a malicious IP in customer logs.
The incident is LIVE. You need to know NOW if this is isolated or widespread.

Run with: marimo run s1_active_incident.py
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
    # Scenario 1: Active Incident

    ## "Is this happening elsewhere?"

    **The situation:** It's 2 AM. Your SOC just found a malicious IP in customer logs.
    The incident is **LIVE**. Adrenaline high. You need to know NOW:

    > Is this an isolated attack, or is it hitting others too?

    ---
    """)
    return


@app.cell
def _(mo):
    ioc_input = mo.ui.text(
        value="185.234.72.14",
        placeholder="Enter IP, hash, or domain...",
        label="🔍 IoC to check",
        full_width=True
    )
    return (ioc_input,)


@app.cell
def _(mo, ioc_input):
    mo.hstack([
        ioc_input,
        mo.ui.button(label="Check FRANK", kind="success", value=True)
    ], justify="start", gap=1)
    return


@app.cell
def _(mo, ioc_input):
    # Query FRANK API
    ioc_value = ioc_input.value or "185.234.72.14"

    # TODO: Replace with actual API call
    # response = httpx.get(f"http://localhost:8000/api/v1/sightings/search?observable={ioc_value}")

    # Mock response for demo
    mock_result = {
        "ioc": ioc_value,
        "seen_by": 3,
        "sectors": ["Finance", "Finance", "Logistics"],
        "first_seen": "2h ago",
        "trend": "increasing",
        "your_org_first": False,
        "confidence_avg": 0.90
    }

    unique_sectors = list(set(mock_result['sectors']))

    mo.md(f"""
    ## Results for `{mock_result['ioc']}`

    | Metric | Value |
    |--------|-------|
    | **Organizations reporting** | {mock_result['seen_by']} |
    | **Sectors affected** | {', '.join(unique_sectors)} |
    | **First seen in network** | {mock_result['first_seen']} |
    | **Trend** | ↑ {mock_result['trend']} |
    | **Average confidence** | {mock_result['confidence_avg']:.0%} |
    | **You are first reporter** | {'✅ Yes' if mock_result['your_org_first'] else '❌ No'} |

    ---

    ### Interpretation

    🚨 **You are NOT alone.** This IoC is active across **{mock_result['seen_by']} organizations**.

    **Recommended actions:**
    1. Check shared SIGMA rules for this IoC
    2. Coordinate response with affected parties
    3. Submit additional observables you discover

    """)
    return mock_result, ioc_value, unique_sectors


@app.cell
def _(mo):
    mo.md("""
    ---

    ### Network Topology

    ```
                         ┌─────────────┐
                         │    FRANK    │
                         │   Central   │
                         └──────┬──────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
       ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
       │ Bank    │         │Insurance│         │  Port   │
       │ Alpha   │         │  Beta   │         │Rotterdam│
       │(Finance)│         │(Finance)│         │(Logist.)│
       └─────────┘         └─────────┘         └─────────┘
            ▲                   ▲                   ▲
            │                   │                   │
         Sighting            Sighting            Sighting
         02:15 UTC           03:42 UTC           04:10 UTC
    ```

    *All three organizations reported the same IoC within hours*

    ---

    [← Back to Scenarios](/)
    """)
    return


if __name__ == "__main__":
    app.run()
