#!/usr/bin/env python3
"""
Scenario 3: Supply Chain Attack — Axios (March 2026)

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
    # Scenario 3: Supply Chain Attack

    ## Axios npm Compromise — March 31, 2026

    **The situation:** It's Monday morning. You open your threat intel feed and see
    the news: `axios`, one of the most popular npm packages with over 100 million
    weekly downloads, was compromised. Versions 1.14.1 and 0.30.4 contained a Remote
    Access Trojan (RAT) that exfiltrates environment variables and opens a backdoor.

    **The timeline:**
    - March 31, 06:00 UTC — Malicious versions published to npm
    - March 31, 24:00 UTC — npm removes the packages (18-hour window)
    - Unknown — How many of your customers pulled the bad version?

    **The problem:** You manage MDR for 35 customers. Many run Node.js applications.
    You need to know immediately:
    - Which customers have the compromised package in their dependency tree?
    - Are any of them already showing signs of RAT callback behavior?
    - What detection rules should you deploy across all customer SIEMs?

    **What FRANK provides:** The FRANK network has already aggregated intelligence
    from multiple organizations that detected this attack. You get:
    - Known indicators of compromise (callback URLs, beacon patterns)
    - A pre-built SIGMA detection rule ready to deploy
    - Cross-reference against your MDR telemetry to find exposed customers

    This is the power of collective defense — the detection rule was available
    **6 hours before npm took down the malicious packages**.

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
        "scan_scope": mo.ui.dropdown(
            options=["All 35 customers", "Critical customers only (12)", "Single customer"],
            value="All 35 customers",
            label="Scan Scope"
        ),
    })
    config
    return (config,)


@app.cell
def _(mo):
    mo.md("""
    ---
    ### Query Supply Chain IoCs
    """)
    return


@app.cell
def _(mo):
    package_input = mo.ui.text(value="axios", label="Package name")
    version_input = mo.ui.text(value="1.14.1", label="Compromised version")
    return package_input, version_input


@app.cell
def _(mo, package_input, version_input):
    scan_button = mo.ui.run_button(label="Scan Customers")
    mo.hstack([package_input, version_input, scan_button], widths=[2, 1, 1], align="end")
    return (scan_button,)


@app.cell
def _(mo, scan_button, package_input, version_input, config):
    mo.stop(not scan_button.value)

    pkg = package_input.value
    ver = version_input.value

    # Mock scan results for SBP's 35 customers
    scan_results = [
        {"customer": "Customer 3", "version": "1.14.1", "callback_detected": False, "status": "exposed"},
        {"customer": "Customer 7", "version": "1.14.0", "callback_detected": False, "status": "safe"},
        {"customer": "Customer 12", "version": "1.14.1", "callback_detected": True, "status": "compromised"},
        {"customer": "Customer 19", "version": "0.30.4", "callback_detected": False, "status": "exposed"},
        {"customer": "Customer 28", "version": "1.13.0", "callback_detected": False, "status": "safe"},
    ]

    exposed = [r for r in scan_results if r["status"] == "exposed"]
    compromised = [r for r in scan_results if r["status"] == "compromised"]
    safe = [r for r in scan_results if r["status"] == "safe"]

    # Build results table
    rows = []
    for r in scan_results:
        if r["status"] == "compromised":
            status_icon = "🚨 **Compromised**"
        elif r["status"] == "exposed":
            status_icon = "⚠️ Exposed"
        else:
            status_icon = "✅ Safe"
        callback = "Yes" if r["callback_detected"] else "No"
        rows.append(f"| {r['customer']} | {r['version']} | {callback} | {status_icon} |")

    table = "\n".join(rows)

    # Formatted results view
    formatted_view = mo.md(f"""
    **Package:** `{pkg}@{ver}` | **Scope:** {config.value['scan_scope']}

    | Customer | Version | RAT Callback | Status |
    |----------|---------|--------------|--------|
    {table}

    ---
    ### Summary

    | Category | Count |
    |----------|-------|
    | 🚨 Active compromise | {len(compromised)} |
    | ⚠️ Exposed (no callback yet) | {len(exposed)} |
    | ✅ Safe version | {len(safe)} |
    | Total scanned | {len(scan_results)} of 35 |

    ---
    ### Access Tiers

    **Your access level: `core_member`**

    As a core member, you see `target_organisation` UUIDs in the YAML response.
    Only you can link these UUIDs back to your own customers — FRANK doesn't
    know the mapping. Other members see only sector aggregates.

    ---
    ### Recommended Actions

    1. **Customer 12:** Initiate incident response — RAT callback detected
    2. **Customer 3, 19:** Force package update, scan for lateral movement
    3. **All:** Deploy SIGMA rule from FRANK network

    ```yaml
    title: Axios NPM Supply Chain RAT Callback
    id: indicator--c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f
    status: experimental
    description: |
      Detects HTTP POST requests to callback endpoints used by the
      compromised axios npm packages (1.14.1, 0.30.4) from March 2026.
    author: FRANK Network (aggregated)
    date: 2026/03/31
    references:
      - https://frank.network/campaign/campaign--7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
    logsource:
      category: proxy
    detection:
      selection:
        c-uri|contains:
          - '/api/heartbeat'
          - '/api/upload'
        cs-method: 'POST'
      filter_legitimate:
        c-uri|contains:
          - 'your-legitimate-domain.com'
      condition: selection and not filter_legitimate
    falsepositives:
      - Legitimate applications using similar endpoint patterns
    level: high
    tags:
      - attack.initial_access
      - attack.t1195.002
      - supply_chain
    ```
    """)

    # YAML response view - what FRANK actually returns
    yaml_response = f"""# FRANK API Response — Supply Chain Intelligence
