#!/usr/bin/env python3
"""
Scenario 5: Information Economy Dashboard

FRANK isn't a product — it's a network effect.
Every participant makes every other participant safer.

Run with: marimo run s5_dashboard.py
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import plotly.express as px
    import plotly.graph_objects as go
    import pandas as pd
    from datetime import datetime, timedelta
    return mo, px, go, pd, datetime, timedelta


@app.cell
def _(mo):
    mo.md("""
    # Scenario 5: The Information Economy

    ## FRANK Network Dashboard

    **The big picture:** FRANK isn't a product — it's a **network effect**.

    Every participant makes every other participant safer.
    No commercial incentive. Pure reciprocity.

    ---
    """)
    return


@app.cell
def _(mo):
    # Network statistics
    stats = {
        "organizations": 12,
        "sightings_this_month": 847,
        "sigma_rules_shared": 156,
        "active_incidents": 3,
        "avg_response_time_h": 2.3,
    }

    mo.hstack([
        mo.stat(value=stats["organizations"], label="Organizations", bordered=True),
        mo.stat(value=stats["sightings_this_month"], label="Sightings (May)", bordered=True),
        mo.stat(value=stats["sigma_rules_shared"], label="SIGMA Rules", bordered=True),
        mo.stat(value=stats["active_incidents"], label="Active Incidents", bordered=True),
        mo.stat(value=f"{stats['avg_response_time_h']}h", label="Avg Response", bordered=True),
    ], justify="space-around")
    return (stats,)


@app.cell
def _(mo, pd, px):
    # Sector breakdown
    sector_data = pd.DataFrame({
        "Sector": ["Finance", "Logistics", "Energy", "Healthcare", "IT Services"],
        "Organizations": [5, 3, 2, 1, 1],
        "Sightings": [312, 245, 156, 78, 56]
    })

    fig_sectors = px.bar(
        sector_data,
        x="Sector",
        y="Organizations",
        color="Sightings",
        title="Participating Organizations by Sector",
        color_continuous_scale="Blues"
    )
    fig_sectors.update_layout(height=300)

    mo.ui.plotly(fig_sectors)
    return sector_data, fig_sectors


@app.cell
def _(mo, pd, px):
    # Monthly trend
    trend_data = pd.DataFrame({
        "Month": ["Feb 2026", "Mar 2026", "Apr 2026", "May 2026"],
        "Sightings": [523, 712, 891, 847],
        "New Organizations": [2, 3, 2, 1],
        "SIGMA Rules": [98, 124, 145, 156]
    })

    fig_trend = px.line(
        trend_data,
        x="Month",
        y=["Sightings", "SIGMA Rules"],
        title="Network Growth Trend",
        markers=True
    )
    fig_trend.update_layout(height=300)

    mo.ui.plotly(fig_trend)
    return trend_data, fig_trend


@app.cell
def _(mo):
    mo.md("""
    ---

    ## Value Created This Month

    | Impact Metric | Count | Description |
    |--------------|-------|-------------|
    | **Faster detections enabled** | 23 | Detections that happened faster because of shared intel |
    | **Incidents prevented** | 7 | Attacks blocked before damage due to early warning |
    | **Analyst hours saved** | 340 | Time saved by not duplicating threat research |
    | **Cross-sector correlations** | 12 | Attacks linked across different industries |

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Network Topology

    ```
                                    ┌──────────────┐
                                    │   CYCLOTRON  │
                                    │  (Government)│
                                    └──────┬───────┘
                                           │
                              ┌────────────┴────────────┐
                              │                         │
                        ┌─────▼─────┐             ┌─────▼─────┐
                        │ FRANK-GOV │◀───────────▶│ FRANK-EU  │
                        │   (NL)    │   sync      │(Europol)  │
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
    │120+ cust│          │Backbone │          │ 80+ cust│
    │(Finance,│          │telemetry│          │(Retail, │
    │ Energy) │          │         │          │ Gov)    │
    └─────────┘          └─────────┘          └─────────┘
    ```

    **Network effects:**
    - Every new participant adds visibility
    - Shared rules multiply detection capability
    - Cross-sector correlation reveals campaign scope

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## The Reciprocity Model

    FRANK operates on **pure reciprocity** — no commercial incentive:

    | What you contribute | What you receive |
    |--------------------|-----------------|
    | IoC sightings | Network-wide IoC enrichment |
    | SIGMA rules | Community detection library |
    | Incident confirmations | Early warnings from others |
    | Anonymized telemetry | Threat landscape visibility |

    ### The Math

    - **Alone:** 1 organization × 1 viewpoint = 1× detection capability
    - **FRANK (12 orgs):** 12 organizations × shared rules = **12×** detection capability
    - **FRANK (100 orgs):** 100 organizations × shared rules = **100×** detection capability

    > **This is the information economy.**
    > Your contribution enabled **23 faster detections** at other organizations this month.

    ---

    [← Back to Scenarios](/)
    """)
    return


if __name__ == "__main__":
    app.run()
