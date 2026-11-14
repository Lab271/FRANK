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

Coverage and code quality (ADR-023) are measured on their own, by `make coverage`
and `make quality`, into target/assurance/; this reads what they left and shows a
box each, or "not measured". --coverage-min and --ccn-max turn them into gates.
MC/DC (ADR-025) likewise, from `make test-mcdc`; --mcdc-min gates it.
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

import coverage_metrics
import mcdc_metrics
import quality_metrics
import version

ROOT = Path(__file__).resolve().parent.parent
COVERAGE = ROOT / "target/assurance/coverage.json"   # make coverage
QUALITY = ROOT / "target/assurance/lizard.csv"       # make quality
MCDC = ROOT / "target/assurance/mcdc.json"           # make test-mcdc
# Shown, not gated, unless --coverage-min or --ccn-max is given.
COVERAGE_SHOWN, CCN_SHOWN, LENGTH_SHOWN = 0.80, 15, 80
LINK = re.compile(r"`([^`]+)`")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def links(block, label):
    """Backtick entries on the first `**label:**` line of block; [] when planned or absent."""
    m = re.search(rf"^\*\*{re.escape(label)}:\*\*(.*)$", block, flags=re.MULTILINE)
    if not m or "(planned" in m.group(1):
        return []
    return LINK.findall(m.group(1))


RUST_TEST = re.compile(r"#\[(?:tokio::)?test\b")


def is_rust_test(text, at):
    """Whether the fn starting at offset `at` carries #[test] or #[tokio::test]: the
    attribute and comment lines right above it, up to the first other line."""
    for line in reversed(text[:text.rfind("\n", 0, at) + 1].splitlines()):
        line = line.strip()
        if RUST_TEST.match(line):
            return True
        if not line.startswith(("#[", "//")):
            return False
    return False


def dead_reason(entry, root=ROOT, test=False):
    """None when the link resolves, else why it does not. With test=True (a **Tests:**
    link) a Rust symbol must be a #[test] or #[tokio::test] fn, not a helper (#298)."""
    path, _, symbol = (s.strip() for s in entry.partition("::"))
    file = (root / path).resolve()
    if not (file.is_relative_to(root) and file.is_file()):
        return "file missing"
    if symbol:
        text = file.read_text(errors="replace")
        if file.suffix != ".rs":
            return None if symbol in text else f"no {symbol}"
        fns = [m.start() for m in re.finditer(rf"\bfn\s+{re.escape(symbol)}\b", text)]
        if not fns:
            return f"no fn {symbol}"
        if test and not any(is_rust_test(text, at) for at in fns):
            return f"fn {symbol} is not a test"
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
            results = [(e, dead_reason(e, root, test=True)) for e in links(chunk, "Tests")]
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


def duplicate_numbers(root=ROOT):
    """[(NNN, [folders])] for spec numbers used by more than one folder, outdated ones included:
    "spec 013" must name one spec."""
    by_number = {}
    for d in sorted(p.parent for p in root.glob(".openspec/specs/*/spec.md")):
        number = d.name.split("-", 1)[0]
        by_number.setdefault(number, []).append(d.name)
    return [(n, names) for n, names in by_number.items() if len(names) > 1]


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


def boxed(lines, title="FRANK spec assurance"):
    width = max(len(title) + 1, *(len(ANSI.sub("", l)) for l in lines))
    top = paint(f"╭─ {title} " + "─" * (width - len(title) - 1) + "╮", BOLD)
    body = [paint("│ ", BOLD) + l + " " * (width - len(ANSI.sub("", l))) + paint(" │", BOLD) for l in lines]
    return "\n".join([top, *body, paint("╰" + "─" * (width + 2) + "╯", BOLD)])


def disagree(drift):
    return "1 place disagrees" if len(drift) == 1 else f"{len(drift)} places disagree"


def report(specs, skipped, md_dead, verbose, floor=None, dupes=(), release=None):
    """Dashboard, then a bar per spec, then dead links. Returns (tested share, dead links).
    release: (version, [drift]) from scripts/version.py, shown as a row of the box."""
    reqs = [r for rs in specs.values() for r in rs]
    scen = sum(r["scenarios"] for r in reqs)
    impl = sum(r["implemented"] for r in reqs)
    total = tested(reqs) / scen if scen else 0.0
    dead = sum(len(r["dead"]) for r in reqs) + len(md_dead)
    f = 0.95 if floor is None else floor

    head = []
    if floor is not None:
        ok = total >= floor and not dead and not dupes and not (release and release[1])
        verdict = paint(" PASS ", BOLD, "42;30") if ok else paint(" FAIL ", BOLD, "41;97")
        if not COLOR:
            verdict = "PASS" if ok else "FAIL"
        head.append(f"{verdict}  tested {total:.0%} against a floor of {floor:.0%}")
    head += [
        f"specs        {len(specs)} counted" + (f", {len(skipped)} outdated" if skipped else ""),
        f"implemented  {cell(impl, len(reqs), f)}  requirements",
        f"tested       {cell(tested(reqs), scen, f)}  scenarios",
        "dead links   " + (paint(f"{dead}", RED, BOLD) if dead else paint("0", GREEN)),
        "numbers      " + (paint(f"{len(dupes)} used twice", RED, BOLD) if dupes else paint("unique", GREEN)),
    ]
    if release is not None:
        current, drift = release
        head.append("version      " + (paint(f"{current}, {disagree(drift)}", RED, BOLD) if drift
                                      else paint(f"{current}", GREEN) + paint(f" in all {len(version.PLACES)} places", DIM)))
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
    for number, names in dupes:
        print(paint("DUPLICATE", RED, BOLD) + f" spec number {number}: {', '.join(names)}")
    for problem in (release[1] if release else ()):
        print(paint("VERSION DRIFT", RED, BOLD) + f" {problem}")
    return total, dead


