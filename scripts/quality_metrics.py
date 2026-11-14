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
