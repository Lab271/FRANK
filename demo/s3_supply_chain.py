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

    mo.md(f"""
    ---
    ### Scan Results

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
    ### Recommended Actions

    1. **Customer 12:** Initiate incident response — RAT callback detected
    2. **Customer 3, 19:** Force package update, scan for lateral movement
    3. **All:** Deploy SIGMA rule from FRANK network

    ```yaml
    title: Axios NPM Supply Chain RAT Callback
    detection:
      selection:
        c-uri|contains: ['/api/heartbeat', '/api/upload']
        cs-method: POST
      condition: selection
    ```
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ---
    [← Back to Scenarios](./)
    """)
    return


if __name__ == "__main__":
    app.run()
