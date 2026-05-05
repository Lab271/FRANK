#!/usr/bin/env python3
"""
Scenario 3: Supply Chain Attack — Axios (March 2026)

npm package `axios` was compromised. 100 million weekly downloads.
18-hour window. FRANK helps you assess exposure and detect callbacks.

Run with: marimo run s3_supply_chain.py
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
    # Scenario 3: Supply Chain Attack

    ## Axios npm Compromise — March 31, 2026

    **The situation:** npm package `axios` was compromised by TeamPCP threat actor.

    - **Affected versions:** `axios@1.14.1`, `axios@0.30.4`
    - **Weekly downloads:** 100 million+
    - **Exposure window:** 18 hours
    - **Payload:** Remote Access Trojan (RAT)

    **You need to know:**
    1. Did any of our customers pull the bad version?
    2. What are the exfiltration patterns to scan for?

    ---
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Known IoCs from FRANK Network

    The FRANK network has aggregated intelligence from **47 organizations** that detected this attack:

    | Type | Value | Seen by |
    |------|-------|---------|
    | npm package | `axios@1.14.1` | 47 orgs |
    | npm package | `axios@0.30.4` | 23 orgs |
    | C2 callback | `POST /api/heartbeat` | 12 orgs |
    | Exfil pattern | `POST /api/upload` | 8 orgs |
    | RAT beacon | every 60s to port 8443 | 8 orgs |

    ---

    ## Detection Pattern

    Based on community intelligence, FRANK generated this detection rule:
    """)
    return


@app.cell
def _(mo):
    sigma_rule = """title: Axios NPM Supply Chain RAT Callback
status: experimental
description: Detects Axios supply chain RAT callback patterns (March 2026)
author: FRANK Network (auto-generated)
date: 2026/03/31
references:
    - https://frank.example.com/case/axios-2026-03
logsource:
    category: proxy
detection:
    selection_uri:
        c-uri|contains:
            - '/api/heartbeat'
            - '/api/upload'
    selection_method:
        cs-method: POST
    selection_port:
        dst_port: 8443
    condition: selection_uri and selection_method
    # OR: selection_port for beacon detection
falsepositives:
    - Legitimate heartbeat APIs (verify endpoint ownership)
level: high
tags:
    - attack.command_and_control
    - attack.exfiltration
    - supply_chain.npm"""

    mo.md(f"""
    ```yaml
{sigma_rule}
    ```
    """)
    return (sigma_rule,)


@app.cell
def _(mo):
    mo.md("""
    ---

    ## Your Customer Exposure

    FRANK cross-referenced the IoCs against SBP MDR telemetry:

    | Customer | Axios Version | RAT Callback Detected | Status |
    |----------|---------------|----------------------|--------|
    | Customer A | 1.14.1 | ❌ No | ⚠️ Exposed, no callback yet |
    | Customer B | 1.14.0 | — | ✅ Safe version |
    | Customer C | 1.14.1 | ✅ Yes (3 hits) | 🚨 **Active compromise** |
    | Customer D | 0.30.4 | ❌ No | ⚠️ Exposed, no callback yet |

    ---

    ## Recommended Actions

    1. **Immediate:** Deploy SIGMA rule to all customer SIEMs
    2. **Customer C:** Initiate incident response — RAT is active
    3. **Customer A, D:** Verify package.json, rebuild without compromised version
    4. **All:** Block port 8443 outbound to unknown destinations

    ---

    ## Timeline

    ```
    Mar 31 06:00 UTC — Compromised versions published to npm
         │
         ├── 08:00 — First FRANK sighting (org: logistics-1)
         │
         ├── 12:00 — Pattern aggregated, SIGMA rule generated
         │
         ├── 14:00 — Rule deployed to SBP MDR customers
         │
         ├── 18:00 — npm takes down malicious versions
         │
    Mar 31 24:00 UTC — 47 organizations reporting via FRANK
    ```

    **FRANK value:** Detection rule available **6 hours before npm takedown**

    ---

    [← Back to Scenarios](/)
    """)
    return


if __name__ == "__main__":
    app.run()
