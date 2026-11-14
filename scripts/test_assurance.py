"""Tests for scripts/assurance.py: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import assurance

SPEC = """# Example

**Status:** Implemented

### Requirement 1: Adds [MUST]

**Implementation:** `src/lib.rs::add`

#### Scenario: Adds two numbers

- GIVEN 1 and 2
- THEN 3

**Tests:** `tests/t.rs::adds`

#### Scenario: Overflows

- GIVEN max and 1
- THEN an error

### Requirement 2: Subtracts [SHOULD]

**Implementation:** `src/lib.rs::sub` (planned)

#### Scenario: Subtracts

**Tests:** `tests/t.rs::subtracts` (planned)
"""


class Tree(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.write("src/lib.rs", "pub fn add(a: u8, b: u8) -> u8 { a + b }\n")
        self.write("tests/t.rs", "#[test]\nfn adds() {}\n")
        self.write(".openspec/specs/001-example/spec.md", SPEC)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


class DeadReason(Tree):
    def test_resolves_file_and_rust_fn(self):
        self.assertIsNone(assurance.dead_reason("src/lib.rs::add", self.root))
        self.assertIsNone(assurance.dead_reason("src/lib.rs", self.root))

    def test_missing_file(self):
        self.assertEqual(assurance.dead_reason("src/gone.rs::add", self.root), "file missing")

    def test_rust_symbol_must_be_a_fn_not_a_substring(self):
        # "a" occurs in the file, but there is no `fn a`
        self.assertEqual(assurance.dead_reason("src/lib.rs::a", self.root), "no fn a")

    def test_non_rust_symbol_is_a_substring(self):
        self.write("web/app.js", "function render() {}\n")
        self.assertIsNone(assurance.dead_reason("web/app.js::render", self.root))

    def test_path_outside_the_tree_is_dead(self):
        self.assertEqual(assurance.dead_reason("../outside.rs", self.root), "file missing")


class ParseSpec(Tree):
    def test_scores_scenarios_and_skips_planned(self):
        reqs = assurance.parse_spec(SPEC, self.root)
        self.assertEqual([(r["num"], r["scenarios"], r["backed"], r["implemented"]) for r in reqs],
                         [(1, 2, 1, True), (2, 1, 0, False)])
        self.assertEqual(sum(len(r["dead"]) for r in reqs), 0)

    def test_dead_test_link_counts_against_coverage(self):
        spec = SPEC.replace("tests/t.rs::adds", "tests/t.rs::renamed")
        reqs = assurance.parse_spec(spec, self.root)
        self.assertEqual(reqs[0]["dead"], [("tests/t.rs::renamed", "no fn renamed")])
        self.assertEqual(assurance.tested(reqs), 0)

    def test_dead_implementation_link_means_not_implemented(self):
        reqs = assurance.parse_spec(SPEC.replace("::add`", "::gone`"), self.root)
        self.assertFalse(reqs[0]["implemented"])


class Collect(Tree):
    def test_outdated_spec_is_skipped(self):
        self.write(".openspec/specs/002-old/spec.md",
                   "**Status:** Outdated (Phase 2)\n\n### Requirement 1: Old [MUST]\n\n"
                   "**Implementation:** `src/frank/models.py`\n\n[gone](nowhere.md)\n")
        specs, skipped, md_dead = assurance.collect(self.root)
        self.assertEqual(list(specs), ["001-example"])
        self.assertEqual(skipped, ["002-old"])
        self.assertEqual(md_dead, [])

    def test_duplicate_spec_numbers_are_found(self):
        self.write(".openspec/specs/013-disclosure/spec.md", "**Status:** Implemented\n")
        self.write(".openspec/specs/013-sso/spec.md", "**Status:** Outdated\n")
        self.write(".openspec/specs/014-query/spec.md", "**Status:** Implemented\n")
        self.assertEqual(assurance.duplicate_numbers(self.root),
                         [("013", ["013-disclosure", "013-sso"])])

    def test_dead_markdown_link_is_reported(self):
        self.write("docs/a.md", "[ok](b.md) [web](https://example.org) [gone](c.md#x)\n")
        self.write("docs/b.md", "")
        _, _, md_dead = assurance.collect(self.root)
        self.assertEqual(md_dead, [(Path("docs/a.md"), "c.md")])


class Dashboard(unittest.TestCase):
    def setUp(self):
        self.color, assurance.COLOR = assurance.COLOR, False

    def tearDown(self):
        assurance.COLOR = self.color

    def test_bar_fills_its_share(self):
        self.assertEqual(assurance.bar(0.5, 0.95, 10), "█" * 5 + "░" * 5)
        self.assertEqual(assurance.bar(1.0, 0.95, 10), "█" * 10)

    def test_a_full_bar_means_all(self):
        self.assertEqual(assurance.bar(0.97, 0.95, 10), "█" * 9 + "░")

    def test_grade_against_the_floor(self):
        self.assertEqual(assurance.grade(0.96, 0.95), assurance.GREEN)
        self.assertEqual(assurance.grade(0.85, 0.95), assurance.YELLOW)
        self.assertEqual(assurance.grade(0.47, 0.95), assurance.RED)

    def test_no_escape_codes_without_colour(self):
        self.assertNotIn("\x1b", assurance.cell(7, 15, 0.95))
        self.assertEqual(assurance.paint("x", assurance.RED), "x")

    def test_box_fits_a_title_longer_than_its_lines(self):
        top, body, bottom = assurance.boxed(["x"], "FRANK code quality").split("\n")
        self.assertEqual(len(top), len(body))
        self.assertEqual(len(top), len(bottom))


class Gates(unittest.TestCase):
    """Coverage and quality (ADR-023): shown when measured, gated only on request."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cov = self.dir / "coverage.json"
        self.lizard = self.dir / "lizard.csv"
        lines = lambda c, n: {k: {"count": n, "covered": c, "percent": 0} for k in ("lines", "functions", "regions")}
        self.cov.write_text(json.dumps({"type": "llvm.coverage.json.export", "data": [
            {"files": [{"filename": "/x/a.rs", "summary": lines(8, 10)}], "totals": lines(8, 10)}]}))
        self.lizard.write_text('90,20,900,3,95,"big@1-95@src/a.rs","src/a.rs","big","big",1,95,1,12,30\n')

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = assurance.main(["--coverage", str(self.cov), "--quality", str(self.lizard), *args])
        return code, out.getvalue()

    def test_measured_without_gates_passes_and_shows_both(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("FRANK coverage", out)
        self.assertIn("src/a.rs::big", out)

    def test_not_measured_is_shown_not_failed(self):
        self.cov.unlink()
        self.lizard.unlink()
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("not measured (make coverage)", out)
        self.assertIn("not measured (make quality)", out)

    def test_coverage_below_the_minimum_fails(self):
        self.assertEqual(self.run_main("--coverage-min", "0.8")[0], 0)
        self.assertEqual(self.run_main("--coverage-min", "0.9")[0], 1)

    def test_a_gate_without_its_measurement_fails(self):
        self.cov.unlink()
        self.assertEqual(self.run_main("--coverage-min", "0.5")[0], 1)
        self.lizard.unlink()
        self.assertEqual(self.run_main("--ccn-max", "50")[0], 1)

    def test_a_function_over_ccn_max_fails_and_is_named(self):
        self.assertEqual(self.run_main("--ccn-max", "20")[0], 0)
        code, out = self.run_main("--ccn-max", "19")
        self.assertEqual(code, 1)
        self.assertIn("OVER CCN 20 src/a.rs::big", out)

    def test_tested_scenarios_below_the_floor_fail(self):
        self.assertEqual(self.run_main("--min", "0.0")[0], 0)
        code, out = self.run_main("--min", "1.01")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: tested", out)

    def test_an_unreadable_measurement_fails(self):
        self.lizard.write_text("1,2,3\n")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("UNREADABLE", out)


if __name__ == "__main__":
    unittest.main()
