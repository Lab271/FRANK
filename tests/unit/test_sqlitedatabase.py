#!/usr/bin/env python3
"""
FRANK Platform - Unit Tests
Comprehensive test suite for FRANK database and sample builder components
"""

import unittest
import tempfile
import os
import sqlite3
from datetime import datetime, timezone

# Import the modules we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from frank.db.sqlite import SQLiteFRANKDatabase, create_sqlite_database


class TestSQLiteFRANKDatabase(unittest.TestCase):
    """Test cases for SQLiteFRANKDatabase class"""
    
    def setUp(self):
        """Set up test database for each test"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.db = SQLiteFRANKDatabase(self.db_path)
        
    def tearDown(self):
        """Clean up after each test"""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_database_initialization(self):
        """Test that database initializes with correct schema"""
        # Check if database file exists
        self.assertTrue(os.path.exists(self.db_path))
        
        # Check if tables are created
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
        expected_tables = [
            'organizations', 'submissions', 'sightings', 'observables',
            'observable_statistics', 'access_logs', 'sigma_rules', 'campaigns'
        ]
        
        for table in expected_tables:
            self.assertIn(table, tables)

    def test_hash_observable(self):
        """Test observable hashing function"""
        hash1 = self.db.hash_observable("ipv4", "192.168.1.1")
        hash2 = self.db.hash_observable("ipv4", "192.168.1.1")
        hash3 = self.db.hash_observable("ipv4", "192.168.1.2")
        
        # Same input should produce same hash
        self.assertEqual(hash1, hash2)
        # Different input should produce different hash
        self.assertNotEqual(hash1, hash3)
        # Hash should be SHA256 hex string
        self.assertEqual(len(hash1), 64)            

    def test_upsert_organization(self):
        """Test organization creation and updates"""
        org_data = {
            "organization_id": "test-org-1",
            "tier": "partner",
            "sector": "finance",
            "region": "nl_north_holland",
            "client_count": 5
        }
        
        result = self.db.upsert_organization(org_data)
        self.assertTrue(result)
        
        # Verify organization was stored
        stored_org = self.db.get_organization_info("test-org-1")
        self.assertIsNotNone(stored_org)
        self.assertEqual(stored_org['tier'], 'partner')
        self.assertEqual(stored_org['sector'], 'finance')
        self.assertEqual(stored_org['client_count'], 5)

    def test_store_submission_minimal(self):
        """Test storing a minimal submission"""
        submission = {
            "submission": {
                "submitter": {
                    "organization_id": "test-org-1",
                    "tier": "partner"
                },
                "sighting": {
                    "sighting_id": "test-sighting-1",
                    "confidence": 85,
                    "observables": {
                        "network": [
                            {
                                "id": "test-obs-1",
                                "type": "ipv4",
                                "value": "192.168.1.100"
                            }
                        ]
                    }
                },
                "metadata": {
                    "submission_id": "test-sub-1",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }
        
        result = self.db.store_submission(submission)
        self.assertTrue(result)
        
        # Verify submission was stored
        stored_submission = self.db.get_submission_by_id("test-sub-1", "test-org-1")
        self.assertIsNotNone(stored_submission)

    # def test_store_submission_comprehensive(self):
    #     """Test storing a comprehensive submission with all fields"""
    #     submission = {
    #         "submission": {
    #             "submitter": {
    #                 "organization_id": "test-org-2",
    #                 "tier": "core_member",
    #                 "sector": "cybersecurity_services"
    #             },
    #             "hit_target": {
    #                 "organization_id": "test-victim-1",
    #                 "sector": "financial_services"
    #             },
    #             "sighting": {
    #                 "sighting_id": "test-sighting-2",
    #                 "confidence": 92,
    #                 "severity": "high",
    #                 "first_observed": "2025-01-20T13:15:00Z",
    #                 "last_observed": "2025-01-20T14:25:00Z",
    #                 "observation_count": 23,
    #                 "observables": {
    #                     "network": [
    #                         {
    #                             "id": "test-obs-2",
    #                             "type": "ipv4",
    #                             "value": "185.220.102.45",
    #                             "role": "c2_server",
    #                             "port": 443
    #                         },
    #                         {
    #                             "id": "test-obs-3",
    #                             "type": "domain",
    #                             "value": "malicious.example.com"
    #                         }
    #                     ]
    #                 },
    #                 "sigma_detection": {
    #                     "rule_id": "sigma-test-rule-1",
    #                     "rule_name": "Test SIGMA Rule",
    #                     "rule_version": "1.0",
    #                     "rule_status": "stable",
    #                     "sigma_yaml": "title: Test Rule\ndetection:\n  condition: test",
    #                     "rule_effectiveness": 0.89,
    #                     "false_positive_rate": 0.03
    #                 },
    #                 "threat_context": {
    #                     "campaign": {
    #                         "id": "test-campaign-1",
    #                         "name": "Test Campaign",
    #                         "attribution": "unknown_group",
    #                         "target_sectors": ["financial"],
    #                         "confidence": 78
    #                     }
    #                 }
    #             },
    #             "metadata": {
    #                 "submission_id": "test-sub-2",
    #                 "timestamp": datetime.now(timezone.utc).isoformat(),
    #                 "format_version": "1.0"
    #             }
    #         }
    #     }
        
    #     result = self.db.store_submission(submission)
    #     self.assertTrue(result)
        
    #     # Verify all components were stored
    #     stored_submission = self.db.get_submission_by_id("test-sub-2", "test-org-2")
    #     self.assertIsNotNone(stored_submission)
        
    #     # Check SIGMA rule was stored
    #     sigma_rules = self.db.get_sigma_rules("test-org-2")
    #     self.assertEqual(len(sigma_rules), 1)
    #     self.assertEqual(sigma_rules[0]['rule_name'], 'Test SIGMA Rule')
        
    #     # Check campaign was stored
    #     campaigns = self.db.get_campaigns("test-org-2")
    #     self.assertEqual(len(campaigns), 1)
    #     self.assertEqual(campaigns[0]['campaign_name'], 'Test Campaign')
    
    # def test_query_observables(self):
    #     """Test querying observables with various filters"""
    #     # First store a submission with observables
    #     submission = {
    #         "submission": {
    #             "submitter": {
    #                 "organization_id": "test-org-3",
    #                 "tier": "contributor",
    #                 "sector": "healthcare"
    #             },
    #             "sighting": {
    #                 "sighting_id": "test-sighting-3",
    #                 "confidence": 75,
    #                 "observables": {
    #                     "network": [
    #                         {
    #                             "id": "test-obs-4",
    #                             "type": "ipv4",
    #                             "value": "10.0.0.1"
    #                         },
    #                         {
    #                             "id": "test-obs-5",
    #                             "type": "domain",
    #                             "value": "test.malware.com"
    #                         }
    #                     ]
    #                 }
    #             },
    #             "metadata": {
    #                 "submission_id": "test-sub-3"
    #             }
    #         }
    #     }
        
    #     self.db.store_submission(submission)
        
    #     # Query all observables
    #     results = self.db.query_observables("test-org-3")
    #     self.assertGreaterEqual(len(results), 2)
        
    #     # Query with type filter
    #     ip_results = self.db.query_observables("test-org-3", observable_type="ipv4")
    #     self.assertGreaterEqual(len(ip_results), 1)
        
    #     # Query with confidence filter
    #     high_conf_results = self.db.query_observables(
    #         "test-org-3", 
    #         min_confidence=80,
    #         access_level="contributor"
    #     )
    #     # Should return empty since our submission has confidence 75
    #     self.assertEqual(len(high_conf_results), 0)
    
    # def test_access_level_filtering(self):
    #     """Test that access level filtering works correctly"""
    #     # Create a test submission
    #     submission = {
    #         "submission": {
    #             "submitter": {
    #                 "organization_id": "test-org-4",
    #                 "tier": "partner"
    #             },
    #             "hit_target": {
    #                 "organization_id": "test-victim-2",
    #                 "sector": "retail"
    #             },
    #             "sighting": {
    #                 "sighting_id": "test-sighting-4",
    #                 "confidence": 90,
    #                 "observables": {
    #                     "network": [
    #                         {
    #                             "id": "test-obs-6",
    #                             "type": "ipv4",
    #                             "value": "203.0.113.1"
    #                         }
    #                     ]
    #                 }
    #             },
    #             "metadata": {
    #                 "submission_id": "test-sub-4"
    #             }
    #         }
    #     }
        
    #     self.db.store_submission(submission)
        
    #     # Test different access levels
    #     public_data = self.db.get_submission_by_id("test-sub-4", "test-org-4", "public")
    #     observer_data = self.db.get_submission_by_id("test-sub-4", "test-org-4", "observer")
    #     contributor_data = self.db.get_submission_by_id("test-sub-4", "test-org-4", "contributor")
    #     partner_data = self.db.get_submission_by_id("test-sub-4", "test-org-4", "partner")
        
    #     # Public should have minimal data
    #     self.assertIn('submission', public_data)
    #     self.assertNotIn('hit_target', public_data['submission'])
        
    #     # Observer should have slightly more but masked values
    #     self.assertIn('submission', observer_data)
        
    #     # Contributor should have more complete data but anonymized hit_target
    #     self.assertIn('submission', contributor_data)
        
    #     # Partner should have complete access
    #     self.assertIn('submission', partner_data)
    #     self.assertIn('hit_target', partner_data['submission'])
    
    def test_search_observables_by_value(self):
        """Test searching observables by value"""
        # Store test data
        submission = {
            "submission": {
                "submitter": {
                    "organization_id": "test-org-5",
                    "tier": "observer"
                },
                "sighting": {
                    "sighting_id": "test-sighting-5",
                    "confidence": 80,
                    "observables": {
                        "network": [
                            {
                                "id": "test-obs-7",
                                "type": "domain",
                                "value": "example.malicious.com"
                            }
                        ]
                    }
                },
                "metadata": {
                    "submission_id": "test-sub-5"
                }
            }
        }
        
        self.db.store_submission(submission)
        
        # Search for partial matches
        results = self.db.search_observables_by_value("test-org-5", "malicious")
        self.assertGreaterEqual(len(results), 1)
        
        # Search for exact match
        results = self.db.search_observables_by_value("test-org-5", "example.malicious.com")
        self.assertGreaterEqual(len(results), 1)
    
    def test_statistics_summary(self):
        """Test getting platform statistics"""
        # Store some test data first
        for i in range(3):
            submission = {
                "submission": {
                    "submitter": {
                        "organization_id": f"test-org-stats-{i}",
                        "tier": "contributor",
                        "sector": "technology"
                    },
                    "sighting": {
                        "sighting_id": f"test-sighting-stats-{i}",
                        "confidence": 70 + i * 10,
                        "severity": "medium",
                        "observables": {
                            "network": [
                                {
                                    "id": f"test-obs-stats-{i}",
                                    "type": "ipv4",
                                    "value": f"10.0.0.{i + 10}"
                                }
                            ]
                        }
                    },
                    "metadata": {
                        "submission_id": f"test-sub-stats-{i}"
                    }
                }
            }
            
            self.db.store_submission(submission)
        
        stats = self.db.get_statistics_summary("test-org-stats-0")
        
        # Verify statistics structure
        self.assertIn('total_submissions', stats)
        self.assertIn('active_organizations', stats)
        self.assertIn('observable_types', stats)
        self.assertIn('severity_distribution', stats)
        
        # Verify some basic counts
        self.assertGreaterEqual(stats['total_submissions'], 3)
        self.assertGreaterEqual(stats['active_organizations'], 3)
    
    def test_cleanup_old_data(self):
        """Test data cleanup functionality"""
        # Store some test data
        submission = {
            "submission": {
                "submitter": {
                    "organization_id": "test-org-cleanup",
                    "tier": "contributor"
                },
                "sighting": {
                    "sighting_id": "test-sighting-cleanup",
                    "confidence": 85,
                    "observables": {
                        "network": [
                            {
                                "id": "test-obs-cleanup",
                                "type": "ipv4",
                                "value": "10.0.0.99"
                            }
                        ]
                    }
                },
                "metadata": {
                    "submission_id": "test-sub-cleanup"
                }
            }
        }
        
        self.db.store_submission(submission)
        
        # Test cleanup (with 0 days to clean everything)
        deleted_count = self.db.cleanup_old_data(0)
        self.assertGreaterEqual(deleted_count, 0)
    
    def test_health_check(self):
        """Test database health check"""
        health_status = self.db.health_check()
        
        self.assertEqual(health_status['status'], 'healthy')
        self.assertIn('database_path', health_status)
        self.assertIn('table_counts', health_status)
        self.assertIn('timestamp', health_status)
    
    def test_log_access(self):
        """Test access logging functionality"""
        result = self.db.log_access(
            "test-org-log", 
            "TEST_ACTION", 
            "test_resource", 
            "test-resource-1",
            {"test": "details"}
        )
        self.assertTrue(result)
        
        # Retrieve logs
        logs = self.db.get_access_logs("test-org-log")
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]['action'], 'TEST_ACTION')
    
    def test_factory_function(self):
        """Test the factory function for creating database instances"""
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()
        temp_path = temp_file.name
        
        try:
            db = create_sqlite_database(temp_path)
            self.assertIsInstance(db, SQLiteFRANKDatabase)
            self.assertEqual(db.db_path, temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
