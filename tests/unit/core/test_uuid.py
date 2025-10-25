from frank.core import gen_id

"""
FRANK Platform - Unit Test: gen_id Utility
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

Unit tests for the gen_id function, which generates deterministic STIX-compatible UUIDs for FRANK entities.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import uuid
import unittest

class TestGenId(unittest.TestCase):
    def test_gen_id_empty_string(self):
        """Test gen_id with empty string value yields a valid UUID."""
        id_str = gen_id("custom", "")
        self.assertTrue(id_str.startswith("custom--"))
        self.assertIsInstance(uuid.UUID(id_str.split("--", 1)[-1]), uuid.UUID)

    def test_gen_id_missing_value(self):
        """Test gen_id with missing value argument yields a valid UUID."""
        id_str = gen_id("custom")
        self.assertTrue(id_str.startswith("custom--"))
        self.assertIsInstance(uuid.UUID(id_str.split("--", 1)[-1]), uuid.UUID)

    def test_gen_id_deterministic(self):
        """Test that gen_id returns the same UUID for identical input."""
        id1 = gen_id("ipv4-addr", "185.220.102.45")
        id2 = gen_id("ipv4-addr", "185.220.102.45")
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("ipv4-addr--"))
        self.assertIsInstance(uuid.UUID(id1.split("--", 1)[-1]), uuid.UUID)

    def test_gen_id_type_prefix(self):
        """Test that different type_prefix yields different IDs."""
        id1 = gen_id("ipv4-addr", "185.220.102.45")
        id2 = gen_id("domain-name", "185.220.102.45")
        self.assertNotEqual(id1, id2)
        self.assertTrue(id2.startswith("domain-name--"))

    def test_gen_id_value(self):
        """Test that different value yields different IDs."""
        id1 = gen_id("ipv4-addr", "185.220.102.45")
        id2 = gen_id("ipv4-addr", "8.8.8.8")
        self.assertNotEqual(id1, id2)

    def test_gen_id_uuid_format(self):
        """Test that the returned ID contains a valid UUID."""
        id_str = gen_id("file", "testfile.txt")
        prefix, uuid_str = id_str.split("--", 1)
        self.assertEqual(prefix, "file")
        self.assertIsInstance(uuid.UUID(uuid_str), uuid.UUID)

    def test_gen_id_empty_value(self):
        """Test edge case: empty value still yields a valid UUID."""
        id_str = gen_id("custom", "")
        self.assertTrue(id_str.startswith("custom--"))
        self.assertIsInstance(uuid.UUID(id_str.split("--", 1)[-1]), uuid.UUID)

    def test_gen_id_special_chars(self):
        """Test edge case: special characters in value yield a valid UUID."""
        id_str = gen_id("artifact", "foo@bar.com/123")
        self.assertTrue(id_str.startswith("artifact--"))
        self.assertIsInstance(uuid.UUID(id_str.split("--", 1)[-1]), uuid.UUID)

if __name__ == "__main__":
    unittest.main()
