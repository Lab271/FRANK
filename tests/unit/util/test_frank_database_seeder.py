#!/usr/bin/env python3
"""
FRANK Platform - Unit tests for FRANK Database Seeder module

Tests abstract seeder class, concrete seeder implementations, and sample data generation

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from unittest.mock import Mock, call

from frank.util.sample_builder import SampleDataSeeder, create_demo_orgs, FRANKDatabaseSeeder
from frank.storage.base import BaseFRANKDatabase


class TestFRANKDatabaseSeeder(unittest.TestCase):
    """Unit tests for FRANKDatabaseSeeder abstract class."""
    def test_cannot_instantiate_abstract(self):
        """Cannot instantiate abstract base class."""
        with self.assertRaises(TypeError):
            FRANKDatabaseSeeder()

    def test_subclass_must_implement_seed(self):
        """Subclass without seed method raises TypeError."""
        class IncompleteSeeder(FRANKDatabaseSeeder):
            pass
        with self.assertRaises(TypeError):
            IncompleteSeeder()

    def test_subclass_can_implement_seed(self):
        """Concrete subclass with seed method works."""
        from unittest.mock import Mock
        class ConcreteSeeder(FRANKDatabaseSeeder):
            def seed(self, db_client: BaseFRANKDatabase) -> None:
                self.called = True
        seeder = ConcreteSeeder()
        db_client = Mock(spec=BaseFRANKDatabase)
        seeder.seed(db_client)
        self.assertTrue(hasattr(seeder, 'called'))
        self.assertTrue(seeder.called)

    def test_abstract_method(self):
        """Concrete subclass to cover abstract method."""
        from unittest.mock import Mock
        class ConcreteSeeder(FRANKDatabaseSeeder):
            def seed(self, db_client: BaseFRANKDatabase) -> None:
                super().seed(db_client)
                self.called = True
        seeder = ConcreteSeeder()
        db_client = Mock(spec=BaseFRANKDatabase)
        seeder.seed(db_client)
        self.assertTrue(hasattr(seeder, 'called'))
        self.assertTrue(seeder.called)


class TestSampleDataSeeder(unittest.TestCase):
    """Unit tests for SampleDataSeeder class."""
    def test_seed_calls_upsert_and_store(self):
        """Seeder calls upsert_organisation and store_submission."""
        db_client = Mock(spec=BaseFRANKDatabase)
        seeder = SampleDataSeeder()
        result = seeder.seed(db_client)
        # Should call upsert_organisation for each demo org
        demo_orgs = create_demo_orgs(id_fixed=True)
        upsert_calls = [call(org) for org in demo_orgs]
        db_client.upsert_organisation.assert_has_calls(upsert_calls, any_order=True)
        # Should call store_submission 5 times
        self.assertEqual(db_client.store_submission.call_count, 5)
        self.assertTrue(result)

    def test_seed_returns_true(self):
        """Seeder returns True after seeding."""
        db_client = Mock(spec=BaseFRANKDatabase)
        seeder = SampleDataSeeder()
        self.assertTrue(seeder.seed(db_client))

    def test_seed_demo_submissions_content(self):
        """Seeder stores submissions with correct content."""
        db_client = Mock(spec=BaseFRANKDatabase)
        seeder = SampleDataSeeder()
        seeder.seed(db_client)
        # Check that all submissions have correct org_id and access_level
        for i in range(5):
            expected_confidence = 70 + i * 5
            args, _ = db_client.store_submission.call_args_list[i]
            submission = args[0]
            self.assertEqual(submission.submitter.organisation_id, "demo-partner-org")
            self.assertEqual(submission.submitter.access_level, "partner")
            self.assertEqual(submission.sighting.confidence, expected_confidence)

if __name__ == "__main__":
    unittest.main()
