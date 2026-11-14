"""Tests for scripts/coverage_metrics.py: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import json
import tempfile
import unittest
from pathlib import Path

import coverage_metrics


def summary(covered, count):
    return {"count": count, "covered": covered, "percent": 100 * covered / count if count else 0}


def export(root, files):
    """An llvm-cov --summary-only export; files: {relative name: (covered lines, lines)}."""
    kinds = lambda c, n: {k: summary(c, n) for k in coverage_metrics.KINDS}
    return {
        "type": "llvm.coverage.json.export", "version": "3.1.0",
        "data": [{
            "files": [{"filename": str(Path(root) / name), "summary": kinds(*cn)} for name, cn in files.items()],
            "totals": kinds(sum(c for c, _ in files.values()), sum(n for _, n in files.values())),
        }],
    }


class Read(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "coverage.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_totals_and_files_relative_to_the_root(self):
        self.path.write_text(json.dumps(export(self.root, {"crates/a/src/lib.rs": (9, 10), "crates/a/src/main.rs": (0, 5)})))
        cov = coverage_metrics.read(self.path, self.root)
        self.assertEqual(cov["totals"]["lines"], (9, 15))
        self.assertEqual(cov["totals"]["functions"], (9, 15))
        self.assertEqual(cov["files"], [("crates/a/src/lib.rs", 9, 10), ("crates/a/src/main.rs", 0, 5)])

    def test_a_file_outside_the_root_keeps_its_path(self):
        self.path.write_text(json.dumps(export("/elsewhere", {"x.rs": (1, 2)})))
        self.assertEqual(coverage_metrics.read(self.path, self.root)["files"], [("/elsewhere/x.rs", 1, 2)])

    def test_another_json_is_refused(self):
        self.path.write_text(json.dumps({"data": []}))
        with self.assertRaisesRegex(ValueError, "make coverage"):
            coverage_metrics.read(self.path, self.root)


class LeastCovered(unittest.TestCase):
    def test_lowest_share_first_and_files_without_lines_left_out(self):
        files = [("a.rs", 9, 10), ("b.rs", 0, 5), ("c.rs", 0, 0), ("d.rs", 1, 2), ("e.rs", 0, 50)]
        self.assertEqual(coverage_metrics.least_covered(files, top=3), [("e.rs", 0, 50), ("b.rs", 0, 5), ("d.rs", 1, 2)])


if __name__ == "__main__":
    unittest.main()
