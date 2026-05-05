#!/usr/bin/env python3
"""
Scenario 4: Cyclotron Exchange — Government ↔ Private Sector

Bidirectional threat intelligence sharing.
Government provides context, private sector confirms with telemetry.

Run with: marimo run s4_cyclotron.py
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import json
    from datetime import datetime
    return mo, json, datetime


@app.cell
def _(mo):
    mo.md("""
    # Scenario 4: Cyclotron Feedback Loop

    ## Government ↔ Private Sector Exchange

    **The situation:** You received threat intel from Cyclotron (government intelligence platform).
    SIGMA rules for APT infrastructure targeting Dutch critical sectors.

    **The value exchange:**

    ```
    ┌──────────────┐                              ┌──────────────┐
    │   Cyclotron  │                              │    FRANK     │
    │  (Government)│                              │   (Private)  │
    └──────┬───────┘                              └──────┬───────┘
           │                                             │
           │  1. Push: Detection rules                   │
           │  ──────────────────────────────────────▶   │
           │     (APT indicators, SIGMA rules)          │
           │                                             │
           │  2. Match: Run against MDR telemetry       │
           │                                             │
           │  3. Contribute: Anonymized confirmation    │
           │  ◀──────────────────────────────────────   │
           │     (hit counts, sectors, timestamps)      │
           │                                             │
    ```

    **Both sides win:** Government gets signal. Private sector gets context.

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Incoming from Cyclotron

    Three new detection rules received this morning:

    | Rule ID | Description | Confidence | Source |
    |---------|-------------|------------|--------|
    | CYC-2026-0847 | APT29 infrastructure - beacon pattern | High | AIVD |
    | CYC-2026-0851 | Ransomware staging server | Medium | NCSC-NL |
    | CYC-2026-0855 | Credential harvesting campaign | High | Europol EC3 |

    ---

    ### Rule Details: CYC-2026-0847

    ```yaml
    title: APT29 Infrastructure - Beacon Pattern
    status: production
    confidence: high
    source: AIVD via Cyclotron
    indicators:
      - type: domain
        value: update-service.example.com
        context: C2 server masquerading as update service
      - type: ipv4
        value: 192.0.2.50
        context: Primary C2 endpoint
    detection:
      beacon_interval: 300s (±30s jitter)
      user_agent: "Mozilla/5.0 (compatible; UpdateService/1.0)"
    targets:
      - sector: government
      - sector: energy
      - sector: finance
    ```
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ---

    ## Match Results (SBP MDR Data)

    FRANK ran Cyclotron rules against SBP MDR telemetry covering 120+ customers:

    | Rule ID | Local Hits | Affected Customers | Sectors |
    |---------|------------|-------------------|---------|
    | CYC-2026-0847 | **2** | Customer X, Customer Y | Finance, Logistics |
    | CYC-2026-0851 | 0 | — | — |
    | CYC-2026-0855 | **1** | Customer Z | Energy |

    ### Hit Details: CYC-2026-0847

    | Customer | First Seen | Last Seen | Hit Count | Status |
    |----------|------------|-----------|-----------|--------|
    | Customer X (Finance) | 2026-05-05 08:23 | 2026-05-05 09:15 | 4 | 🚨 Active |
    | Customer Y (Logistics) | 2026-05-04 14:00 | 2026-05-04 14:00 | 1 | ⚠️ Single hit |

    ---
    """)
    return


@app.cell
def _(mo):
    contributed_back = {
        "rule_id": "CYC-2026-0847",
        "private_sector_hits": 2,
        "sectors_affected": ["finance", "logistics"],
        "first_seen": "2026-05-04T14:00:00Z",
        "last_seen": "2026-05-05T09:15:00Z",
        "confidence": "confirmed",
        "reporter": "FRANK-MDR-001"  # Anonymized
    }

    mo.md(f"""
    ## Contributed Back to Cyclotron (Anonymized)

    FRANK automatically generates an anonymized confirmation report:

    ```json
{json.dumps(contributed_back, indent=2)}
    ```

    **What Cyclotron receives:**
    - ✅ Confirmation that APT29 indicators are active in NL
    - ✅ Sector breakdown (without customer names)
    - ✅ Timeline (first/last seen)
    - ❌ No customer identities
    - ❌ No IP addresses
    - ❌ No sensitive telemetry

    ---

    ## Value Created

    | Party | Value Received |
    |-------|---------------|
    | **Government (Cyclotron)** | Confirmation that APT29 is active in Dutch private sector |
    | **Private sector (FRANK)** | Early warning about APT29 campaign + detection rules |
    | **Affected customers** | Immediate notification and response support |

    **This is the information economy:** Intelligence flows both ways.

    ---

    [← Back to Scenarios](/)
    """)
    return (contributed_back,)


@app.cell
def _(mo):
    mo.md("""
    ---

    ## Architecture: Two-FRANK Federation

    ```
    ┌─────────────────────────────────────────────────────────────────┐
    │                        CYCLOTRON                                │
    │                    (Government Platform)                        │
    └───────────────────────────┬─────────────────────────────────────┘
                                │
                                │ Secure API (mTLS)
                                │
    ┌───────────────────────────▼─────────────────────────────────────┐
    │                      FRANK-GOV                                  │
    │            (Government-facing FRANK instance)                   │
    │                                                                 │
    │  • Receives Cyclotron rules                                     │
    │  • Aggregates private sector confirmations                      │
    │  • Strips PII before sending back                               │
    └───────────────────────────┬─────────────────────────────────────┘
                                │
                                │ FRANK-to-FRANK sync
                                │
    ┌───────────────────────────▼─────────────────────────────────────┐
    │                      FRANK-SBP                                  │
    │              (SBP Private FRANK instance)                       │
    │                                                                 │
    │  • Receives rules from FRANK-GOV                                │
    │  • Matches against MDR telemetry                                │
    │  • Reports anonymized confirmations                             │
    └───────────────────────────┬─────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
       ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
       │Customer │         │Customer │         │Customer │
       │    X    │         │    Y    │         │    Z    │
       │(Finance)│         │(Logist.)│         │(Energy) │
       └─────────┘         └─────────┘         └─────────┘
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
