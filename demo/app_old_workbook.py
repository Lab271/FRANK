#!/usr/bin/env python3
"""
FRANK Demo — SBIR RVO Presentation
Marimo app for interactive threat intelligence demo.

Run with: marimo run app.py
Edit with: marimo edit app.py
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
    # ============================================================
    # HEADER & SCENARIO SELECTOR
    # ============================================================

    mo.md("""
    # FRANK — Threat Intelligence Sharing

    **Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling**

    *SBIR Demo — May 2026*
    """)
    return


@app.cell
def _(mo):
    scenarios = {
        "1. Active Incident": "active_incident",
        "2. Evolving Case": "evolving_case",
        "3. Supply Chain (Axios)": "supply_chain",
        "4. Cyclotron Exchange": "cyclotron",
        "5. Information Economy": "dashboard",
    }

    scenario_selector = mo.ui.dropdown(
        options=list(scenarios.keys()),
        value="5. Information Economy",
        label="Select Scenario"
    )

    scenario_selector
    return scenario_selector, scenarios


@app.cell
def _(mo, scenario_selector, scenarios):
    # ============================================================
    # SCENARIO STORIES
    # ============================================================

    stories = {
        "active_incident": """
        ## Scenario 1: "Is this happening elsewhere?"

        **The situation:** It's 2 AM. Your SOC just found a malicious IP in customer logs.
        The incident is **LIVE**. Adrenaline high. You need to know NOW:

        > Is this an isolated attack, or is it hitting others too?

        **Enter the IoC below and check FRANK.**
        """,

        "evolving_case": """
        ## Scenario 2: "The case is evolving"

        **The situation:** What started as a suspicious email is now a full investigation.
        You've collected:

        - Attack source IP
        - Malware binary (Proton variant)
        - C2 domain

        As the case develops, FRANK enriches each observable with community intelligence.

        **Submit your findings. See what the network knows.**
        """,

        "supply_chain": """
        ## Scenario 3: Supply Chain Attack — Axios (March 2026)

        **The situation:** npm package `axios` was compromised. Versions 1.14.1 and 0.30.4
        contained a RAT. 100 million weekly downloads. 18-hour window.

        **You need to know:**
        - Did any of our customers pull the bad version?
        - What are the exfiltration patterns to scan for?

        **Query FRANK for known IoCs and detection patterns.**
        """,

        "cyclotron": """
        ## Scenario 4: Cyclotron Feedback Loop

        **The situation:** You received threat intel from Cyclotron (government).
        SIGMA rules for APT infrastructure.

        **Two-way exchange:**
        1. Import Cyclotron rules into FRANK
        2. Match against your MDR data
        3. Contribute anonymized stats back

        **Private sector confirms, government gets signal. Both win.**
        """,

        "dashboard": """
        ## Scenario 5: The Information Economy

        **The big picture:** FRANK isn't a product — it's a network effect.

        Every participant makes every other participant safer.
        No commercial incentive. Pure reciprocity.

        **This dashboard shows the ecosystem health.**
        """,
    }

    selected = scenarios.get(scenario_selector.value, "dashboard")
    mo.md(stories.get(selected, ""))
    return (selected,)


@app.cell
def _(mo, selected):
    # ============================================================
    # SCENARIO 1: ACTIVE INCIDENT
    # ============================================================

    if selected == "active_incident":
        ioc_input = mo.ui.text(
            placeholder="Enter IP, hash, or domain...",
            label="IoC to check",
            full_width=True
        )
        check_button = mo.ui.button(label="Check FRANK", kind="success")

        mo.vstack([
            ioc_input,
            check_button,
        ])
    else:
        ioc_input = None
        check_button = None
    return check_button, ioc_input


@app.cell
def _(check_button, ioc_input, mo, selected):
    # Results for Scenario 1

    if selected == "active_incident" and check_button is not None and check_button.value:
        # TODO: Replace with actual FRANK API call
        ioc_value = ioc_input.value if ioc_input else "185.234.72.14"

        # Mock response
        mock_result = {
            "ioc": ioc_value,
            "seen_by": 3,
            "sectors": ["Finance", "Finance", "Logistics"],
            "first_seen": "2h ago",
            "trend": "increasing",
            "your_org_first": False
        }

        mo.md(f"""
        ### Results for `{mock_result['ioc']}`

        | Metric | Value |
        |--------|-------|
        | **Organizations seen** | {mock_result['seen_by']} |
        | **Sectors affected** | {', '.join(set(mock_result['sectors']))} |
        | **First seen** | {mock_result['first_seen']} |
        | **Trend** | ↑ {mock_result['trend']} |
        | **You are first reporter** | {'Yes' if mock_result['your_org_first'] else 'No'} |

        > **Interpretation:** You are NOT alone. This IoC is active across {mock_result['seen_by']} organizations.
        > Coordinate response. Check shared SIGMA rules.
        """)
    elif selected == "active_incident":
        mo.md("*Enter an IoC and click 'Check FRANK' to query the network.*")
    return


@app.cell
def _(mo, selected):
    # ============================================================
    # SCENARIO 2: EVOLVING CASE
    # ============================================================

    if selected == "evolving_case":
        mo.md("""
        ### Submit Investigation Findings

        As your investigation progresses, submit each observable:
        """)

        attack_ip = mo.ui.text(placeholder="Attack source IP", label="Source IP")
        malware_hash = mo.ui.text(placeholder="SHA256 hash", label="Malware hash")
        c2_domain = mo.ui.text(placeholder="C2 domain", label="C2 Domain")
        submit_btn = mo.ui.button(label="Submit to FRANK", kind="success")

        mo.vstack([
            attack_ip,
            malware_hash,
            c2_domain,
            submit_btn
        ])
    return


@app.cell
def _(mo, selected):
    # ============================================================
    # SCENARIO 3: SUPPLY CHAIN
    # ============================================================

    if selected == "supply_chain":
        mo.md("""
        ### Axios Supply Chain Attack (March 31, 2026)

        **Compromised packages:**
        - `axios@1.14.1`
        - `axios@0.30.4`

        **Known IoCs from FRANK network:**

        | Type | Value | Seen by |
        |------|-------|---------|
        | npm package | `axios@1.14.1` | 47 orgs |
        | npm package | `axios@0.30.4` | 23 orgs |
        | C2 callback | `POST /api/heartbeat` | 12 orgs |
        | Exfil pattern | `POST /api/upload` | 8 orgs |
        | RAT beacon | every 60s to port 8443 | 8 orgs |

        **Generated SIGMA rule:**
        ```yaml
        title: Axios NPM Supply Chain RAT Callback
        status: experimental
        logsource:
            category: proxy
        detection:
            selection:
                c-uri|contains:
                    - '/api/heartbeat'
                    - '/api/upload'
                cs-method: POST
            condition: selection
        ```

        **Action:** Deploy this SIGMA rule to all customer SIEMs.
        """)
    return


@app.cell
def _(mo, selected):
    # ============================================================
    # SCENARIO 4: CYCLOTRON
    # ============================================================

    if selected == "cyclotron":
        mo.md("""
        ### Cyclotron ↔ FRANK Exchange

        **Incoming from Cyclotron:**

        | Rule ID | Description | Confidence |
        |---------|-------------|------------|
        | CYC-2026-0847 | APT29 infrastructure | High |
        | CYC-2026-0851 | Ransomware staging | Medium |
        | CYC-2026-0855 | Credential harvesting | High |

        **Matched against SBP MDR data:**

        | Rule ID | Local hits | Affected customers |
        |---------|------------|-------------------|
        | CYC-2026-0847 | 2 | Finance, Logistics |
        | CYC-2026-0851 | 0 | — |
        | CYC-2026-0855 | 1 | Energy |

        **Contributed back to Cyclotron (anonymized):**

        ```json
        {
          "rule_id": "CYC-2026-0847",
          "private_sector_hits": 2,
          "sectors_affected": ["finance", "logistics"],
          "first_seen": "2026-05-05T08:23:00Z",
          "confidence": "confirmed"
        }
        ```

        > **Value:** Government gets signal. Private sector gets context. Both win.
        """)
    return


@app.cell
def _(mo, selected):
    # ============================================================
    # SCENARIO 5: DASHBOARD
    # ============================================================

    if selected == "dashboard":
        # Mock statistics
        stats = {
            "organizations": 12,
            "sightings_this_month": 847,
            "sigma_rules_shared": 156,
            "sectors": {
                "Finance": 5,
                "Logistics": 3,
                "Energy": 2,
                "Healthcare": 1,
                "Other": 1
            },
            "value_created": {
                "faster_detections": 23,
                "prevented_incidents": 7,
                "hours_saved": 340
            }
        }

        mo.md(f"""
        ### FRANK Network Health

        | Metric | Value |
        |--------|-------|
        | **Participating organizations** | {stats['organizations']} |
        | **Sightings shared this month** | {stats['sightings_this_month']} |
        | **SIGMA rules in network** | {stats['sigma_rules_shared']} |

        ### Sector Breakdown

        | Sector | Organizations |
        |--------|---------------|
        | Finance | {stats['sectors']['Finance']} |
        | Logistics | {stats['sectors']['Logistics']} |
        | Energy | {stats['sectors']['Energy']} |
        | Healthcare | {stats['sectors']['Healthcare']} |
        | Other | {stats['sectors']['Other']} |

        ### Value Created

        | Impact | Count |
        |--------|-------|
        | Faster detections enabled | {stats['value_created']['faster_detections']} |
        | Incidents prevented | {stats['value_created']['prevented_incidents']} |
        | Analyst hours saved | {stats['value_created']['hours_saved']} |

        > **The network effect:** Your contribution enabled {stats['value_created']['faster_detections']}
        > faster detections at other organizations this month.
        """)
    return


@app.cell
def _(mo):
    # ============================================================
    # TOPOLOGY VISUALIZATION
    # ============================================================

    # TODO: Add plotly/altair graph showing network topology
    # Different for each scenario:
    # - S1-3: Single FRANK, multiple MDRs
    # - S4: Two FRANKs with sync arrows
    # - S5: Multiple FRANKs in mesh

    mo.md("""
    ---
    *Topology visualization placeholder — will show interactive network graph*
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
 
    """)
    return


if __name__ == "__main__":
    app.run()
