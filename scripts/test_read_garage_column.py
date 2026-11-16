"""Tests for scripts/read-garage-column.sh (#330): python3 -m unittest discover -s scripts -p 'test_*.py'

A stub column-rs prints its version and echoes the location it is given.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("read-garage-column.sh")
STUB = """#!/bin/sh
[ "$1" = --version ] && { echo "column-rs 0.46.0"; exit 0; }
echo "location=$3"
"""
URL = "s3://b/sightings?endpoint=https://s3.example&region=eu01"
KEYS = {"AWS_ACCESS_KEY_ID": "id", "AWS_SECRET_ACCESS_KEY": "secret"}


class ReadGarageColumn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.stub = root / "column-rs"
        self.stub.write_text(STUB)
        self.stub.chmod(0o755)
        # Sourcing this file would leave a marker: it must never be read with URL set.
        self.marker = root / "sourced"
        self.env_file = root / "frank.env"
        self.env_file.write_text(f"touch {self.marker}\nAWS_ACCESS_KEY_ID=garage\nAWS_SECRET_ACCESS_KEY=garage\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith("AWS_")}
        base.update(COLUMN_RS=str(self.stub), FRANK_S3_ENV=str(self.env_file), NO_COLOR="1")
        base.update(env)
        return subprocess.run([str(SCRIPT), "SELECT 1"], env=base, capture_output=True, text=True)

    def location(self, **env):
        r = self.run_script(**KEYS, **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip().removeprefix("location=")

    def test_url_audit_inserts_audit_before_query(self):
        self.assertEqual(self.location(URL=URL, TABLE="audit"),
                         "s3://b/sightings/audit?endpoint=https://s3.example&region=eu01")

    def test_url_already_audit_is_left_alone(self):
        url = "s3://b/sightings/audit?region=eu-central-1"
        self.assertEqual(self.location(URL=url, TABLE="audit"), url)

    def test_url_audit_without_query(self):
        self.assertEqual(self.location(URL="s3://b/sightings/", TABLE="audit"), "s3://b/sightings/audit")

    def test_url_sightings_as_given(self):
        self.assertEqual(self.location(URL=URL), URL)

    def test_url_without_keys_fails_and_never_reads_garage_env(self):
        r = self.run_script(URL=URL)
        self.assertEqual(r.returncode, 1)
        self.assertIn("export-credentials", r.stderr)
        self.assertFalse(self.marker.exists(), "s3/frank.env was sourced for another endpoint")

    def test_url_with_only_one_key_fails(self):
        r = self.run_script(URL=URL, AWS_ACCESS_KEY_ID="id")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.marker.exists())

    def test_garage_default_still_reads_env_file(self):
        r = self.run_script(TLS="0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.marker.exists())
        self.assertEqual(r.stdout.strip(), "location=s3://frank/sightings?endpoint=http://127.0.0.1:3900&region=garage")


if __name__ == "__main__":
    unittest.main()
