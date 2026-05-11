#!/usr/bin/env python3
"""
Scenario 5: Information Economy Dashboard

Run with: uv run python serve.py
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Scenario 5: The Information Economy

    ## FRANK Network Dashboard

    **The big picture:** FRANK is not a product you buy — it's a network you join.
    The value comes from participation, not from features.

    **How it works:**
    - Every organization that joins FRANK contributes their threat sightings
    - Every sighting enriches the collective knowledge base
    - Every participant benefits from everyone else's visibility
    - The more organizations participate, the more valuable the network becomes

    **The economics are simple:**
    - Traditional threat intel: You pay a vendor for access to their data
    - FRANK model: You contribute your data, you receive everyone's data
    - No commercial middleman extracting value — pure peer-to-peer reciprocity

    **Why this matters for the Netherlands:**
    Dutch critical infrastructure — finance, energy, logistics, healthcare — faces
    the same threats. When a bank detects an APT campaign, that intelligence should
    flow to energy companies before they're hit. When a hospital sees ransomware
    staging, logistics providers should get early warning.

    FRANK makes this possible without exposing sensitive customer data, without
    commercial incentives distorting the information flow, and without requiring
    organizations to trust each other with raw telemetry.

    **This dashboard shows the health of the ecosystem.**

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("### Configuration")
    config = mo.ui.dictionary({
        "frank_instance": mo.ui.dropdown(
            options=["FRANK-SBP (Production)", "FRANK-Central (Aggregate)"],
            value="FRANK-SBP (Production)",
            label="FRANK Instance"
        ),
        "time_range": mo.ui.dropdown(
            options=["Last 24 hours", "Last 7 days", "Last 30 days", "All time"],
            value="Last 30 days",
            label="Time Range"
        ),
    })
    config
    return (config,)


@app.cell
def _(mo, config):
    refresh_button = mo.ui.run_button(label="Refresh Dashboard")
    mo.hstack([mo.md(f"**Instance:** {config.value['frank_instance']} | **Range:** {config.value['time_range']}"), refresh_button], justify="space-between")
    return (refresh_button,)


@app.cell
def _(mo, refresh_button, config):
    # Always show stats, but update timestamp on refresh
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S") if refresh_button.value else "—"

    # SBP-specific stats (35 customers)
    stats = {
        "customers": 35,
        "participating_orgs": 12,  # in FRANK network
        "sightings_this_month": 847,
        "sigma_rules_shared": 156,
        "active_incidents": 3,
    }

    mo.hstack([
        mo.stat(value=stats["customers"], label="SBP Customers", bordered=True),
        mo.stat(value=stats["participating_orgs"], label="FRANK Orgs", bordered=True),
        mo.stat(value=stats["sightings_this_month"], label="Sightings (May)", bordered=True),
        mo.stat(value=stats["sigma_rules_shared"], label="SIGMA Rules", bordered=True),
        mo.stat(value=stats["active_incidents"], label="Active Incidents", bordered=True),
    ], justify="space-around")
    return (timestamp,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ### SBP Customer Sectors (35 total)

    | Sector | Customers | Sightings |
    |--------|-----------|-----------|
    | Finance | 12 | 312 |
    | Logistics | 8 | 245 |
    | Energy | 6 | 156 |
    | Healthcare | 5 | 78 |
    | Other | 4 | 56 |

    ---
    ### Value Created This Month

    | Impact | Count | Description |
    |--------|-------|-------------|
    | **Faster detections** | 23 | Detections enabled by shared intel |
    | **Incidents prevented** | 7 | Attacks blocked due to early warning |
    | **Analyst hours saved** | 340 | Time saved by not duplicating research |
    | **Cross-org correlations** | 12 | Attacks linked across customers |
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    ### The Reciprocity Model

    | You contribute | You receive |
    |----------------|-------------|
    | IoC sightings | Network-wide enrichment |
    | SIGMA rules | Community detection library |
    | Incident confirmations | Early warnings |
    | Anonymized telemetry | Threat landscape visibility |

    **The math:**
    - Alone: 1 org × 1 viewpoint = **1×** detection
    - FRANK (12 orgs): 12 × shared rules = **12×** detection

    > Your contributions enabled **23 faster detections** at other organizations this month.

    ---
    ### Architecture

    ```
                                ┌──────────────┐
                                │     NDN      │
                                │  (Government)│
                                └──────┬───────┘
                                       │
                          ┌────────────┴────────────┐
                          │                         │
                    ┌─────▼─────┐             ┌─────▼─────┐
                    │ FRANK-GOV │◀───────────▶│ FRANK-EU  │
                    │   (NL)    │    sync     │ (Europol) │
                    └─────┬─────┘             └───────────┘
                          │
     ┌────────────────────┼────────────────────┐
     │                    │                    │
┌────▼────┐          ┌────▼────┐          ┌────▼────┐
│FRANK-SBP│          │FRANK-KPN│          │FRANK-FOX│
│  (MDR)  │          │  (ISP)  │          │  (MDR)  │
└────┬────┘          └────┬────┘          └────┬────┘
     │                    │                    │
┌────┴────┐          ┌────┴────┐          ┌────┴────┐
│35 cust. │          │Backbone │          │ 50 cust │
│Finance, │          │telemetry│          │ Retail, │
│ Energy  │          │         │          │  Gov    │
└─────────┘          └─────────┘          └─────────┘
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
