#!/usr/bin/env python3
"""FRANK's version: one number in five places, checked and bumped together.

    Cargo.toml        [workspace.package] version (the source; the Makefile's VERSION)
    Cargo.lock        the workspace crates frank, frank-core, frank-wasm
    fuzz/Cargo.lock   frank-core
    README.md         ## Version: X.Y.Z
    CHANGELOG.md      the newest ## [X.Y.Z] section

Usage:
    scripts/version.py                  show the version; exit 1 if a place disagrees
    scripts/version.py --bump minor     major|minor|patch: write the next version
                                        everywhere and turn [Unreleased] into
                                        ## [X.Y.Z] - today (it must not be empty)
"""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRATES = ("frank", "frank-core", "frank-wasm")
SEMVER = r"\d+\.\d+\.\d+"


def lock_pattern():
    names = "|".join(re.escape(c) for c in CRATES)
    return re.compile(rf'(name = "(?:{names})"\nversion = ")({SEMVER})(")')


# place -> (file, pattern whose group 2 is the version)
PLACES = {
    "Cargo.toml": ("Cargo.toml", re.compile(rf'(\[workspace\.package\]\nversion = ")({SEMVER})(")')),
    "Cargo.lock": ("Cargo.lock", lock_pattern()),
    "fuzz/Cargo.lock": ("fuzz/Cargo.lock", lock_pattern()),
    "README.md": ("README.md", re.compile(rf"(^## Version: )({SEMVER})()", re.MULTILINE)),
    "CHANGELOG.md": ("CHANGELOG.md", re.compile(rf"(^## \[)({SEMVER})(\])", re.MULTILINE)),
}
UNRELEASED = re.compile(r"^## \[Unreleased\]\n(.*?)(?=^## \[)", re.MULTILINE | re.DOTALL)


def found(root=ROOT):
    """place -> the versions it holds (the changelog: only its newest section)."""
    out = {}
    for place, (file, pattern) in PLACES.items():
        text = (root / file).read_text()
        versions = [m.group(2) for m in pattern.finditer(text)]
        out[place] = versions[:1] if place == "CHANGELOG.md" else versions
    return out


def drift(root=ROOT):
    """(the version in Cargo.toml, [problems])."""
    places = found(root)
    current = (places["Cargo.toml"] or [None])[0]
    problems = []
    for place, versions in places.items():
        if not versions:
            problems.append(f"{place}: no version found")
        elif any(v != current for v in versions):
            problems.append(f"{place}: {', '.join(sorted(set(versions)))} (Cargo.toml says {current})")
    return current, problems


def next_version(current, part):
    major, minor, patch = map(int, current.split("."))
    return {"major": f"{major + 1}.0.0", "minor": f"{major}.{minor + 1}.0", "patch": f"{major}.{minor}.{patch + 1}"}[part]


def bump(part, root=ROOT, today=None):
    """Write the next version everywhere; returns it. Refuses on drift or an empty [Unreleased]."""
    current, problems = drift(root)
    if problems:
        raise SystemExit("version: places disagree, fix them first:\n  " + "\n  ".join(problems))
    changelog = (root / "CHANGELOG.md").read_text()
    m = UNRELEASED.search(changelog)
    if not m or not m.group(1).strip():
        raise SystemExit("version: [Unreleased] in CHANGELOG.md is empty; add the release's entries there first")
    new = next_version(current, part)
    date = (today or dt.date.today()).isoformat()
    for place, (file, pattern) in PLACES.items():
        if place == "CHANGELOG.md":
            continue
        path = root / file
        path.write_text(pattern.sub(lambda m: m.group(1) + new + m.group(3), path.read_text()))
    entries = m.group(1).strip("\n")
    changelog = changelog[:m.start()] + f"## [Unreleased]\n\n## [{new}] - {date}\n\n{entries}\n\n" + changelog[m.end():]
    (root / "CHANGELOG.md").write_text(changelog)
    return new


def main(argv=None):
    p = argparse.ArgumentParser(description="FRANK's version: check or bump")
    p.add_argument("--bump", choices=["major", "minor", "patch"], help="write the next version everywhere")
    args = p.parse_args(argv)
    if args.bump:
        old = drift()[0]
        new = bump(args.bump)
        print(f"{old} -> {new}: " + ", ".join(PLACES))
        print(f"next: git add {' '.join(f for f, _ in PLACES.values())} && git commit -m 'chore: release v{new}'")
        return 0
    current, problems = drift()
    for problem in problems:
        print(f"DRIFT {problem}")
    print(f"{current}" + ("" if problems else f" (in all of {', '.join(PLACES)})"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
