#!/usr/bin/env python3
"""
FRANK Demo — Scenario Launcher

SBIR RVO Presentation — May 2026

Run with: marimo run index.py
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
    # FRANK — Threat Intelligence Sharing

    **Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling**

    *SBIR RVO Demo — May 2026*

    ---

    ## Demo Scenarios

    Click any scenario to explore:

    ---

    ### 🚨 [Scenario 1: Active Incident](http://localhost:2718/s1_active_incident.py)

    **"Is this happening elsewhere?"**

    It's 2 AM. Your SOC found a malicious IP. The incident is LIVE.
    Query FRANK to see if others are being hit too.

    ---

    ### 🔍 [Scenario 2: Evolving Case](http://localhost:2718/s2_evolving_case.py)

    **"The investigation grows"**

    What started as one IoC is now three. As your case develops,
    FRANK enriches each observable with community intelligence.

    ---

    ### 📦 [Scenario 3: Supply Chain Attack](http://localhost:2718/s3_supply_chain.py)

    **Axios npm compromise — March 2026**

    100 million weekly downloads. 18-hour window. FRANK helped detect
    the RAT callbacks 6 hours before npm takedown.

    ---

    ### 🔄 [Scenario 4: Cyclotron Exchange](http://localhost:2718/s4_cyclotron.py)

    **Government ↔ Private Sector**

    Bidirectional intelligence sharing. Government provides context,
    private sector confirms with telemetry. Both win.

    ---

    ### 📊 [Scenario 5: Information Economy](http://localhost:2718/s5_dashboard.py)

    **The Network Effect Dashboard**

    FRANK isn't a product — it's a network effect.
    Every participant makes every other participant safer.

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Architecture

    ```
    ┌─────────────────────────────────────────────────────────────────────┐
    │                         FRANK ECOSYSTEM                             │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   ┌──────────────┐                          ┌──────────────┐        │
    │   │   CYCLOTRON  │◀────────────────────────▶│  FRANK-GOV   │        │
    │   │ (Government) │    Secure Exchange       │   (Bridge)   │        │
    │   └──────────────┘                          └──────┬───────┘        │
    │                                                    │                │
    │                            ┌───────────────────────┼──────────┐     │
    │                            │                       │          │     │
    │                       ┌────▼────┐            ┌─────▼────┐     │     │
    │                       │FRANK-SBP│◀──────────▶│FRANK-KPN │     │     │
    │                       │  (MDR)  │   Sync     │  (ISP)   │     │     │
    │                       └────┬────┘            └──────────┘     │     │
    │                            │                                  │     │
    │                 ┌──────────┼──────────┐                       │     │
    │                 │          │          │                       │     │
    │            ┌────▼───┐ ┌────▼───┐ ┌────▼───┐                   │     │
    │            │Customer│ │Customer│ │Customer│                   │     │
    │            │   A    │ │   B    │ │   C    │                   │     │
    │            │(MDR)   │ │(MDR)   │ │(MDR)   │                   │     │
    │            └────────┘ └────────┘ └────────┘                   │     │
    │                                                               │     │
    └───────────────────────────────────────────────────────────────┴─────┘
    ```

    ---

    ## Quick Start

    ```bash
    # Start FRANK instances
    cd demo
    docker compose up -d

    # Run demo launcher
    marimo run index.py --host 0.0.0.0 --port 2718

    # Access at http://localhost:2718
    ```

    ---

    *Schuberg Philis — SBIR Grant SB1CD24006*
    """)
    return


if __name__ == "__main__":
    app.run()
