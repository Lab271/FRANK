#!/usr/bin/env python3
"""FRANK assurance: spec -> code -> test traceability (ADR-021).

Reads .openspec/specs/*/spec.md and checks every link against the tree:

    ### Requirement N: Title [MUST]
    **Implementation:** `crates/frank/src/admin.rs::add_user`      (before the first scenario)
    #### Scenario: ...
    **Tests:** `crates/frank/tests/api.rs::users_are_disabled_then_removed`   (in the scenario it backs)

A link is `path` or `path::symbol`, backtick-quoted, comma-separated on one line.
For a .rs file the symbol must be a `fn` in that file; for other files a substring.
A line with `(planned)` is skipped. A spec whose **Status:** starts with `Outdated`
is skipped. Relative Markdown links in .openspec/, docs/, README.md and
CONTRIBUTING.md must resolve too.

Scores per spec:
    implemented  requirements whose implementation links all resolve
    tested       scenarios with at least one resolving test link; each dead link
                 subtracts one, because a stale link is a false claim of coverage

Usage:
    scripts/assurance.py            dashboard
    scripts/assurance.py -v         per requirement, with dead links
    scripts/assurance.py --min 0.5  exit 1 if tested < 50% or any link is dead
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"`([^`]+)`")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def links(block, label):
    """Backtick entries on the first `**label:**` line of block; [] when planned or absent."""
    m = re.search(rf"^\*\*{re.escape(label)}:\*\*(.*)$", block, flags=re.MULTILINE)
    if not m or "(planned" in m.group(1):
        return []
    return LINK.findall(m.group(1))


def dead_reason(entry, root=ROOT):
    """None when the link resolves, else why it does not."""
    path, _, symbol = (s.strip() for s in entry.partition("::"))
    file = (root / path).resolve()
    if not (file.is_relative_to(root) and file.is_file()):
        return "file missing"
    if symbol:
        text = file.read_text(errors="replace")
        pattern = rf"\bfn\s+{re.escape(symbol)}\b" if file.suffix == ".rs" else re.escape(symbol)
        if not re.search(pattern, text):
            return f"no {'fn ' if file.suffix == '.rs' else ''}{symbol}"
    return None


def outdated(text):
    m = re.search(r"^\*\*Status:\*\*\s*(.*)$", text, flags=re.MULTILINE)
    return bool(m and m.group(1).startswith("Outdated"))


def parse_spec(text, root=ROOT):
    """Requirements of one spec, each with its scenarios' coverage and dead links."""
    reqs = []
    for block in re.split(r"(?=^### Requirement \d+)", text, flags=re.MULTILINE):
        m = re.match(r"### Requirement (\d+): (.+?)\s*\[(\w+)\]", block)
        if not m:
            continue
        preamble, *scenarios = re.split(r"(?=^#### Scenario:)", block, flags=re.MULTILINE)
        impl = links(preamble, "Implementation")
        dead = [(e, r) for e in impl if (r := dead_reason(e, root))]
        backed = 0
        for chunk in scenarios or [block]:
            results = [(e, dead_reason(e, root)) for e in links(chunk, "Tests")]
            dead += [(e, r) for e, r in results if r]
            backed += any(r is None for _, r in results)
        reqs.append({
            "num": int(m.group(1)), "title": m.group(2), "scenarios": max(len(scenarios), 1),
            "implemented": bool(impl) and not any(e in impl for e, _ in dead),
            "backed": backed, "dead": dead,
        })
    return reqs


def dead_md_links(root=ROOT):
    """(file, target) for relative Markdown links that do not resolve."""
    files = [*root.glob(".openspec/**/*.md"), *root.glob("docs/**/*.md"), root / "README.md", root / "CONTRIBUTING.md"]
    out = []
    for f in sorted(p for p in files if p.is_file()):
        text = f.read_text(errors="replace")
        if f.name == "spec.md" and outdated(text):
            continue
        for target in MD_LINK.findall(text):
            target = target.split("#")[0]
            if target and not re.match(r"[a-z]+:", target) and not (f.parent / target).exists():
                out.append((f.relative_to(root), target))
    return out


def collect(root=ROOT):
    specs, skipped = {}, []
    for f in sorted(root.glob(".openspec/specs/*/spec.md")):
        text = f.read_text()
        if outdated(text):
            skipped.append(f.parent.name)
        else:
            specs[f.parent.name] = parse_spec(text, root)
    return specs, skipped, dead_md_links(root)


def tested(reqs):
    return max(0, sum(r["backed"] for r in reqs) - sum(len(r["dead"]) for r in reqs))


def report(specs, skipped, md_dead, verbose):
    reqs = [r for rs in specs.values() for r in rs]
    scen = sum(r["scenarios"] for r in reqs)
    print(f"{'spec':<28}{'implemented':>14}{'tested':>16}")
    for name, rs in specs.items():
        n = sum(r["scenarios"] for r in rs)
        impl = sum(r["implemented"] for r in rs)
        print(f"{name:<28}{impl:>7}/{len(rs):<3}{impl / len(rs) if rs else 0:>4.0%}"
              f"{tested(rs):>9}/{n:<3}{tested(rs) / n if n else 0:>4.0%}")
    total = tested(reqs) / scen if scen else 0.0
    print(f"{'total':<28}{sum(r['implemented'] for r in reqs):>7}/{len(reqs):<8}{tested(reqs):>9}/{scen:<3}{total:>4.0%}")
    if skipped:
        print(f"outdated, not counted: {', '.join(skipped)}")
    dead = sum(len(r["dead"]) for r in reqs) + len(md_dead)
    for name, rs in specs.items():
        for r in rs:
            if verbose:
                mark = ("I" if r["implemented"] else "-") + ("T" if r["backed"] >= r["scenarios"] else "t" if r["backed"] else "-")
                print(f"  [{mark}] {name} Req {r['num']}: {r['title']} ({r['backed']}/{r['scenarios']} scenarios)")
            for e, why in r["dead"]:
                print(f"DEAD LINK {name} Req {r['num']}: {e} ({why})")
    for f, target in md_dead:
        print(f"DEAD LINK {f}: {target}")
    return total, dead


def main(argv=None):
    p = argparse.ArgumentParser(description="FRANK spec traceability")
    p.add_argument("-v", "--verbose", action="store_true", help="per requirement, with dead links")
    p.add_argument("--min", type=float, help="fail if tested < MIN (0.0-1.0) or any link is dead")
    args = p.parse_args(argv)
    total, dead = report(*collect(), args.verbose)
    if args.min is not None:
        ok = total >= args.min and not dead
        print(f"{'PASS' if ok else 'FAIL'}: tested {total:.0%} (min {args.min:.0%}), {dead} dead links")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
