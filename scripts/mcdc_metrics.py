"""MC/DC from cargo-mvl-mcdc (ADR-025): reads target/assurance/mcdc.json, written by `make test-mcdc`.

The file is `cargo-mvl-mcdc harvest`'s output: one record per decision of the
snapshot (tests/mcdc/obligations.json) with id, file, line, vectors_required,
compiler_void, vectors_discharged, discharged and tagged_tests ({name, vector,
passed}). vectors_required is the number of conditions plus one: 0 for an
exhaustive match (the compiler covers it), 2 for one condition (branch coverage,
which llvm-cov already measures), 3 or more for a decision MC/DC is about.

    python3 scripts/mcdc_metrics.py target/assurance/mcdc.json [-v]

prints the decisions of two or more conditions and fails while one is not covered.
"""

import argparse
import json
import sys
from pathlib import Path


def read(path):
    """The harvest records; ValueError when the file is not one."""
    records = json.loads(Path(path).read_text())
    if not isinstance(records, list) or any("vectors_required" not in r for r in records):
        raise ValueError(f"{path}: not cargo-mvl-mcdc harvest output; run make test-mcdc")
    return records


def multi(records):
    """The decisions of two or more conditions: the ones MC/DC asks tests for."""
    return [r for r in records if not r["compiler_void"] and r["vectors_required"] >= 3]


def summary(records):
    """{decisions, covered, open: [records not covered], single, void}."""
    m = multi(records)
    return {
        "decisions": len(m),
        "covered": sum(1 for r in m if r["discharged"]),
        "open": [r for r in m if not r["discharged"]],
        "single": sum(1 for r in records if not r["compiler_void"] and r["vectors_required"] == 2),
        "void": sum(1 for r in records if r["compiler_void"]),
    }


def missing(record):
    """What one decision still needs, one line each: a vector without a passing test, or a failing test."""
    passed = {t["vector"] for t in record["tagged_tests"] if t["passed"]}
    out = [f"add mcdc__{record['id']}__v{v}_<what>"
           for v in range(1, record["vectors_required"] + 1) if v not in passed]
    out += [f"fix {t['name']} (failing)" for t in record["tagged_tests"] if not t["passed"]]
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="MC/DC from cargo-mvl-mcdc harvest")
    p.add_argument("path", type=Path)
    p.add_argument("-v", "--verbose", action="store_true", help="every decision, and what each open one needs")
    args = p.parse_args(argv)
    records = read(args.path)
    s = summary(records)
    print(f"MC/DC: {s['covered']}/{s['decisions']} decisions of two or more conditions covered "
          f"({s['single']} of one condition left to branch coverage, {s['void']} exhaustive matches)")
    for r in multi(records):
        if args.verbose or not r["discharged"]:
            mark = "OK" if r["discharged"] else "--"
            print(f"  [{mark}] {r['id']}  {r['vectors_discharged']}/{r['vectors_required']} vectors  "
                  f"({r['file']}:{r['line']})")
            if args.verbose and not r["discharged"]:
                for line in missing(r):
                    print(f"         {line}")
    if s["open"]:
        print(f"FAIL: {len(s['open'])} decisions not covered (VERBOSE=1 for the missing vectors)")
        return 1
    print("PASS: every decision of two or more conditions is covered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
