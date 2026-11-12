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
    scripts/assurance.py            dashboard, a bar per spec (colour on a terminal; NO_COLOR=1 turns it off)
    scripts/assurance.py -v         per requirement, with dead links
    scripts/assurance.py --min 0.5  exit 1 if tested < 50% or any link is dead
"""

import argparse
import os
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


# Colour on a terminal, in GitHub Actions (its log shows it) or with
# FORCE_COLOR; never with NO_COLOR set (https://no-color.org).
COLOR = "NO_COLOR" not in os.environ and (
    sys.stdout.isatty() or "GITHUB_ACTIONS" in os.environ or "FORCE_COLOR" in os.environ)
GREEN, YELLOW, RED, BOLD, DIM = "32", "33", "31", "1", "2"
BAR = 20
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def paint(text, *codes):
    return f"\x1b[{';'.join(codes)}m{text}\x1b[0m" if COLOR and codes and text else text


def grade(share, floor):
    """Green at or above the floor, yellow within 15 points of it, red below."""
    return GREEN if share >= floor else YELLOW if share >= floor - 0.15 else RED


def bar(share, floor, width=BAR):
    """`width` cells, the filled share in its grade's colour."""
    filled = round(share * width)
    if share < 1 and filled == width:
        filled -= 1  # a full bar means 100%
    return paint("█" * filled, grade(share, floor)) + paint("░" * (width - filled), DIM)


def cell(done, of, floor, width=BAR):
    share = done / of if of else 0.0
    return f"{bar(share, floor, width)} {done:>3}/{of:<3} {paint(f'{share:>4.0%}', grade(share, floor))}"


def boxed(lines):
    width = max(len(ANSI.sub("", l)) for l in lines)
    top = paint("╭─ FRANK spec assurance " + "─" * (width - 21) + "╮", BOLD)
    body = [paint("│ ", BOLD) + l + " " * (width - len(ANSI.sub("", l))) + paint(" │", BOLD) for l in lines]
    return "\n".join([top, *body, paint("╰" + "─" * (width + 2) + "╯", BOLD)])


def report(specs, skipped, md_dead, verbose, floor=None):
    """Dashboard, then a bar per spec, then dead links. Returns (tested share, dead links)."""
    reqs = [r for rs in specs.values() for r in rs]
    scen = sum(r["scenarios"] for r in reqs)
    impl = sum(r["implemented"] for r in reqs)
    total = tested(reqs) / scen if scen else 0.0
    dead = sum(len(r["dead"]) for r in reqs) + len(md_dead)
    f = 0.95 if floor is None else floor

    head = []
    if floor is not None:
        ok = total >= floor and not dead
        verdict = paint(" PASS ", BOLD, "42;30") if ok else paint(" FAIL ", BOLD, "41;97")
        if not COLOR:
            verdict = "PASS" if ok else "FAIL"
        head.append(f"{verdict}  tested {total:.0%} against a floor of {floor:.0%}")
    head += [
        f"specs        {len(specs)} counted" + (f", {len(skipped)} outdated" if skipped else ""),
        f"implemented  {cell(impl, len(reqs), f)}  requirements",
        f"tested       {cell(tested(reqs), scen, f)}  scenarios",
        "dead links   " + (paint(f"{dead}", RED, BOLD) if dead else paint("0", GREEN)),
    ]
    print(boxed(head))
    print()

    name_w = max(map(len, specs), default=4) + 2
    print(paint(f"{'spec':<{name_w}}{'implemented':<27}tested", BOLD))
    for name, rs in specs.items():
        n = sum(r["scenarios"] for r in rs)
        d = sum(len(r["dead"]) for r in rs)
        warn = paint(f"  {d} dead", RED, BOLD) if d else ""
        print(f"{name:<{name_w}}{cell(sum(r['implemented'] for r in rs), len(rs), f, 10)}    "
              f"{cell(tested(rs), n, f, 10)}{warn}")
    if skipped:
        print(paint(f"outdated, not counted: {', '.join(skipped)}", DIM))

    for name, rs in specs.items():
        for r in rs:
            if verbose:
                full = r["backed"] >= r["scenarios"]
                mark = (paint("I", GREEN) if r["implemented"] else paint("-", RED)) + \
                       (paint("T", GREEN) if full else paint("t", YELLOW) if r["backed"] else paint("-", RED))
                print(f"  [{mark}] {name} Req {r['num']}: {r['title']} ({r['backed']}/{r['scenarios']} scenarios)")
            for e, why in r["dead"]:
                print(paint("DEAD LINK", RED, BOLD) + f" {name} Req {r['num']}: {e} ({why})")
    for file, target in md_dead:
        print(paint("DEAD LINK", RED, BOLD) + f" {file}: {target}")
    return total, dead


def main(argv=None):
    p = argparse.ArgumentParser(description="FRANK spec traceability")
    p.add_argument("-v", "--verbose", action="store_true", help="per requirement, with dead links")
    p.add_argument("--min", type=float, help="fail if tested < MIN (0.0-1.0) or any link is dead")
    args = p.parse_args(argv)
    total, dead = report(*collect(), args.verbose, args.min)
    if args.min is not None:
        ok = total >= args.min and not dead
        print(f"{'PASS' if ok else 'FAIL'}: tested {total:.0%} (min {args.min:.0%}), {dead} dead links")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
