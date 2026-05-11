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

    ## What is FRANK?

    FRANK is a threat intelligence sharing platform that enables Dutch organizations
    to collectively defend against cyber threats. Built by Schuberg Philis as part of
    the SBIR cybersecurity innovation program (SB1CD24006), FRANK creates a trusted
    network where MDR providers, critical infrastructure operators, and government
    agencies can share threat indicators without exposing sensitive customer data.

    **The core principle:** When one organization detects a threat, all organizations
    benefit. No commercial middleman. Pure reciprocity.

    ---

    ## How FRANK Works

    When an MDR analyst detects a threat indicator, they submit a **sighting** to FRANK:

    ```yaml
    # FRANK Sighting Submission (minimal format)
    submission:
      submitter:
        organisation_id: "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff"
        access_level: "partner"

      sighting:
        sighting_id: "sighting-ee20065d-2555-424f-ad9e-0f8428623c75"
        timestamp: "2026-05-05T02:15:00Z"
        confidence: 87

        observables:
          network:
            - type: "ipv4"
              value: "185.220.102.45"
            - type: "domain"
              value: "secure-bank-verify.nl"
    ```

    FRANK **anonymizes** and **aggregates** this with sightings from other organizations:

    ```yaml
    # FRANK Aggregated Response
    query_result:
      observable: "185.220.102.45"
      total_sightings: 3
      unique_organisations: 2
      sectors_affected:
        - "financial_services"
        - "logistics"
      first_seen: "2026-05-04T14:00:00Z"
      last_seen: "2026-05-05T02:15:00Z"
      trend: "increasing"
      sigma_matches:
        - rule_id: "NDN-2026-0847"
          rule_name: "APT29 Infrastructure Beacon"
          confidence: "high"
    ```

    **What's shared:** Observable, sector, timestamp, confidence, SIGMA matches.
    **What's NOT shared:** Customer identity, source IPs, raw logs, PII.

    ---

    ## Demo Scenarios

    These five scenarios demonstrate FRANK's value in real-world situations.
    Each scenario has interactive elements — configure, input data, and see results.

    ---

    ### 🚨 [Scenario 1: Active Incident](/s1)

    **"Is this happening elsewhere?"**

    It's 2 AM. Your SOC detected a suspicious IP beaconing from a customer network.
    Before triggering a full incident response, you need to know: is this an isolated
    attack or part of a broader campaign? Query FRANK to get instant context from
    the collective network.

    ---

    ### 🔍 [Scenario 2: Evolving Case](/s2)

    **"The investigation grows"**

    A phishing email led to malware, which led to C2 traffic. You now have three
    observables: IP, hash, domain. As you submit each one to FRANK, you receive
    enrichment from the community — some indicators are already known, others are
    new contributions from your investigation.

    ---

    ### 📦 [Scenario 3: Supply Chain Attack](/s3)

    **Axios npm compromise — March 2026**

    A widely-used npm package was compromised with a RAT. 100 million weekly downloads.
    18-hour exposure window. FRANK aggregated detection patterns from multiple organizations
    and generated SIGMA rules — available 6 hours before the official takedown.

    ---

    ### 🔄 [Scenario 4: NDN Exchange](/s4)

    **Government ↔ Private Sector**

    The Dutch government pushes APT indicators via the Nationaal Detectie Netwerk (NDN).
    FRANK matches them against MDR telemetry from 35 customers. Anonymized confirmations
    flow back. Government gets ground-truth validation. Private sector gets early warning.
    Both win.

    ---

    ### 📊 [Scenario 5: Information Economy](/s5)

    **The Network Effect Dashboard**

    FRANK isn't a product — it's a network effect. This dashboard shows the health of
    the ecosystem: participating organizations, shared sightings, SIGMA rules, and the
    measurable value created through collective defense.

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
    │   │     NDN      │◀────────────────────────▶│  FRANK-GOV   │        │
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
