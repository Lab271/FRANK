"""ASGI server for FRANK Demo — multi-page Marimo app.

Uses Marimo's create_asgi_app() to mount each scenario at a clean path.

Run with: make run  (or: uv run python serve.py)
"""

from pathlib import Path

import uvicorn
from marimo import create_asgi_app

APP_DIR = Path(__file__).parent

# Build multi-page app
marimo_app = (
    create_asgi_app()
    .with_app(path="/", root=str(APP_DIR / "index.py"))
    .with_app(path="/s1", root=str(APP_DIR / "s1_active_incident.py"))
    .with_app(path="/s2", root=str(APP_DIR / "s2_evolving_case.py"))
    .with_app(path="/s3", root=str(APP_DIR / "s3_supply_chain.py"))
    .with_app(path="/s4", root=str(APP_DIR / "s4_cyclotron.py"))
    .with_app(path="/s5", root=str(APP_DIR / "s5_dashboard.py"))
).build()

if __name__ == "__main__":
    print("\n  FRANK Demo — SBIR RVO May 2026")
    print("  ================================")
    print("  http://localhost:2718/     — Launcher")
    print("  http://localhost:2718/s1   — Active Incident")
    print("  http://localhost:2718/s2   — Evolving Case")
    print("  http://localhost:2718/s3   — Supply Chain (Axios)")
    print("  http://localhost:2718/s4   — Cyclotron Exchange")
    print("  http://localhost:2718/s5   — Information Economy")
    print()
    uvicorn.run(marimo_app, host="0.0.0.0", port=2718)
