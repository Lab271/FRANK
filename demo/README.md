# FRANK Demo — SBIR RVO Presentation (May 13, 2026)

## Overview

Interactive demo for RVO showcasing FRANK's threat intelligence sharing capabilities.
Built with Marimo for reactive Python-based presentation.

## Demo Scenarios

| # | Scenario | Topology | Shows |
|---|----------|----------|-------|
| 1 | Active Incident | Single MDR → FRANK | Speed: "Is this happening elsewhere?" |
| 2 | Evolving Case | Single MDR → FRANK | Enrichment: Multi-observable correlation |
| 3 | Supply Chain | Single MDR → FRANK | Scanning: Exfiltration pattern lookup |
| 4 | Cyclotron Loop | FRANK ↔ FRANK | Bidirectional: Government-private exchange |
| 5 | Information Economy | Multi-FRANK | Network: Public dashboard, value metrics |

## Architecture

```
Scenarios 1-3: Internal (SBP MDR customers)
┌─────────────────────────────────────────────┐
│                  FRANK                       │
│              (Central Hub)                   │
│                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │Customer │  │Customer │  │Customer │     │
│  │MDR #1   │  │MDR #2   │  │MDR #3   │     │
│  └────┬────┘  └────┬────┘  └────┬────┘     │
│       │            │            │          │
│       └────────────┴────────────┘          │
│                    │                        │
│              [Query/Submit]                 │
└─────────────────────────────────────────────┘

Scenario 4: Cross-organization (SBP ↔ Partner)
┌──────────────┐         ┌──────────────┐
│  FRANK-SBP   │◄───────►│ FRANK-Partner│
│              │  Sync   │              │
│  ┌────────┐  │         │  ┌────────┐  │
│  │SBP MDRs│  │         │  │Partner │  │
│  └────────┘  │         │  │ MDRs   │  │
└──────────────┘         └──────────────┘

Scenario 5: Public Network (Information Economy)
┌──────────────────────────────────────────────────┐
│                 FRANK Network                     │
│                                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │FRANK-SBP│  │FRANK-X  │  │FRANK-Y  │  ...    │
│  └────┬────┘  └────┬────┘  └────┬────┘         │
│       │            │            │               │
│       └────────────┴────────────┘               │
│                    │                            │
│            [Aggregated Stats]                   │
│            [Sector Breakdown]                   │
│            [Value Attribution]                  │
└──────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Start FRANK backend (from FRANK root)
cd environments/local-docker
make stage3

# 2. Start demo app (separate terminal)
cd demo
uv run marimo run app.py

# 3. Open browser
open http://localhost:2718
```

## Files

```
demo/
├── README.md           # This file
├── app.py              # Main Marimo app (entry point)
├── scenarios/          # Scenario-specific logic
│   ├── __init__.py
│   ├── s1_active_incident.py
│   ├── s2_evolving_case.py
│   ├── s3_supply_chain.py
│   ├── s4_cyclotron.py
│   └── s5_dashboard.py
├── components/         # Reusable UI components
│   ├── __init__.py
│   ├── ioc_input.py
│   ├── results_panel.py
│   └── topology_graph.py
├── data/               # Demo seed data
│   ├── seed_sightings.json
│   └── march_iocs.json
└── client.py           # FRANK API client
```

## Demo Data

### Scenario 3: March 2026 Supply Chain Attack (Axios)

IoCs for supply chain demo:
- npm package: `axios@1.14.1`, `axios@0.30.4`
- C2 domains: (from briefing)
- Exfil patterns: HTTP POST to `/api/upload`

### Scenario 4: Cyclotron Exchange

Simulated SIGMA rules from government feed:
- APT29 infrastructure indicators
- Ransomware C2 patterns

## Development

```bash
# Install demo dependencies
cd demo
uv pip install marimo plotly httpx

# Run in edit mode (for development)
uv run marimo edit app.py

# Run in presentation mode
uv run marimo run app.py --headless --port 2718
```

## RVO Presentation Flow

1. **Open** — Dashboard view (Scenario 5) showing network health
2. **Scenario 1** — Live: paste IP, show instant lookup
3. **Scenario 2** — Story: case evolves, show correlation
4. **Scenario 3** — Story: Axios attack, show exfil detection
5. **Scenario 4** — Story: receive from Cyclotron, contribute back
6. **Close** — Return to dashboard, show value created

Total runtime: ~15 minutes with Q&A.
