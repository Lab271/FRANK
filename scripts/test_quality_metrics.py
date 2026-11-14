"""Tests for scripts/quality_metrics.py: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import tempfile
import unittest
from pathlib import Path

import quality_metrics

# lizard 1.25.1 -l rust -Eio --csv: nloc, ccn, token, param, length, location, file,
# name, long_name (quoted, may hold commas), start, end, fan_in, fan_out, general_fan_out
CSV = '''6,2,61,2,6,"fmt@46-51@src/a.rs","src/a.rs","fmt","fmt & self , f : & mut Formatter",46,51,0,0,0
90,20,900,3,95,"big@60-154@src/a.rs","src/a.rs","big","big a , b , c",60,154,1,12,30
3,1,18,1,3,"new@1-3@src/b.rs","src/b.rs","new","new",1,3,40,0,0
'''


class Read(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "lizard.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def test_rows_with_commas_in_the_signature(self):
        self.path.write_text(CSV)
        funcs = quality_metrics.read(self.path)
        self.assertEqual(len(funcs), 3)
        self.assertEqual(funcs[1], {"file": "src/a.rs", "name": "big", "start": 60, "nloc": 90, "ccn": 20,
                                    "length": 95, "fan_in": 1, "fan_out": 12})

    def test_a_csv_without_fan_in_out_is_refused(self):
        self.path.write_text('6,2,61,2,6,"fmt@46-51@src/a.rs","src/a.rs","fmt","fmt",46,51\n')
        with self.assertRaisesRegex(ValueError, "make quality"):
            quality_metrics.read(self.path)

    def test_file_lengths_from_disk_and_a_gone_file_left_out(self):
        (self.root / "src").mkdir()
        (self.root / "src/a.rs").write_text("fn a() {}\n" * 7)
        self.path.write_text(CSV)
        lengths = quality_metrics.file_lengths(quality_metrics.read(self.path), self.root)
        self.assertEqual(lengths, {"src/a.rs": 7})


class Summary(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
        tmp.write(CSV)
        tmp.close()
        self.funcs = quality_metrics.read(tmp.name)
        Path(tmp.name).unlink()

    def test_over_the_limits_and_the_worst_first(self):
        q = quality_metrics.summary(self.funcs, {"src/a.rs": 200, "src/b.rs": 300}, ccn_max=15, length_max=80, top=2)
        self.assertEqual(q["functions"], 3)
        self.assertAlmostEqual(q["ccn_avg"], 23 / 3)
        self.assertEqual([f["name"] for f in q["over_ccn"]], ["big"])
        self.assertEqual([f["name"] for f in q["over_length"]], ["big"])
        self.assertEqual([f["name"] for f in q["by_ccn"]], ["big", "fmt"])
        self.assertEqual([f["name"] for f in q["by_fan_in"]], ["new", "big"])
        self.assertEqual(q["longest_files"], [("src/b.rs", 300), ("src/a.rs", 200)])

    def test_nothing_scanned(self):
        q = quality_metrics.summary([], {}, 15, 80)
        self.assertEqual((q["functions"], q["ccn_avg"], q["by_ccn"]), (0, 0.0, []))


if __name__ == "__main__":
    unittest.main()
