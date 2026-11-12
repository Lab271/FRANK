"""Tests for scripts/version.py: python3 -m unittest discover -s scripts -p 'test_*.py'"""

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import version

FILES = {
    "Cargo.toml": '[workspace]\nmembers = []\n\n[workspace.package]\nversion = "0.41.0"\nedition = "2021"\n',
    "Cargo.lock": '[[package]]\nname = "frank"\nversion = "0.41.0"\n\n[[package]]\nname = "frank-core"\n'
                  'version = "0.41.0"\n\n[[package]]\nname = "serde"\nversion = "1.0.0"\n',
    "fuzz/Cargo.lock": '[[package]]\nname = "frank-core"\nversion = "0.41.0"\n',
    "README.md": "# FRANK\n\n## Version: 0.41.0\n",
    "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- A thing (#1).\n\n"
                    "## [0.41.0] - 2026-11-11\n\n- MCP.\n\n## [0.40.0] - 2026-11-10\n",
}


class Version(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name, text in FILES.items():
            self.write(name, text)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def read(self, name):
        return (self.root / name).read_text()

    def test_all_places_agree(self):
        self.assertEqual(version.drift(self.root), ("0.41.0", []))

    def test_a_stale_place_is_drift(self):
        self.write("README.md", "## Version: 0.38.2\n")
        current, problems = version.drift(self.root)
        self.assertEqual(current, "0.41.0")
        self.assertEqual(problems, ["README.md: 0.38.2 (Cargo.toml says 0.41.0)"])

    def test_next_version(self):
        self.assertEqual(version.next_version("0.41.3", "patch"), "0.41.4")
        self.assertEqual(version.next_version("0.41.3", "minor"), "0.42.0")
        self.assertEqual(version.next_version("0.41.3", "major"), "1.0.0")

    def test_bump_writes_every_place_and_dates_the_changelog(self):
        new = version.bump("minor", self.root, today=dt.date(2026, 11, 12))
        self.assertEqual(new, "0.42.0")
        self.assertEqual(version.drift(self.root), ("0.42.0", []))
        self.assertIn('name = "serde"\nversion = "1.0.0"', self.read("Cargo.lock"))
        self.assertIn("## [Unreleased]\n\n## [0.42.0] - 2026-11-12\n\n### Added\n\n- A thing (#1).\n\n"
                      "## [0.41.0] - 2026-11-11", self.read("CHANGELOG.md"))

    def test_bump_refuses_an_empty_unreleased(self):
        self.write("CHANGELOG.md", "## [Unreleased]\n\n## [0.41.0] - 2026-11-11\n")
        with self.assertRaises(SystemExit):
            version.bump("patch", self.root)
        self.assertIn('version = "0.41.0"', self.read("Cargo.toml"))

    def test_bump_refuses_on_drift(self):
        self.write("fuzz/Cargo.lock", '[[package]]\nname = "frank-core"\nversion = "0.40.0"\n')
        with self.assertRaises(SystemExit):
            version.bump("patch", self.root)
        self.assertIn('version = "0.41.0"', self.read("Cargo.toml"))


if __name__ == "__main__":
    unittest.main()
