"""Tests for scripts/assurance.py: python3 -m unittest discover -s scripts -p 'test_*.py'"""

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


if __name__ == "__main__":
    unittest.main()
