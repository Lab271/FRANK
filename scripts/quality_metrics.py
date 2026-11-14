"""Code quality from lizard (ADR-023): reads target/assurance/lizard.csv, written by `make quality`.

    uvx lizard==1.25.1 -l rust -Eio --csv crates/*/src

One row per function, no header:

    nloc, ccn, token, param, length, location, file, name, long_name, start, end,
    fan_in, fan_out, general_fan_out        (the last three from -Eio)

lizard's fan-in and fan-out match calls by bare function name across the scan, so
two functions called `new` share their callers: they are approximate, never a gate.
"""

import csv
from pathlib import Path

COLUMNS = 14


def read(path):
    """[{file, name, start, nloc, ccn, length, fan_in, fan_out}] from lizard's CSV."""
    out = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) != COLUMNS:
                raise ValueError(f"{path}: {len(row)} columns, expected {COLUMNS} (lizard -Eio --csv); run make quality")
            out.append({
                "file": row[6], "name": row[7], "start": int(row[9]),
                "nloc": int(row[0]), "ccn": int(row[1]), "length": int(row[4]),
                "fan_in": int(row[11]), "fan_out": int(row[12]),
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
        "by_fan_in": worst("fan_in"),
        "by_fan_out": worst("fan_out"),
        "longest_files": sorted(files.items(), key=lambda kv: (-kv[1], kv[0]))[:top],
    }
