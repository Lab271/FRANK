"""Tests for scripts/mcdc_metrics.py: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import mcdc_metrics


def record(id, required, passed=(), failed=(), void=False):
    """One harvest record; passed and failed are vector numbers with a tagged test."""
    tests = ([{"name": f"mcdc__{id}__v{v}_x", "vector": v, "passed": True} for v in passed]
             + [{"name": f"mcdc__{id}__v{v}_y", "vector": v, "passed": False} for v in failed])
    done = void or len(set(passed)) >= required
    return {"id": id, "file": "crates/a/src/a.rs", "line": 7, "vectors_required": 0 if void else required,
            "compiler_void": void, "vectors_discharged": len(set(passed)), "discharged": done,
            "tagged_tests": tests}


class Metrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "mcdc.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, *records):
        self.path.write_text(json.dumps(list(records)))

    def run_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = mcdc_metrics.main([str(self.path), *args])
        return code, out.getvalue()

    def test_only_decisions_of_two_or_more_conditions_count(self):
        self.write(record("a_m_1", 3, passed=(1, 2, 3)), record("a_m_2", 4, passed=(1,)),
                   record("a_s_3", 2), record("a_v_4", 0, void=True))
        s = mcdc_metrics.summary(mcdc_metrics.read(self.path))
        self.assertEqual((s["decisions"], s["covered"], s["single"], s["void"]), (2, 1, 1, 1))
        self.assertEqual([r["id"] for r in s["open"]], ["a_m_2"])

    def test_missing_names_each_vector_without_a_passing_test_and_each_failing_test(self):
        self.assertEqual(mcdc_metrics.missing(record("a_m_1", 3, passed=(1,), failed=(2,))),
                         ["add mcdc__a_m_1__v2_<what>", "add mcdc__a_m_1__v3_<what>",
                          "fix mcdc__a_m_1__v2_y (failing)"])

    def test_an_open_decision_fails_and_is_named(self):
        self.write(record("a_m_1", 3, passed=(1, 2, 3)), record("a_m_2", 3, passed=(1, 2)))
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("1/2 decisions", out)
        self.assertIn("a_m_2  2/3 vectors", out)
        self.assertNotIn("a_m_1", out)
        self.assertIn("add mcdc__a_m_2__v3_<what>", self.run_main("-v")[1])

    def test_all_covered_passes(self):
        self.write(record("a_m_1", 3, passed=(1, 2, 3)), record("a_s_2", 2))
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)

    def test_another_json_is_refused(self):
        self.path.write_text(json.dumps({"data": []}))
        with self.assertRaisesRegex(ValueError, "make test-mcdc"):
            mcdc_metrics.read(self.path)


if __name__ == "__main__":
    unittest.main()