def age(path):
    """How long ago the file was written: 'measured 3 h ago'."""
    s = max(0, time.time() - Path(path).stat().st_mtime)
    for unit, n in (("d", 86400), ("h", 3600), ("min", 60)):
        if s >= n:
            return f"measured {s // n:.0f} {unit} ago"
    return "measured just now"


def short(func):
    """crates/frank/src/main.rs + main -> frank/src/main.rs::main"""
    return f"{func['file'].removeprefix('crates/')}::{func['name']}"


def report_coverage(path, floor=None):
    """The coverage box. Returns the share of lines covered, None when not measured."""
    print()
    if not Path(path).is_file():
        print(boxed([paint("not measured (make coverage)", DIM)], "FRANK coverage"))
        return None
    cov = coverage_metrics.read(path, ROOT)
    f = COVERAGE_SHOWN if floor is None else floor
    lines = [f"{kind:<12} {cell(*cov['totals'][kind], f)}" for kind in coverage_metrics.KINDS]
    lines.append(paint(f"cargo llvm-cov, {age(path)}", DIM))
    print(boxed(lines, "FRANK coverage"))
    worst = coverage_metrics.least_covered(cov["files"])
    if worst:
        print(paint("least covered (lines)", BOLD))
        for name, done, of in worst:
            print(f"  {cell(done, of, f, 10)}  {name}")
    covered, count = cov["totals"]["lines"]
    return covered / count if count else 0.0


def ccn_problems(funcs, ccn_max, baseline=None):
    """What --ccn-max (and the baseline, when given) does not allow, one line each."""
    if baseline is None:
        over = sorted((f for f in funcs if f["ccn"] > ccn_max), key=lambda f: -f["ccn"])
        return [paint("OVER CCN", RED, BOLD) + f" {f['ccn']} {short(f)}" for f in over]
    new, grew, stale = quality_metrics.ratchet(funcs, baseline, ccn_max)
    return ([paint("OVER CCN", RED, BOLD) + f" {f['ccn']} {short(f)} (not in the baseline)" for f in new]
            + [paint("GREW CCN", RED, BOLD) + f" {f['ccn']} {short(f)} (baseline {b})" for f, b in grew]
            + [paint("STALE", RED, BOLD) + f" {file.removeprefix('crates/')}::{name} (baseline {b}, now at or under "
               f"{ccn_max} or gone): take it off the baseline" for file, name, b in stale])


def report_quality(path, ccn_max=None, baseline_path=None):
    """The quality box. Returns what --ccn-max does not allow ([] without it), None when not measured."""
    print()
    if not Path(path).is_file():
        print(boxed([paint("not measured (make quality)", DIM)], "FRANK code quality"))
        return None
    funcs = quality_metrics.read(path)
    baseline = quality_metrics.read_baseline(baseline_path) if baseline_path else None
    limit = CCN_SHOWN if ccn_max is None else ccn_max
    q = quality_metrics.summary(funcs, quality_metrics.file_lengths(funcs, ROOT), limit, LENGTH_SHOWN)

    def count(items, what):
        return paint(f"{len(items)} {what}", YELLOW if items else GREEN)

    top = q["by_ccn"][0] if q["by_ccn"] else None
    lines = [
        f"functions    {q['functions']} in {q['files']} files",
        f"CCN          avg {q['ccn_avg']:.1f}" + (f", max {top['ccn']} {short(top)}" if top else ""),
        f"{f'CCN > {limit}':<13}{count(q['over_ccn'], 'functions')}"
        + (f" (baseline {len(baseline)})" if baseline is not None else ""),
        f"{f'length > {LENGTH_SHOWN}':<13}{count(q['over_length'], 'functions')}",
    ]
    if q["longest_files"]:
        name, n = q["longest_files"][0]
        lines.append(f"longest file {n} lines {name.removeprefix('crates/')}")
    lines.append(paint(f"lizard, crates/*/src, {age(path)}", DIM))
    print(boxed(lines, "FRANK code quality"))
    tables = (("CCN", "by_ccn", "ccn"), ("function lines", "by_length", "length"))
    for title, key, field in tables:
        print(paint(f"highest {title}", BOLD))
        for f in q[key]:
            print(f"  {f[field]:>4}  {short(f)}")
    print(paint("longest files", BOLD))
    for name, n in q["longest_files"]:
        print(f"  {n:>4}  {name.removeprefix('crates/')}")
    return ccn_problems(funcs, ccn_max, baseline) if ccn_max is not None else []