frank_response:
  query:
    type: "supply_chain"
    package: "{pkg}"
    version: "{ver}"
    timestamp: "2026-03-31T12:30:00Z"

  threat_intel:
    campaign_id: "campaign--7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d"
    malware_id: "malware--b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e"
    severity: "critical"
    confidence: 95
    first_reported: "2026-03-31T08:15:00Z"
    reporters: 4
    sectors_affected:
      - "financial_services"
      - "logistics"
      - "healthcare"

  timeline:
    malicious_publish: "2026-03-31T06:00:00Z"
    frank_rule_available: "2026-03-31T12:00:00Z"
    npm_takedown: "2026-03-31T24:00:00Z"
    early_warning_hours: 12

  indicators:
    compromised_versions:
      - "1.14.1"
      - "0.30.4"
    callback_patterns:
      - "/api/heartbeat"
      - "/api/upload"
    c2_domains:
      - "cdn-analytics.net"
      - "npm-telemetry.io"
    file_hashes:
      - sha256: "a1d4e5f6c8b9a0e1d2c3b4a5f6e7d8c9b0a1e2f3..."
        version: "1.14.1"

  network_sightings:
    total_organisations: 8
    callback_detected: 3
    sectors:
      financial_services: 2
      logistics: 1

  # Access tier: core_member
  # Core members see target_organisation UUIDs (below)
  # Only the submitting MDR can link these back to their own customers
  target_sightings:
    - target_id: "identity--d4e5f6a7-8b9c-0d1e-2f3a-4b5c6d7e8f9a"
      sector: "financial_services"
      callback_detected: true
    - target_id: "identity--e5f6a7b8-9c0d-1e2f-3a4b-5c6d7e8f9a0b"
      sector: "financial_services"
      callback_detected: false
    - target_id: "identity--f6a7b8c9-0d1e-2f3a-4b5c-6d7e8f9a0b1c"
      sector: "logistics"
      callback_detected: false

  sigma_rule:
    id: "indicator--c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f"
    title: "Axios NPM Supply Chain RAT Callback"
    status: "experimental"
    author: "FRANK Network (aggregated)"
    date: "2026/03/31"
    logsource:
      category: "proxy"
    detection:
      selection:
        c-uri|contains:
          - "/api/heartbeat"
          - "/api/upload"
        cs-method: "POST"
      condition: "selection"
    level: "high"
    tags:
      - "attack.initial_access"
      - "attack.t1195.002"
"""

    yaml_view = mo.md(f"""
**FRANK API Response**

```yaml
{yaml_response}
```
    """)

    # Tabbed interface
    mo.vstack([
        mo.md("---\n### Scan Results"),
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
    ┌─────────────┐     compromised      ┌─────────────┐
    │    npm      │ ──────────────────▶  │   axios     │
    │  registry   │     versions         │  1.14.1     │
    └─────────────┘                      └──────┬──────┘
                                                │
                     ┌──────────────────────────┼──────────────┐
                     │                          │              │
                ┌────▼────┐                ┌────▼────┐    ┌────▼────┐
                │Customer │                │Customer │    │Customer │
                │    3    │                │   12    │    │   19    │
                │(exposed)│                │(comprom)│    │(exposed)│
                └─────────┘                └────┬────┘    └─────────┘
                                                │
                                           RAT callback
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │  C2 Server  │
                                         │ /api/heart  │
                                         └─────────────┘

    FRANK aggregates IoCs → Generates SIGMA rule → You scan 35 customers
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
