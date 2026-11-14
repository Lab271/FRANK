"""Tests for scripts/quality_metrics.py: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import io
import tempfile
import unittest
from pathlib import Path

import quality_metrics

# lizard 1.25.1 -l rust --csv: nloc, ccn, token, param, length, location, file,
# name, long_name (quoted, may hold commas), start, end
CSV = '''6,2,61,2,6,"fmt@46-51@src/a.rs","src/a.rs","fmt","fmt & self , f : & mut Formatter",46,51
90,20,900,3,95,"big@60-154@src/a.rs","src/a.rs","big","big a , b , c",60,154
3,1,18,1,3,"new@1-3@src/b.rs","src/b.rs","new","new",1,3
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
                                    "length": 95})

    def test_a_csv_with_other_columns_is_refused(self):
        # lizard -Eio adds fan_in, fan_out, general_fan_out: not read (#298)
        self.path.write_text('6,2,61,2,6,"fmt@46-51@src/a.rs","src/a.rs","fmt","fmt",46,51,0,0,0\n')
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
        self.assertEqual(q["longest_files"], [("src/b.rs", 300), ("src/a.rs", 200)])

    def test_nothing_scanned(self):
        q = quality_metrics.summary([], {}, 15, 80)
        self.assertEqual((q["functions"], q["ccn_avg"], q["by_ccn"]), (0, 0.0, []))


def fn(file, name, ccn):
    return {"file": file, "name": name, "start": 1, "nloc": 1, "ccn": ccn, "length": 1}


class Baseline(unittest.TestCase):
    """The CCN baseline (#301): over the limit only as listed, and the list only shrinks."""

    BASE = {("a.rs", "big"): 20, ("a.rs", "fixed"): 18, ("b.rs", "gone"): 30}

    def test_the_same_code_passes(self):
        funcs = [fn("a.rs", "big", 20), fn("a.rs", "fixed", 18), fn("b.rs", "gone", 30), fn("a.rs", "small", 3)]
        self.assertEqual(quality_metrics.ratchet(funcs, self.BASE, 15), ([], [], []))

    def test_new_grew_and_stale(self):
        funcs = [fn("a.rs", "big", 21), fn("a.rs", "fixed", 15), fn("c.rs", "fresh", 16)]
        new, grew, stale = quality_metrics.ratchet(funcs, self.BASE, 15)
        self.assertEqual([f["name"] for f in new], ["fresh"])
        self.assertEqual([(f["name"], b) for f, b in grew], [("big", 20)])
        self.assertEqual(stale, [("a.rs", "fixed", 18), ("b.rs", "gone", 30)])

    def test_better_but_still_over_passes(self):
        funcs = [fn("a.rs", "big", 17), fn("a.rs", "fixed", 18), fn("b.rs", "gone", 30)]
        self.assertEqual(quality_metrics.ratchet(funcs, self.BASE, 15), ([], [], []))

    def test_a_repeated_name_counts_at_its_worst(self):
        # two `new` in one file (one per impl block): the key stands for both
        funcs = [fn("a.rs", "new", 16), fn("a.rs", "new", 3)]
        self.assertEqual(quality_metrics.worst_per_name(funcs)[("a.rs", "new")]["ccn"], 16)
        self.assertEqual(quality_metrics.ratchet(funcs, {("a.rs", "new"): 16}, 15), ([], [], []))

    def test_written_and_read_back(self):
        funcs = [fn("a.rs", "big", 20), fn("a.rs", "new", 16), fn("a.rs", "new", 3), fn("b.rs", "ok", 15)]
        out = io.StringIO()
        quality_metrics.write_baseline(funcs, 15, out)
        self.assertEqual(out.getvalue(), "file,function,ccn\na.rs,big,20\na.rs,new,16\n")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "baseline.csv"
            path.write_text(out.getvalue())
            self.assertEqual(quality_metrics.read_baseline(path), {("a.rs", "big"): 20, ("a.rs", "new"): 16})
            path.write_text("name,ccn\nbig,20\n")
            with self.assertRaisesRegex(ValueError, "make quality-baseline"):
                quality_metrics.read_baseline(path)


if __name__ == "__main__":
    unittest.main()