def report_mcdc(path, floor=None):
    """The MC/DC box. Returns the share of decisions covered, None when not measured."""
    print()
    if not Path(path).is_file():
        print(boxed([paint("not measured (make test-mcdc)", DIM)], "FRANK MC/DC"))
        return None
    s = mcdc_metrics.summary(mcdc_metrics.read(path))
    lines = [
        f"{'decisions':<12} {cell(s['covered'], s['decisions'], 1.0 if floor is None else floor)}",
        paint(f"of two or more conditions; {s['single']} of one left to branch coverage", DIM),
        paint(f"cargo-mvl-mcdc, {age(path)}", DIM),
    ]
    print(boxed(lines, "FRANK MC/DC"))
    for r in s["open"][:5]:
        print(f"  {paint('open', YELLOW)}  {r['id']}  {r['vectors_discharged']}/{r['vectors_required']} vectors  "
              f"{r['file'].removeprefix('crates/')}:{r['line']}")
    return s["covered"] / s["decisions"] if s["decisions"] else 1.0


def main(argv=None):
    p = argparse.ArgumentParser(description="FRANK spec traceability")
    p.add_argument("-v", "--verbose", action="store_true", help="per requirement, with dead links")
    p.add_argument("--min", type=float,
                   help="fail if tested < MIN (0.0-1.0), any link is dead or two specs share a number")
    p.add_argument("--coverage", type=Path, default=COVERAGE, help="llvm-cov JSON (make coverage)")
    p.add_argument("--quality", type=Path, default=QUALITY, help="lizard CSV (make quality)")
    p.add_argument("--mcdc", type=Path, default=MCDC, help="cargo-mvl-mcdc harvest JSON (make test-mcdc)")
    p.add_argument("--coverage-min", type=float,
                   help="fail if lines covered < MIN (0.0-1.0) or coverage was not measured")
    p.add_argument("--ccn-max", type=int,
                   help="fail if a function's CCN > MAX or quality was not measured")
    p.add_argument("--ccn-baseline", type=Path,
                   help="with --ccn-max: the functions allowed over it, at most at their CCN (make quality-baseline)")
    p.add_argument("--mcdc-min", type=float,
                   help="fail if decisions covered < MIN (0.0-1.0) or MC/DC was not measured")
    args = p.parse_args(argv)
    dupes = duplicate_numbers()
    release = version.drift()
    total, dead = report(*collect(), args.verbose, args.min, dupes, release)
    try:
        lines = report_coverage(args.coverage, args.coverage_min)
        over = report_quality(args.quality, args.ccn_max, args.ccn_baseline)
        mcdc = report_mcdc(args.mcdc, args.mcdc_min)
    except (ValueError, KeyError, OSError) as e:
        print(paint("UNREADABLE", RED, BOLD) + f" {e}")
        return 1
    failures = []
    if args.min is not None:
        print()
        drift = release[1]
        print(f"{'PASS' if total >= args.min and not dead and not dupes and not drift else 'FAIL'}: tested {total:.0%} "
              f"(min {args.min:.0%}), {dead} dead links, {len(dupes)} duplicate spec numbers, "
              f"version {release[0]}" + (f" ({disagree(drift)})" if drift else ""))
        if total < args.min or dead or dupes or drift:
            failures.append("specs")
    if args.coverage_min is not None:
        ok = lines is not None and lines >= args.coverage_min
        # One decimal: 93.9% against 94% must not read "94% (min 94%)".
        got = "not measured" if lines is None else f"{lines:.1%}"
        print(f"{'PASS' if ok else 'FAIL'}: lines covered {got} (min {args.coverage_min:.1%})")
        if not ok:
            failures.append("coverage")
    if args.ccn_max is not None:
        ok = over is not None and not over
        got = "not measured" if over is None else f"{len(over)} problems"
        against = f"max {args.ccn_max}" + (f", baseline {args.ccn_baseline}" if args.ccn_baseline else "")
        print(f"{'PASS' if ok else 'FAIL'}: CCN {got} ({against})")
        for line in over or []:
            print(line)
        if not ok:
            failures.append("quality")
    if args.mcdc_min is not None:
        ok = mcdc is not None and mcdc >= args.mcdc_min
        got = "not measured" if mcdc is None else f"{mcdc:.1%}"
        print(f"{'PASS' if ok else 'FAIL'}: MC/DC decisions covered {got} (min {args.mcdc_min:.1%})")
        if not ok:
            failures.append("mcdc")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
