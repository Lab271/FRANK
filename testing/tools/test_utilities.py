#!/usr/bin/env python3
"""
FRANK Platform - Testing Utilities and Helper Tools
Collection of utility functions and classes for testing automation.
"""

import os
import sys
import time
import json
import uuid
import hashlib
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import logging

class TestDataGenerator:
    """Generate realistic test data for FRANK platform testing"""
    
    def __init__(self, seed: int = None):
        if seed:
            random.seed(seed)
        self.threat_types = ['malware', 'phishing', 'c2', 'exploit', 'vulnerability']
        self.severity_levels = ['low', 'medium', 'high', 'critical']
        self.malware_families = ['trojan', 'ransomware', 'botnet', 'spyware', 'adware']
        self.domains = ['example.com', 'test.org', 'malicious.net', 'suspicious.info']
    
    def generate_threat_data(self, count: int = 1) -> List[Dict]:
        """Generate realistic threat intelligence data"""
        threats = []
        
        for _ in range(count):
            threat_type = random.choice(self.threat_types)
            
            if threat_type == 'malware':
                indicator = self.generate_hash()
                category = random.choice(self.malware_families)
            elif threat_type == 'phishing':
                indicator = self.generate_domain()
                category = 'phishing'
            elif threat_type == 'c2':
                indicator = self.generate_ip() if random.choice([True, False]) else self.generate_domain()
                category = 'command_control'
            else:
                indicator = self.generate_hash() if random.choice([True, False]) else self.generate_ip()
                category = threat_type
            
            threat = {
                'id': f"threat_{uuid.uuid4().hex[:8]}",
                'type': threat_type,
                'category': category,
                'indicator': indicator,
                'severity': random.choice(self.severity_levels),
                'confidence': round(random.uniform(0.1, 1.0), 2),
                'first_seen': self.generate_timestamp(),
                'last_seen': self.generate_timestamp(),
                'source': f"test_source_{random.randint(1, 10)}",
                'description': f"Test {threat_type} indicator for {category}",
                'tags': self.generate_tags(),
                'ttl': random.randint(3600, 86400),  # 1 hour to 1 day
                'metadata': {
                    'test_data': True,
                    'generated_at': datetime.utcnow().isoformat(),
                    'generator_version': '1.0'
                }
            }
            threats.append(threat)
        
        return threats
    
    def generate_user_data(self, count: int = 1) -> List[Dict]:
        """Generate test user data"""
        users = []
        
        for i in range(count):
            user = {
                'id': f"user_{uuid.uuid4().hex[:8]}",
                'username': f"test_user_{i+1}_{uuid.uuid4().hex[:6]}",
                'email': f"test.user.{i+1}@{random.choice(self.domains)}",
                'first_name': f"TestUser{i+1}",
                'last_name': f"LastName{i+1}",
                'role': random.choice(['admin', 'analyst', 'viewer', 'contributor']),
                'organization_id': f"org_{uuid.uuid4().hex[:8]}",
                'created_at': self.generate_timestamp(),
                'last_login': self.generate_timestamp(),
                'is_active': random.choice([True, True, True, False]),  # 75% active
                'preferences': {
                    'notifications': random.choice([True, False]),
                    'theme': random.choice(['light', 'dark']),
                    'language': random.choice(['en', 'es', 'fr', 'de'])
                },
                'metadata': {
                    'test_data': True,
                    'generated_at': datetime.utcnow().isoformat()
                }
            }
            users.append(user)
        
        return users
    
    def generate_organization_data(self, count: int = 1) -> List[Dict]:
        """Generate test organization data"""
        orgs = []
        org_types = ['government', 'enterprise', 'education', 'nonprofit', 'security_vendor']
        
        for i in range(count):
            org = {
                'id': f"org_{uuid.uuid4().hex[:8]}",
                'name': f"Test Organization {i+1}",
                'domain': f"testorg{i+1}.{random.choice(self.domains)}",
                'type': random.choice(org_types),
                'tier': random.choice(['free', 'standard', 'premium', 'enterprise']),
                'country': random.choice(['US', 'UK', 'DE', 'FR', 'CA', 'AU']),
                'industry': random.choice(['technology', 'finance', 'healthcare', 'government', 'education']),
                'created_at': self.generate_timestamp(),
                'is_active': True,
                'settings': {
                    'data_sharing': random.choice(['public', 'private', 'restricted']),
                    'retention_days': random.choice([30, 90, 180, 365]),
                    'auto_enrichment': random.choice([True, False])
                },
                'contact': {
                    'admin_email': f"admin@testorg{i+1}.{random.choice(self.domains)}",
                    'phone': f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
                },
                'metadata': {
                    'test_data': True,
                    'generated_at': datetime.utcnow().isoformat()
                }
            }
            orgs.append(org)
        
        return orgs
    
    def generate_hash(self, hash_type: str = 'sha256') -> str:
        """Generate realistic hash values"""
        if hash_type == 'md5':
            return hashlib.md5(f"test_{uuid.uuid4().hex}".encode()).hexdigest()
        elif hash_type == 'sha1':
            return hashlib.sha1(f"test_{uuid.uuid4().hex}".encode()).hexdigest()
        else:  # sha256
            return hashlib.sha256(f"test_{uuid.uuid4().hex}".encode()).hexdigest()
    
    def generate_ip(self, version: int = 4) -> str:
        """Generate IP addresses"""
        if version == 6:
            # IPv6
            return ':'.join([f"{random.randint(0, 65535):x}" for _ in range(8)])
        else:
            # IPv4 - avoid private ranges for realistic threats
            while True:
                ip = f"{random.randint(1, 223)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
                # Avoid private ranges
                if not (ip.startswith('10.') or ip.startswith('192.168.') or 
                       ip.startswith('172.16.') or ip.startswith('127.')):
                    return ip
    
    def generate_domain(self) -> str:
        """Generate domain names"""
        subdomains = ['www', 'mail', 'ftp', 'admin', 'secure', 'api', 'cdn']
        subdomain = random.choice(subdomains) if random.choice([True, False]) else None
        
        domain_name = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 12)))
        tld = random.choice(['.com', '.org', '.net', '.info', '.biz', '.co'])
        
        if subdomain:
            return f"{subdomain}.{domain_name}{tld}"
        else:
            return f"{domain_name}{tld}"
    
    def generate_timestamp(self, days_back: int = 30) -> str:
        """Generate timestamps within the last N days"""
        now = datetime.utcnow()
        random_days = random.randint(0, days_back)
        random_hours = random.randint(0, 23)
        random_minutes = random.randint(0, 59)
        
        timestamp = now - timedelta(days=random_days, hours=random_hours, minutes=random_minutes)
        return timestamp.isoformat() + 'Z'
    
    def generate_tags(self, count: int = None) -> List[str]:
        """Generate realistic tags"""
        available_tags = [
            'malware', 'phishing', 'apt', 'ransomware', 'trojan', 'botnet',
            'c2', 'exploit', 'vulnerability', 'suspicious', 'confirmed',
            'high-confidence', 'medium-confidence', 'low-confidence',
            'automated', 'manual', 'verified', 'sandbox', 'honeypot'
        ]
        
        if count is None:
            count = random.randint(1, 5)
        
        return random.sample(available_tags, min(count, len(available_tags)))

