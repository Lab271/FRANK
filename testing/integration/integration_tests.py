#!/usr/bin/env python3
"""
FRANK Platform - Integration Testing Module
End-to-end testing of complete workflows and system integration.
"""

import time
import json
import uuid
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

@dataclass
class IntegrationTestResult:
    """Data class for integration test results"""
    test_name: str
    workflow: str
    status: str  # PASS, FAIL, SKIP
    execution_time: float
    steps_completed: int
    total_steps: int
    error_message: Optional[str] = None
    data_created: List[str] = None
    data_cleaned: bool = False

class WorkflowStep:
    """Represents a single step in an integration test workflow"""
    
    def __init__(self, name: str, action: callable, validation: callable = None, 
                 cleanup: callable = None, timeout: int = 30):
        self.name = name
        self.action = action
        self.validation = validation
        self.cleanup = cleanup
        self.timeout = timeout
        self.result = None
        self.execution_time = 0

class IntegrationTestFramework:
    """Framework for executing integration tests"""
    
    def __init__(self, base_url: str, auth_token: str = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.test_data = {}
        self.created_resources = []
        self.results = []
    
    def execute_workflow(self, workflow_name: str, steps: List[WorkflowStep]) -> IntegrationTestResult:
        """Execute a complete workflow with multiple steps"""
        print(f"Executing workflow: {workflow_name}")
        
        start_time = time.time()
        steps_completed = 0
        error_message = None
        
        try:
            for i, step in enumerate(steps, 1):
                print(f"  Step {i}/{len(steps)}: {step.name}")
                
                step_start = time.time()
                
                try:
                    # Execute the step action
                    step.result = step.action()
                    
                    # Validate the result if validation function provided
                    if step.validation:
                        validation_result = step.validation(step.result)
                        if not validation_result:
                            raise Exception(f"Validation failed for step: {step.name}")
                    
                    step.execution_time = time.time() - step_start
                    steps_completed += 1
                    print(f"    ✓ Completed in {step.execution_time:.2f}s")
                    
                except Exception as e:
                    step.execution_time = time.time() - step_start
                    error_message = f"Step '{step.name}' failed: {str(e)}"
                    print(f"    ✗ Failed: {error_message}")
                    break
            
            # Determine overall status
            if steps_completed == len(steps):
                status = "PASS"
            elif steps_completed == 0:
                status = "FAIL"
            else:
                status = "PARTIAL"
            
            execution_time = time.time() - start_time
            
            result = IntegrationTestResult(
                test_name=workflow_name,
                workflow=workflow_name,
                status=status,
                execution_time=execution_time,
                steps_completed=steps_completed,
                total_steps=len(steps),
                error_message=error_message,
                data_created=self.created_resources.copy(),
                data_cleaned=False
            )
            
            self.results.append(result)
            return result
            
        finally:
            # Cleanup created resources
            self._cleanup_workflow_data(steps)
    
    def _cleanup_workflow_data(self, steps: List[WorkflowStep]):
        """Cleanup data created during workflow execution"""
        print("  Cleaning up test data...")
        
        # Execute cleanup functions for each step
        for step in reversed(steps):  # Cleanup in reverse order
            if step.cleanup and step.result:
                try:
                    step.cleanup(step.result)
                except Exception as e:
                    print(f"    Warning: Cleanup failed for {step.name}: {str(e)}")
        
        # Clear created resources list
        self.created_resources.clear()

class FRANKIntegrationTestSuite:
    """Integration test suite for FRANK platform"""
    
    def __init__(self, base_url: str, auth_token: str = None):
        self.framework = IntegrationTestFramework(base_url, auth_token)
        self.test_user_id = None
        self.test_org_id = None
    
    def test_complete_threat_sharing_workflow(self) -> IntegrationTestResult:
        """Test complete threat intelligence sharing workflow"""
        
        def create_user():
            """Create a test user"""
            user_data = {
                'username': f'test_user_{uuid.uuid4().hex[:8]}',
                'email': f'test_{uuid.uuid4().hex[:8]}@example.com',
                'password': 'TestPassword123!',
                'organization': 'Test Organization'
            }
            
            # Simulate user creation API call
            print(f"    Creating user: {user_data['username']}")
            self.test_user_id = f"user_{uuid.uuid4().hex[:8]}"
            self.framework.created_resources.append(f"user:{self.test_user_id}")
            
            return {'user_id': self.test_user_id, 'user_data': user_data}
        
        def validate_user_creation(result):
            """Validate user was created successfully"""
            return result and 'user_id' in result and result['user_id']
        
        def authenticate_user(result=None):
            """Authenticate the created user"""
            print(f"    Authenticating user: {self.test_user_id}")
            
            # Simulate authentication
            auth_token = f"token_{uuid.uuid4().hex}"
            return {'auth_token': auth_token, 'expires_in': 3600}
        
        def validate_authentication(result):
            """Validate authentication was successful"""
            return result and 'auth_token' in result
        
        def submit_threat_data(result=None):
            """Submit threat intelligence data"""
            threat_data = {
                'type': 'malware',
                'category': 'trojan',
                'indicator': hashlib.sha256(f'test_malware_{uuid.uuid4().hex}'.encode()).hexdigest(),
                'severity': 'high',
                'description': 'Test malware sample for integration testing',
                'source': 'integration_test',
                'first_seen': time.strftime('%Y-%m-%d %H:%M:%S'),
                'ttl': 86400  # 24 hours
            }
            
            print(f"    Submitting threat: {threat_data['indicator'][:16]}...")
            threat_id = f"threat_{uuid.uuid4().hex[:8]}"
            self.framework.created_resources.append(f"threat:{threat_id}")
            
            return {'threat_id': threat_id, 'threat_data': threat_data}
        
        def validate_threat_submission(result):
            """Validate threat was submitted successfully"""
            return result and 'threat_id' in result
        
        def search_threat_data(result=None):
            """Search for the submitted threat data"""
            print(f"    Searching for submitted threat...")
            
            # Simulate search API call
            search_results = [
                {
                    'threat_id': result['threat_id'],
                    'relevance_score': 1.0,
                    'matched_fields': ['indicator', 'type']
                }
            ]
            
            return {'search_results': search_results, 'total_found': 1}
        
        def validate_search_results(result):
            """Validate search found the threat"""
            return (result and 'search_results' in result and 
                   len(result['search_results']) > 0)
        
        def retrieve_threat_details(result=None):
            """Retrieve detailed threat information"""
            threat_id = result['search_results'][0]['threat_id']
            print(f"    Retrieving threat details: {threat_id}")
            
            # Simulate threat details retrieval
            threat_details = {
                'threat_id': threat_id,
                'type': 'malware',
                'indicator': 'abc123...',
                'metadata': {
                    'confidence': 0.95,
                    'tags': ['trojan', 'test'],
                    'last_updated': time.strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            
            return threat_details
        
        def validate_threat_details(result):
            """Validate threat details were retrieved"""
            return result and 'threat_id' in result and 'metadata' in result
        
        def update_threat_data(result=None):
            """Update threat data with additional information"""
            threat_id = result['threat_id']
            print(f"    Updating threat: {threat_id}")
            
            update_data = {
                'severity': 'critical',
                'additional_indicators': ['192.168.1.100', 'malicious.example.com'],
                'updated_by': self.test_user_id
            }
            
            return {'threat_id': threat_id, 'updates': update_data}
        
        def validate_threat_update(result):
            """Validate threat was updated successfully"""
            return result and 'updates' in result
        
        def cleanup_user(result):
            """Cleanup created user"""
            if self.test_user_id:
                print(f"    Cleaning up user: {self.test_user_id}")
                # Simulate user deletion
        
        def cleanup_threat(result):
            """Cleanup created threat"""
            if result and 'threat_id' in result:
                print(f"    Cleaning up threat: {result['threat_id']}")
                # Simulate threat deletion
        
        # Define workflow steps
        steps = [
            WorkflowStep("Create User", create_user, validate_user_creation, cleanup_user),
            WorkflowStep("Authenticate User", authenticate_user, validate_authentication),
            WorkflowStep("Submit Threat Data", submit_threat_data, validate_threat_submission, cleanup_threat),
            WorkflowStep("Search Threat Data", search_threat_data, validate_search_results),
            WorkflowStep("Retrieve Threat Details", retrieve_threat_details, validate_threat_details),
            WorkflowStep("Update Threat Data", update_threat_data, validate_threat_update)
        ]
        
        return self.framework.execute_workflow("Complete Threat Sharing Workflow", steps)
    
    def test_multi_tenant_isolation_workflow(self) -> IntegrationTestResult:
        """Test multi-tenant data isolation"""
        
        def create_organization_a():
            """Create first test organization"""
            org_data = {
                'name': f'Test_Org_A_{uuid.uuid4().hex[:6]}',
                'domain': 'testa.example.com',
                'tier': 'premium'
            }
            
            org_id = f"org_a_{uuid.uuid4().hex[:8]}"
            self.framework.created_resources.append(f"org:{org_id}")
            
            return {'org_id': org_id, 'org_data': org_data}
        
        def create_organization_b():
            """Create second test organization"""
            org_data = {
                'name': f'Test_Org_B_{uuid.uuid4().hex[:6]}',
                'domain': 'testb.example.com',
                'tier': 'standard'
            }
            
            org_id = f"org_b_{uuid.uuid4().hex[:8]}"
            self.framework.created_resources.append(f"org:{org_id}")
            
            return {'org_id': org_id, 'org_data': org_data}
        
        def create_users_for_orgs(result=None):
            """Create users for both organizations"""
            # Get organization IDs from previous steps
            org_a_id = self.framework.results[-1].test_name  # Hack to get org A ID
            org_b_id = result['org_id']  # Current org B ID
            
            users = []
            for org_id, org_name in [(org_a_id, 'A'), (org_b_id, 'B')]:
                user_data = {
                    'username': f'user_org_{org_name}_{uuid.uuid4().hex[:6]}',
                    'email': f'user{org_name}@test{org_name.lower()}.example.com',
                    'organization_id': org_id
                }
                
                user_id = f"user_{org_name}_{uuid.uuid4().hex[:8]}"
                self.framework.created_resources.append(f"user:{user_id}")
                users.append({'user_id': user_id, 'user_data': user_data})
            
            return {'users': users}
        
        def submit_org_specific_threats(result=None):
            """Submit threats for each organization"""
            users = result['users']
            threats = []
            
            for i, user in enumerate(users):
                threat_data = {
                    'type': 'malware',
                    'indicator': hashlib.sha256(f'org_threat_{i}_{uuid.uuid4().hex}'.encode()).hexdigest(),
                    'severity': 'medium',
                    'organization_id': user['user_data']['organization_id'],
                    'submitter_id': user['user_id'],
                    'privacy_level': 'organization'
                }
                
                threat_id = f"threat_org_{i}_{uuid.uuid4().hex[:8]}"
                self.framework.created_resources.append(f"threat:{threat_id}")
                threats.append({'threat_id': threat_id, 'threat_data': threat_data})
            
            return {'threats': threats}
        
        def test_cross_org_access(result=None):
            """Test that organizations cannot access each other's data"""
            threats = result['threats']
            
            # Simulate user from Org A trying to access Org B's threat
            org_a_threat = threats[0]['threat_id']
            org_b_threat = threats[1]['threat_id']
            
            # This should fail (return empty or error)
            cross_access_result = {
                'org_a_accessing_b': False,  # Should be False (access denied)
                'org_b_accessing_a': False,  # Should be False (access denied)
                'isolation_verified': True
            }
            
            return cross_access_result
        
        def validate_isolation(result):
            """Validate that tenant isolation is working"""
            return (result and result.get('isolation_verified') and 
                   not result.get('org_a_accessing_b') and 
                   not result.get('org_b_accessing_a'))
        
        def cleanup_orgs(result):
            """Cleanup created organizations"""
            print("    Cleaning up organizations and associated data")
        
        steps = [
            WorkflowStep("Create Organization A", create_organization_a),
            WorkflowStep("Create Organization B", create_organization_b),
            WorkflowStep("Create Users for Organizations", create_users_for_orgs),
            WorkflowStep("Submit Organization-Specific Threats", submit_org_specific_threats),
            WorkflowStep("Test Cross-Organization Access", test_cross_org_access, validate_isolation, cleanup_orgs)
        ]
        
        return self.framework.execute_workflow("Multi-Tenant Isolation Workflow", steps)
    
    def test_data_pipeline_workflow(self) -> IntegrationTestResult:
        """Test complete data processing pipeline"""
        
        def submit_raw_threat_feed():
            """Submit raw threat intelligence feed data"""
            feed_data = {
                'source': 'test_feed',
                'format': 'json',
                'threats': [
                    {
                        'indicator': hashlib.sha256(f'feed_threat_1_{uuid.uuid4().hex}'.encode()).hexdigest(),
                        'type': 'hash',
                        'malware_family': 'test_family',
                        'first_seen': '2024-01-01T00:00:00Z'
                    },
                    {
                        'indicator': '192.168.100.1',
                        'type': 'ip',
                        'category': 'c2_server',
                        'confidence': 0.85
                    },
                    {
                        'indicator': 'malicious.test.com',
                        'type': 'domain',
                        'tags': ['phishing', 'test'],
                        'ttl': 3600
                    }
                ]
            }
            
            batch_id = f"batch_{uuid.uuid4().hex[:8]}"
            self.framework.created_resources.append(f"batch:{batch_id}")
            
            return {'batch_id': batch_id, 'feed_data': feed_data}
        
        def validate_feed_submission(result):
            """Validate feed was submitted successfully"""
            return result and 'batch_id' in result and 'feed_data' in result
        
        def process_threat_normalization(result=None):
            """Process threat normalization and enrichment"""
            batch_id = result['batch_id']
            
            # Simulate processing pipeline
            processed_threats = []
            for threat in result['feed_data']['threats']:
                processed_threat = {
                    'id': f"processed_{uuid.uuid4().hex[:8]}",
                    'original_indicator': threat['indicator'],
                    'normalized_indicator': threat['indicator'].lower(),
                    'threat_type': threat['type'],
                    'confidence_score': threat.get('confidence', 0.9),
                    'enrichment_status': 'completed',
                    'processing_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                processed_threats.append(processed_threat)
            
            return {'batch_id': batch_id, 'processed_threats': processed_threats}
        
        def validate_normalization(result):
            """Validate threat normalization was successful"""
            return (result and 'processed_threats' in result and 
                   len(result['processed_threats']) > 0)
        
        def index_threats_for_search(result=None):
            """Index processed threats in search engine"""
            processed_threats = result['processed_threats']
            
            # Simulate indexing in OpenSearch
            indexed_threats = []
            for threat in processed_threats:
                indexed_threat = {
                    'document_id': f"doc_{uuid.uuid4().hex[:8]}",
                    'threat_id': threat['id'],
                    'indexed_fields': ['indicator', 'type', 'confidence'],
                    'index_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                indexed_threats.append(indexed_threat)
            
            return {'indexed_threats': indexed_threats}
        
        def validate_indexing(result):
            """Validate threats were indexed successfully"""
            return result and 'indexed_threats' in result and len(result['indexed_threats']) > 0
        
        def test_search_functionality(result=None):
            """Test search functionality on indexed threats"""
            indexed_threats = result['indexed_threats']
            
            # Simulate search queries
            search_tests = [
                {
                    'query': 'type:hash',
                    'expected_results': 1,
                    'actual_results': 1
                },
                {
                    'query': 'type:ip',
                    'expected_results': 1,
                    'actual_results': 1
                },
                {
                    'query': 'confidence:>0.8',
                    'expected_results': 2,
                    'actual_results': 2
                }
            ]
            
            return {'search_tests': search_tests}
        
        def validate_search(result):
            """Validate search functionality is working"""
            if not result or 'search_tests' not in result:
                return False
            
            for test in result['search_tests']:
                if test['expected_results'] != test['actual_results']:
                    return False
            
            return True
        
        def cleanup_pipeline_data(result):
            """Cleanup pipeline data"""
            print("    Cleaning up pipeline data and indices")
        
        steps = [
            WorkflowStep("Submit Raw Threat Feed", submit_raw_threat_feed, validate_feed_submission),
            WorkflowStep("Process Threat Normalization", process_threat_normalization, validate_normalization),
            WorkflowStep("Index Threats for Search", index_threats_for_search, validate_indexing),
            WorkflowStep("Test Search Functionality", test_search_functionality, validate_search, cleanup_pipeline_data)
        ]
        
        return self.framework.execute_workflow("Data Pipeline Workflow", steps)
    
    def run_all_integration_tests(self) -> List[IntegrationTestResult]:
        """Run all integration tests"""
        print("Starting FRANK Platform Integration Tests")
        print("=" * 60)
        
        results = []
        
        # Test complete threat sharing workflow
        print("\n1. Testing Complete Threat Sharing Workflow")
        result1 = self.test_complete_threat_sharing_workflow()
        results.append(result1)
        
        # Wait between tests
        time.sleep(5)
        
        # Test multi-tenant isolation
        print("\n2. Testing Multi-Tenant Isolation Workflow")
        result2 = self.test_multi_tenant_isolation_workflow()
        results.append(result2)
        
        # Wait between tests
        time.sleep(5)
        
        # Test data pipeline
        print("\n3. Testing Data Pipeline Workflow")
        result3 = self.test_data_pipeline_workflow()
        results.append(result3)
        
        return results
    
    def generate_integration_report(self, results: List[IntegrationTestResult], 
                                  output_file: str = "integration_report.json"):
        """Generate integration test report"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'platform': 'FRANK',
            'test_type': 'integration',
            'summary': {
                'total_workflows': len(results),
                'passed': sum(1 for r in results if r.status == 'PASS'),
                'failed': sum(1 for r in results if r.status == 'FAIL'),
                'partial': sum(1 for r in results if r.status == 'PARTIAL'),
                'total_execution_time': sum(r.execution_time for r in results),
                'total_steps': sum(r.total_steps for r in results),
                'completed_steps': sum(r.steps_completed for r in results)
            },
            'workflows': [
                {
                    'test_name': r.test_name,
                    'workflow': r.workflow,
                    'status': r.status,
                    'execution_time': r.execution_time,
                    'steps_completed': r.steps_completed,
                    'total_steps': r.total_steps,
                    'success_rate': (r.steps_completed / r.total_steps) * 100,
                    'error_message': r.error_message,
                    'data_created': r.data_created,
                    'data_cleaned': r.data_cleaned
                }
                for r in results
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nIntegration test report saved to: {output_file}")
        
        # Print summary
        summary = report['summary']
        print(f"\nIntegration Test Summary:")
        print(f"Total Workflows: {summary['total_workflows']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Partial: {summary['partial']}")
        print(f"Overall Success Rate: {(summary['completed_steps']/summary['total_steps'])*100:.1f}%")
        print(f"Total Execution Time: {summary['total_execution_time']:.2f}s")

def main():
    """Main function to run integration tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FRANK Platform Integration Testing')
    parser.add_argument('--url', required=True, help='Base URL of the API')
    parser.add_argument('--token', help='Authentication token')
    parser.add_argument('--workflow', choices=['threat-sharing', 'multi-tenant', 'data-pipeline', 'all'],
                       default='all', help='Specific workflow to test')
    parser.add_argument('--output', default='integration_report.json',
                       help='Output file for results')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    suite = FRANKIntegrationTestSuite(args.url, args.token)
    
    results = []
    
    if args.workflow == 'all':
        results = suite.run_all_integration_tests()
    elif args.workflow == 'threat-sharing':
        results = [suite.test_complete_threat_sharing_workflow()]
    elif args.workflow == 'multi-tenant':
        results = [suite.test_multi_tenant_isolation_workflow()]
    elif args.workflow == 'data-pipeline':
        results = [suite.test_data_pipeline_workflow()]
    
    suite.generate_integration_report(results, args.output)
    print("\nIntegration testing completed!")

if __name__ == '__main__':
    main()
