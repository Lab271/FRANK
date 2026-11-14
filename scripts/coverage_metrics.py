"""Test coverage from cargo llvm-cov (ADR-023): reads target/assurance/coverage.json, written by `make coverage`.

    cargo llvm-cov --workspace --locked --json --summary-only --output-path target/assurance/coverage.json

The file is llvm-cov's export: data[0].totals and data[0].files[].summary, each with
lines, functions and regions as {count, covered, percent}.
"""

import json
from pathlib import Path

KINDS = ("lines", "functions", "regions")


def read(path, root):
    """{totals: {kind: (covered, count)}, files: [(relative file, covered lines, lines)]}."""
    doc = json.loads(Path(path).read_text())
    if doc.get("type") != "llvm.coverage.json.export" or not doc.get("data"):
        raise ValueError(f"{path}: not an llvm-cov JSON export; run make coverage")
    data = doc["data"][0]
    totals = {k: (data["totals"][k]["covered"], data["totals"][k]["count"]) for k in KINDS}
    root = Path(root).resolve()
    files = []
    for f in data["files"]:
        name = Path(f["filename"]).resolve()
        if name.is_relative_to(root):
            name = name.relative_to(root)
        lines = f["summary"]["lines"]
        files.append((str(name), lines["covered"], lines["count"]))
    return {"totals": totals, "files": files}


def least_covered(files, top=5):
    """The files with the lowest share of lines covered; files without lines are left out."""
    measured = [f for f in files if f[2]]
    return sorted(measured, key=lambda f: (f[1] / f[2], -f[2], f[0]))[:top]