class TestResultCollector:
    """Collect and aggregate test results from multiple test runs"""
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        self.results = []
        self.start_time = time.time()
        self.metadata = {
            'session_id': self.session_id,
            'start_time': datetime.utcnow().isoformat(),
            'framework_version': '1.0',
            'python_version': sys.version
        }
    
    def add_result(self, test_name: str, category: str, status: str, 
                   execution_time: float = 0, details: Dict = None):
        """Add a test result"""
        result = {
            'test_name': test_name,
            'category': category,
            'status': status,
            'execution_time': execution_time,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        self.results.append(result)
    
    def get_summary(self) -> Dict:
        """Get summary statistics"""
        total_tests = len(self.results)
        if total_tests == 0:
            return {'total': 0, 'passed': 0, 'failed': 0, 'warnings': 0}
        
        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        failed = sum(1 for r in self.results if r['status'] == 'FAIL')
        warnings = sum(1 for r in self.results if r['status'] == 'WARNING')
        
        total_time = sum(r['execution_time'] for r in self.results)
        
        return {
            'total': total_tests,
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'pass_rate': (passed / total_tests) * 100,
            'total_execution_time': total_time,
            'session_duration': time.time() - self.start_time
        }
    
    def get_results_by_category(self) -> Dict:
        """Group results by category"""
        categories = {}
        for result in self.results:
            cat = result['category']
            if cat not in categories:
                categories[cat] = {'total': 0, 'passed': 0, 'failed': 0, 'warnings': 0}
            
            categories[cat]['total'] += 1
            if result['status'] == 'PASS':
                categories[cat]['passed'] += 1
            elif result['status'] == 'FAIL':
                categories[cat]['failed'] += 1
            elif result['status'] == 'WARNING':
                categories[cat]['warnings'] += 1
        
        return categories
    
    def export_results(self, filename: str = None) -> str:
        """Export results to JSON file"""
        if filename is None:
            filename = f"test_results_{self.session_id}.json"
        
        export_data = {
            'metadata': self.metadata,
            'summary': self.get_summary(),
            'results_by_category': self.get_results_by_category(),
            'detailed_results': self.results
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return filename

class TestEnvironmentManager:
    """Manage test environment setup and cleanup"""
    
    def __init__(self, base_url: str, environment: str = 'test'):
        self.base_url = base_url
        self.environment = environment
        self.created_resources = []
        self.temp_files = []
        self.logger = logging.getLogger(__name__)
    
    def setup_test_data(self, data_types: List[str] = None) -> Dict:
        """Setup test data for testing"""
        data_types = data_types or ['threats', 'users', 'organizations']
        generator = TestDataGenerator()
        test_data = {}
        
        for data_type in data_types:
            if data_type == 'threats':
                test_data['threats'] = generator.generate_threat_data(10)
            elif data_type == 'users':
                test_data['users'] = generator.generate_user_data(5)
            elif data_type == 'organizations':
                test_data['organizations'] = generator.generate_organization_data(3)
        
        # Save test data to file
        filename = f"test_data_{uuid.uuid4().hex[:8]}.json"
        with open(filename, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        self.temp_files.append(filename)
        self.logger.info(f"Test data generated and saved to {filename}")
        
        return test_data
    
    def create_test_user(self, role: str = 'analyst') -> Dict:
        """Create a test user"""
        generator = TestDataGenerator()
        user_data = generator.generate_user_data(1)[0]
        user_data['role'] = role
        
        # In real implementation, this would make API call to create user
        user_id = user_data['id']
        self.created_resources.append(('user', user_id))
        
        self.logger.info(f"Created test user: {user_id}")
        return user_data
    
    def create_test_organization(self) -> Dict:
        """Create a test organization"""
        generator = TestDataGenerator()
        org_data = generator.generate_organization_data(1)[0]
        
        # In real implementation, this would make API call to create organization
        org_id = org_data['id']
        self.created_resources.append(('organization', org_id))
        
        self.logger.info(f"Created test organization: {org_id}")
        return org_data
    
    def cleanup(self):
        """Clean up created resources and temporary files"""
        self.logger.info("Starting test environment cleanup...")
        
        # Clean up created resources
        for resource_type, resource_id in self.created_resources:
            try:
                # In real implementation, make API calls to delete resources
                self.logger.info(f"Cleaned up {resource_type}: {resource_id}")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {resource_type} {resource_id}: {e}")
        
        # Clean up temporary files
        for filename in self.temp_files:
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                    self.logger.info(f"Removed temporary file: {filename}")
            except Exception as e:
                self.logger.warning(f"Failed to remove file {filename}: {e}")
        
        self.logger.info("Test environment cleanup completed")

class SecurityTestHelper:
    """Helper functions for security testing"""
    
    @staticmethod
    def generate_malicious_payloads() -> Dict[str, List[str]]:
        """Generate common malicious payloads for testing"""
        return {
            'sql_injection': [
                "'; DROP TABLE users; --",
                "' OR '1'='1",
                "1; SELECT * FROM information_schema.tables; --",
                "' UNION SELECT username, password FROM users; --"
            ],
            'xss': [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
                "javascript:alert('XSS')",
                "<svg onload=alert('XSS')>"
            ],
            'command_injection': [
                "; cat /etc/passwd",
                "&& whoami",
                "| nc -l 4444",
                "`id`"
            ],
            'path_traversal': [
                "../../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
                "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
                "....//....//....//etc/passwd"
            ],
            'ldap_injection': [
                "*)(&",
                "*)(uid=*",
                "*)(|(mail=*))",
                "*))(|(cn=*"
            ],
            'template_injection': [
                "{{7*7}}",
                "${7*7}",
                "#{7*7}",
                "<%=7*7%>"
            ]
        }
    
    @staticmethod
    def validate_security_headers(headers: Dict[str, str]) -> Dict[str, bool]:
        """Validate security headers in HTTP response"""
        required_headers = {
            'X-Content-Type-Options': lambda v: v.lower() == 'nosniff',
            'X-Frame-Options': lambda v: v.upper() in ['DENY', 'SAMEORIGIN'],
            'X-XSS-Protection': lambda v: '1' in v,
            'Strict-Transport-Security': lambda v: 'max-age=' in v,
            'Content-Security-Policy': lambda v: len(v) > 0,
            'Referrer-Policy': lambda v: v in ['no-referrer', 'strict-origin-when-cross-origin'],
            'Permissions-Policy': lambda v: len(v) > 0
        }
        
        results = {}
        for header, validator in required_headers.items():
            if header in headers:
                results[header] = validator(headers[header])
            else:
                results[header] = False
        
        return results
    
    @staticmethod
    def generate_weak_passwords() -> List[str]:
        """Generate list of weak passwords for testing"""
        return [
            'password',
            '123456',
            'admin',
            'qwerty',
            'test',
            'guest',
            'root',
            'password123',
            '1234567890',
            'abc123'
        ]
    
    @staticmethod
    def check_password_strength(password: str) -> Dict[str, bool]:
        """Check password strength"""
        checks = {
            'min_length': len(password) >= 8,
            'has_uppercase': any(c.isupper() for c in password),
            'has_lowercase': any(c.islower() for c in password),
            'has_digit': any(c.isdigit() for c in password),
            'has_special': any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password),
            'not_common': password.lower() not in [
                'password', '123456', 'qwerty', 'admin', 'test'
            ]
        }
        
        checks['overall_strong'] = all(checks.values())
        return checks

class PerformanceTestHelper:
    """Helper functions for performance testing"""
    
    @staticmethod
    def calculate_percentiles(values: List[float], percentiles: List[int] = None) -> Dict[int, float]:
        """Calculate percentiles from a list of values"""
        if not values:
            return {}
        
        percentiles = percentiles or [50, 75, 90, 95, 99]
        sorted_values = sorted(values)
        results = {}
        
        for p in percentiles:
            index = int((p / 100) * len(sorted_values))
            if index >= len(sorted_values):
                index = len(sorted_values) - 1
            results[p] = sorted_values[index]
        
        return results
    
    @staticmethod
    def analyze_response_times(response_times: List[float]) -> Dict[str, float]:
        """Analyze response time statistics"""
        if not response_times:
            return {}
        
        return {
            'count': len(response_times),
            'min': min(response_times),
            'max': max(response_times),
            'average': sum(response_times) / len(response_times),
            'median': sorted(response_times)[len(response_times) // 2],
            'p95': PerformanceTestHelper.calculate_percentiles(response_times, [95])[95],
            'p99': PerformanceTestHelper.calculate_percentiles(response_times, [99])[99]
        }

def setup_logging(level: str = 'INFO', log_file: str = None) -> logging.Logger:
    """Setup logging configuration"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger('frank_testing')
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def load_test_config(config_file: str = 'test_config.json') -> Dict:
    """Load test configuration from file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'default_timeout': 30,
            'max_retries': 3,
            'parallel_workers': 4,
            'report_format': 'json'
        }

def create_test_session() -> str:
    """Create a unique test session ID"""
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    random_suffix = uuid.uuid4().hex[:6]
    return f"frank_test_{timestamp}_{random_suffix}"

if __name__ == '__main__':
    # Example usage
    print("FRANK Testing Utilities - Example Usage")
    
    # Generate test data
    generator = TestDataGenerator(seed=12345)
    threats = generator.generate_threat_data(3)
    users = generator.generate_user_data(2)
    
    print(f"\nGenerated {len(threats)} threat indicators:")
    for threat in threats:
        print(f"  - {threat['type']}: {threat['indicator']} ({threat['severity']})")
    
    print(f"\nGenerated {len(users)} test users:")
    for user in users:
        print(f"  - {user['username']} ({user['role']})")
    
    # Test result collection
    collector = TestResultCollector()
    collector.add_result('API Test 1', 'Functional', 'PASS', 0.5)
    collector.add_result('Security Test 1', 'Security', 'FAIL', 1.2)
    
    summary = collector.get_summary()
    print(f"\nTest Summary: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']:.1f}%)")
