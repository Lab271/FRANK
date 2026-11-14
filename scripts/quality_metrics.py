"""Code quality from lizard (ADR-023): reads target/assurance/lizard.csv, written by `make quality`.

    uvx lizard==1.25.1 -l rust --csv crates/*/src

One row per function, no header:

    nloc, ccn, token, param, length, location, file, name, long_name, start, end

Not used, because lizard gets them wrong for Rust (#298): fan-in and fan-out
(-Eio matches every token equal to a function's bare name, variables included)
and the parameter count (a tuple pattern counts each name).
"""

import csv
from pathlib import Path

COLUMNS = 11


def read(path):
    """[{file, name, start, nloc, ccn, length}] from lizard's CSV."""
    out = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) != COLUMNS:
                raise ValueError(f"{path}: {len(row)} columns, expected {COLUMNS} (lizard --csv); run make quality")
            out.append({
                "file": row[6], "name": row[7], "start": int(row[9]),
                "nloc": int(row[0]), "ccn": int(row[1]), "length": int(row[4]),
            })
    return out


def file_lengths(funcs, root):
    """{file: lines} for the files lizard scanned; a file gone since is left out."""
    out = {}
    for name in sorted({f["file"] for f in funcs}):
        p = Path(root) / name
        if p.is_file():
            out[name] = p.read_text(errors="replace").count("\n")
    return out


def summary(funcs, files, ccn_max, length_max, top=5):
    """The numbers the dashboard shows."""
    def worst(key, n=top):
        return sorted(funcs, key=lambda f: (-f[key], f["file"], f["start"]))[:n]
    return {
        "functions": len(funcs),
        "files": len(files),
        "ccn_avg": sum(f["ccn"] for f in funcs) / len(funcs) if funcs else 0.0,
        "over_ccn": [f for f in worst("ccn", len(funcs)) if f["ccn"] > ccn_max],
        "over_length": [f for f in funcs if f["length"] > length_max],
        "by_ccn": worst("ccn"),
        "by_length": worst("length"),
        "longest_files": sorted(files.items(), key=lambda kv: (-kv[1], kv[0]))[:top],
    }


# The CCN baseline (#301): the functions over the limit when the gate was switched
# on, each with its CCN then. `file::name` is not unique (a `new` or `fmt` per impl
# block), so a key stands for every function of that name in the file, at the
# highest CCN among them.
BASELINE_HEADER = ["file", "function", "ccn"]


def worst_per_name(funcs):
    """{(file, name): the function of that name in the file with the highest CCN}."""
    out = {}
    for f in funcs:
        key = (f["file"], f["name"])
        if key not in out or f["ccn"] > out[key]["ccn"]:
            out[key] = f
    return out


def read_baseline(path):
    """{(file, name): ccn} from the baseline CSV."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and list(rows[0]) != BASELINE_HEADER:
        raise ValueError(f"{path}: expected the columns {','.join(BASELINE_HEADER)}; run make quality-baseline")
    return {(r["file"], r["function"]): int(r["ccn"]) for r in rows}


def write_baseline(funcs, ccn_max, out):
    """The baseline for these functions: every name over ccn_max, worst first."""
    over = [f for f in worst_per_name(funcs).values() if f["ccn"] > ccn_max]
    w = csv.writer(out, lineterminator="\n")
    w.writerow(BASELINE_HEADER)
    for f in sorted(over, key=lambda f: (-f["ccn"], f["file"], f["name"])):
        w.writerow([f["file"], f["name"], f["ccn"]])


def ratchet(funcs, baseline, ccn_max):
    """What the baseline does not allow: (new, grew, stale), each a list.

    new    functions over ccn_max that the baseline does not list
    grew   listed functions above their recorded CCN, as (function, recorded)
    stale  listed (file, name, recorded) now at or under ccn_max, or gone:
           take them off, so the list only shrinks
    """
    now = worst_per_name(funcs)
    new = sorted((f for k, f in now.items() if f["ccn"] > ccn_max and k not in baseline), key=lambda f: -f["ccn"])
    grew = [(now[k], b) for k, b in sorted(baseline.items()) if k in now and now[k]["ccn"] > b]
    stale = [(*k, b) for k, b in sorted(baseline.items()) if k not in now or now[k]["ccn"] <= ccn_max]
    return new, grew, stale


def main(argv=None):
    import argparse
    import sys
    p = argparse.ArgumentParser(description="FRANK code quality: write the CCN baseline (make quality-baseline)")
    p.add_argument("csv", help="lizard CSV (make quality)")
    p.add_argument("--ccn-max", type=int, required=True)
    args = p.parse_args(argv)
    write_baseline(read(args.csv), args.ccn_max, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
