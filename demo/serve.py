"""ASGI server for FRANK Demo — multi-page Marimo app.

Uses Marimo's create_asgi_app() to mount each scenario at a clean path.

Run with: make run  (or: uv run python serve.py)
"""

import base64
from pathlib import Path

import uvicorn
from marimo import create_asgi_app

APP_DIR = Path(__file__).parent
LOGO_FILE = APP_DIR / "assets" / "sbp_logo.png"

# Embed logo as base64
if LOGO_FILE.exists():
    logo_b64 = base64.b64encode(LOGO_FILE.read_bytes()).decode()
    logo_img = f'<img src="data:image/png;base64,{logo_b64}" alt="Schuberg Philis" style="height:40px">'
else:
    logo_img = "Schuberg Philis"

# CSS and HTML for branding
html_head = f"""
<style>
#sbp-logo {{
    position: fixed;
    top: 12px;
    right: 16px;
    z-index: 9999;
    opacity: 0.9;
}}
#sbp-logo:hover {{
    opacity: 1;
}}
</style>
<script>
(function () {{
    function addLogo() {{
        if (!document.body) return;
        if (document.getElementById("sbp-logo")) return;
        var div = document.createElement("div");
        div.id = "sbp-logo";
        div.innerHTML = '{logo_img}';
        document.body.appendChild(div);
    }}
    if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", addLogo);
    }} else {{
        addLogo();
    }}
    // Re-add if removed by marimo re-render
    var observer = new MutationObserver(addLogo);
    function startObserver() {{
        if (document.body) observer.observe(document.body, {{childList: true}});
        else setTimeout(startObserver, 50);
    }}
    startObserver();
}})();
</script>
"""

# Build multi-page app
marimo_app = (
    create_asgi_app(html_head=html_head)
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
