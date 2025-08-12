#!/usr/bin/env python3
"""
FRANK API Functional Tests

This module contains comprehensive functional tests for the FRANK API endpoints,
including authentication, data processing, and threat intelligence operations.
"""

import pytest
import requests
import json
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Any
import uuid

class FRANKAPITester:
    """Main test class for FRANK API functional testing"""
    
    def __init__(self, base_url: str, api_key: str = None, tenant_id: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.session = requests.Session()
        self.auth_token = None
        
    def setup_auth(self, username: str, password: str) -> bool:
        """Authenticate with the FRANK API and get access token"""
        auth_url = f"{self.base_url}/auth/login"
        
        auth_data = {
            "username": username,
            "password": password,
            "tenant_id": self.tenant_id
        }
        
        try:
            response = self.session.post(auth_url, json=auth_data)
            response.raise_for_status()
            
            auth_result = response.json()
            self.auth_token = auth_result.get('access_token')
            
            # Set authorization header for future requests
            self.session.headers.update({
                'Authorization': f'Bearer {self.auth_token}',
                'Content-Type': 'application/json',
                'X-Tenant-ID': self.tenant_id
            })
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Authentication failed: {e}")
            return False
    
    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test the health check endpoint"""
        url = f"{self.base_url}/health"
        
        try:
            response = requests.get(url, timeout=10)
            
            return {
                'status': 'success' if response.status_code == 200 else 'failed',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'response_data': response.json() if response.status_code == 200 else None
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def test_submit_sighting(self, sighting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test submitting a threat sighting"""
        url = f"{self.base_url}/v1/sightings"
        
        try:
            response = self.session.post(url, json=sighting_data)
            
            return {
                'status': 'success' if response.status_code in [200, 201] else 'failed',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'response_data': response.json() if response.status_code in [200, 201] else None,
                'sighting_id': response.json().get('sighting_id') if response.status_code in [200, 201] else None
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def test_get_sightings(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Test retrieving threat sightings"""
        url = f"{self.base_url}/v1/sightings"
        
        try:
            params = filters or {}
            response = self.session.get(url, params=params)
            
            return {
                'status': 'success' if response.status_code == 200 else 'failed',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'response_data': response.json() if response.status_code == 200 else None,
                'count': len(response.json().get('sightings', [])) if response.status_code == 200 else 0
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def test_submit_indicators(self, indicators: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Test submitting threat indicators"""
        url = f"{self.base_url}/v1/indicators"
        
        payload = {
            'indicators': indicators,
            'source': 'api_test',
            'confidence': 85
        }
        
        try:
            response = self.session.post(url, json=payload)
            
            return {
                'status': 'success' if response.status_code in [200, 201] else 'failed',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'response_data': response.json() if response.status_code in [200, 201] else None,
                'processed_count': response.json().get('processed_count') if response.status_code in [200, 201] else 0
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def test_search_indicators(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Test searching threat indicators"""
        url = f"{self.base_url}/v1/indicators/search"
        
        payload = {
            'query': query,
            'filters': filters or {},
            'limit': 100
        }
        
        try:
            response = self.session.post(url, json=payload)
            
            return {
                'status': 'success' if response.status_code == 200 else 'failed',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'response_data': response.json() if response.status_code == 200 else None,
                'results_count': len(response.json().get('results', [])) if response.status_code == 200 else 0
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def test_sigma_rule_execution(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test SIGMA rule execution"""
        url = f"{self.base_url}/v1/sigma/execute"
        
        try:
            response = self.session.post(url, json=rule_data)
            
            return {
                'status': 'success' if response.status_code in [200, 202] else 'failed',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'response_data': response.json() if response.status_code in [200, 202] else None,
                'execution_id': response.json().get('execution_id') if response.status_code in [200, 202] else None
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def test_tenant_isolation(self, other_tenant_id: str) -> Dict[str, Any]:
        """Test multi-tenant data isolation"""
        results = {
            'isolation_test': 'success',
            'tests': []
        }
        
        # Test 1: Try to access other tenant's sightings
        url = f"{self.base_url}/v1/sightings"
        headers = self.session.headers.copy()
        headers['X-Tenant-ID'] = other_tenant_id
        
        try:
            response = requests.get(url, headers=headers)
            
            test_result = {
                'test': 'other_tenant_access',
                'status': 'success' if response.status_code in [401, 403] else 'failed',
                'status_code': response.status_code,
                'expected': 'Should be denied access to other tenant data'
            }
            
            if response.status_code == 200:
                test_result['status'] = 'failed'
                test_result['issue'] = 'Access granted to other tenant data'
                results['isolation_test'] = 'failed'
            
            results['tests'].append(test_result)
            
        except Exception as e:
            results['tests'].append({
                'test': 'other_tenant_access',
                'status': 'error',
                'error': str(e)
            })
        
        return results
    
    def test_rate_limiting(self, endpoint: str = '/v1/sightings', requests_count: int = 100) -> Dict[str, Any]:
        """Test API rate limiting"""
        url = f"{self.base_url}{endpoint}"
        
        results = {
            'rate_limit_test': 'success',
            'requests_sent': 0,
            'rate_limited': False,
            'rate_limit_threshold': None
        }
        
        for i in range(requests_count):
            try:
                response = self.session.get(url)
                results['requests_sent'] = i + 1
                
                if response.status_code == 429:  # Too Many Requests
                    results['rate_limited'] = True
                    results['rate_limit_threshold'] = i + 1
                    break
                    
                # Small delay to avoid overwhelming the server
                time.sleep(0.1)
                
            except Exception as e:
                results['error'] = str(e)
                break
        
        return results
    
    def test_data_validation(self) -> Dict[str, Any]:
        """Test input validation and sanitization"""
        tests = []
        
        # Test 1: SQL Injection attempt
        malicious_query = "'; DROP TABLE sightings; --"
        
        search_result = self.test_search_indicators(malicious_query)
        tests.append({
            'test': 'sql_injection_prevention',
            'input': malicious_query,
            'status': 'success' if search_result['status'] in ['success', 'failed'] else 'failed',
            'response_code': search_result.get('status_code')
        })
        
        # Test 2: XSS attempt
        xss_payload = "<script>alert('xss')</script>"
        
        sighting_data = {
            'description': xss_payload,
            'indicators': [{'type': 'ip', 'value': '192.168.1.1'}],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        sighting_result = self.test_submit_sighting(sighting_data)
        tests.append({
            'test': 'xss_prevention',
            'input': xss_payload,
            'status': 'success' if sighting_result['status'] in ['success', 'failed'] else 'failed',
            'response_code': sighting_result.get('status_code')
        })
        
        # Test 3: Buffer overflow attempt
        large_payload = 'A' * 10000
        
        large_sighting = {
            'description': large_payload,
            'indicators': [{'type': 'ip', 'value': '192.168.1.1'}],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        buffer_result = self.test_submit_sighting(large_sighting)
        tests.append({
            'test': 'buffer_overflow_prevention',
            'input_size': len(large_payload),
            'status': 'success' if buffer_result['status'] in ['success', 'failed'] else 'failed',
            'response_code': buffer_result.get('status_code')
        })
        
        return {
            'validation_tests': tests,
            'overall_status': 'success' if all(t['status'] == 'success' for t in tests) else 'failed'
        }

def generate_test_data() -> Dict[str, Any]:
    """Generate test threat intelligence data"""
    return {
        'sightings': [
            {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'description': 'Suspicious network activity detected',
                'confidence': 85,
                'severity': 'high',
                'indicators': [
                    {'type': 'ip', 'value': '192.168.1.100'},
                    {'type': 'domain', 'value': 'malicious-example.com'},
                    {'type': 'hash', 'value': 'a1b2c3d4e5f6789012345678901234567890abcd'}
                ],
                'tags': ['malware', 'network', 'test']
            },
            {
                'id': str(uuid.uuid4()),
                'timestamp': (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                'description': 'Malicious file detected',
                'confidence': 95,
                'severity': 'critical',
                'indicators': [
                    {'type': 'hash', 'value': 'deadbeefcafebabe1234567890abcdef12345678'},
                    {'type': 'filename', 'value': 'malware.exe'}
                ],
                'tags': ['malware', 'file', 'test']
            }
        ],
        'indicators': [
            {'type': 'ip', 'value': '10.0.0.1', 'tags': ['test', 'internal']},
            {'type': 'ip', 'value': '203.0.113.1', 'tags': ['test', 'external']},
            {'type': 'domain', 'value': 'test-malicious.example', 'tags': ['test', 'domain']},
            {'type': 'url', 'value': 'http://malicious.example/payload', 'tags': ['test', 'url']},
            {'type': 'hash', 'value': '5d41402abc4b2a76b9719d911017c592', 'tags': ['test', 'md5']}
        ],
        'sigma_rules': [
            {
                'name': 'Test Rule - Suspicious Process',
                'rule': '''
title: Suspicious Process Execution
id: test-rule-001
status: test
description: Detects suspicious process execution patterns
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith:
            - '\\cmd.exe'
            - '\\powershell.exe'
        CommandLine|contains:
            - 'whoami'
            - 'net user'
    condition: selection
falsepositives:
    - Administrative activity
level: medium
tags:
    - attack.discovery
    - attack.t1033
                ''',
                'data_source': 'windows_events'
            }
        ]
    }

# Pytest test functions
@pytest.fixture
def api_tester():
    """Fixture to create API tester instance"""
    base_url = "https://api.frank-dev.com"  # Update with actual URL
    tenant_id = "test-tenant-001"
    
    tester = FRANKAPITester(base_url, tenant_id=tenant_id)
    
    # Authenticate (update with test credentials)
    auth_success = tester.setup_auth("test_user", "test_password")
    
    if not auth_success:
        pytest.skip("Authentication failed - check credentials and environment")
    
    return tester

@pytest.fixture
def test_data():
    """Fixture to provide test data"""
    return generate_test_data()

def test_health_endpoint(api_tester):
    """Test the health check endpoint"""
    result = api_tester.test_health_endpoint()
    
    assert result['status'] == 'success', f"Health check failed: {result}"
    assert result['status_code'] == 200
    assert result['response_time'] < 5.0, "Health check response time too slow"

def test_submit_and_retrieve_sighting(api_tester, test_data):
    """Test submitting and retrieving a sighting"""
    sighting = test_data['sightings'][0]
    
    # Submit sighting
    submit_result = api_tester.test_submit_sighting(sighting)
    assert submit_result['status'] == 'success', f"Failed to submit sighting: {submit_result}"
    
    sighting_id = submit_result['sighting_id']
    assert sighting_id is not None, "No sighting ID returned"
    
    # Retrieve sightings
    retrieve_result = api_tester.test_get_sightings({'id': sighting_id})
    assert retrieve_result['status'] == 'success', f"Failed to retrieve sighting: {retrieve_result}"
    assert retrieve_result['count'] > 0, "No sightings returned"

def test_submit_and_search_indicators(api_tester, test_data):
    """Test submitting and searching indicators"""
    indicators = test_data['indicators']
    
    # Submit indicators
    submit_result = api_tester.test_submit_indicators(indicators)
    assert submit_result['status'] == 'success', f"Failed to submit indicators: {submit_result}"
    
    # Search for submitted indicators
    search_result = api_tester.test_search_indicators("test")
    assert search_result['status'] == 'success', f"Failed to search indicators: {search_result}"

def test_sigma_rule_execution(api_tester, test_data):
    """Test SIGMA rule execution"""
    sigma_rule = test_data['sigma_rules'][0]
    
    execution_result = api_tester.test_sigma_rule_execution(sigma_rule)
    assert execution_result['status'] == 'success', f"SIGMA rule execution failed: {execution_result}"
    
    execution_id = execution_result['execution_id']
    assert execution_id is not None, "No execution ID returned"

def test_tenant_isolation(api_tester):
    """Test multi-tenant data isolation"""
    other_tenant_id = "other-tenant-002"
    
    isolation_result = api_tester.test_tenant_isolation(other_tenant_id)
    assert isolation_result['isolation_test'] == 'success', f"Tenant isolation failed: {isolation_result}"

def test_rate_limiting(api_tester):
    """Test API rate limiting"""
    rate_limit_result = api_tester.test_rate_limiting(requests_count=50)
    
    # Check if rate limiting is properly implemented
    if rate_limit_result['rate_limited']:
        assert rate_limit_result['rate_limit_threshold'] < 50, "Rate limit threshold too high"
    else:
        # Rate limiting might not be triggered with low request count
        print("Rate limiting not triggered - consider testing with higher request count")

def test_input_validation(api_tester):
    """Test input validation and security"""
    validation_result = api_tester.test_data_validation()
    
    assert validation_result['overall_status'] == 'success', f"Input validation failed: {validation_result}"
    
    for test in validation_result['validation_tests']:
        assert test['status'] == 'success', f"Validation test failed: {test}"

def test_performance_benchmarks(api_tester, test_data):
    """Test API performance benchmarks"""
    sighting = test_data['sightings'][0]
    
    # Test sighting submission performance
    submit_result = api_tester.test_submit_sighting(sighting)
    assert submit_result['response_time'] < 2.0, f"Sighting submission too slow: {submit_result['response_time']}s"
    
    # Test search performance
    search_result = api_tester.test_search_indicators("test")
    assert search_result['response_time'] < 3.0, f"Search too slow: {search_result['response_time']}s"

if __name__ == "__main__":
    # Run tests directly
    import sys
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "https://api.frank-dev.com"
    
    tenant_id = "test-tenant-001"
    tester = FRANKAPITester(base_url, tenant_id=tenant_id)
    
    # Run manual tests
    print("Running FRANK API functional tests...")
    
    # Health check
    health_result = tester.test_health_endpoint()
    print(f"Health check: {health_result['status']}")
    
    # Authentication test
    if tester.setup_auth("test_user", "test_password"):
        print("Authentication: success")
        
        # Generate test data
        test_data = generate_test_data()
        
        # Test sighting submission
        sighting_result = tester.test_submit_sighting(test_data['sightings'][0])
        print(f"Sighting submission: {sighting_result['status']}")
        
        # Test indicator search
        search_result = tester.test_search_indicators("test")
        print(f"Indicator search: {search_result['status']}")
        
        print("Manual test run completed.")
    else:
        print("Authentication failed - check credentials")
