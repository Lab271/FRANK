#!/usr/bin/env python3
"""
FRANK Mock Data Ingestion Script
Generates and submits 2000 mock threat intelligence submissions via API
"""

import json
import requests
import random
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid

class MockDataGenerator:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-Api-Key': self.api_key
        })
        
        # Mock data pools
        self.sectors = ['finance', 'healthcare', 'manufacturing', 'government', 'technology', 'energy', 'retail', 'education']
        self.access_levels = ['partner', 'premium', 'enterprise', 'community']
        self.observable_types = ['ipv4', 'domain', 'url', 'file_hash', 'email']
        self.roles = ['c2_server', 'phishing_domain', 'malicious_ip', 'botnet_member', 'drop_zone', 'exfiltration_point']
        
        # IP ranges for realistic IPs
        self.ip_ranges = [
            '192.168.{}.{}', '10.0.{}.{}', '172.16.{}.{}',  # Private ranges
            '185.220.{}.{}', '194.61.{}.{}', '103.224.{}.{}',  # Public ranges
            '45.142.{}.{}', '89.248.{}.{}', '162.244.{}.{}'
        ]
        
        # Domain patterns
        self.domain_patterns = [
            '{}.com', '{}.net', '{}.org', '{}.biz', 'www.{}.com',
            'mail.{}.com', 'secure.{}.net', 'login.{}.org'
        ]
        
        # Malicious keywords for realistic domains
        self.malicious_keywords = [
            'bank-update', 'security-alert', 'account-verify', 'login-secure',
            'paypal-confirm', 'amazon-security', 'microsoft-update', 'google-verify',
            'crypto-wallet', 'bitcoin-secure', 'eth-mining', 'defi-protocol'
        ]

    def generate_ip_address(self):
        """Generate a realistic IP address"""
        pattern = random.choice(self.ip_ranges)
        return pattern.format(random.randint(1, 254), random.randint(1, 254))

    def generate_domain(self):
        """Generate a realistic malicious domain"""
        keyword = random.choice(self.malicious_keywords)
        # Add some variation
        if random.random() < 0.3:
            keyword += str(random.randint(1, 99))
        if random.random() < 0.2:
            keyword = keyword.replace('-', '.')
        
        pattern = random.choice(self.domain_patterns)
        return pattern.format(keyword)

    def generate_file_hash(self):
        """Generate a realistic file hash"""
        hash_types = ['md5', 'sha1', 'sha256']
        hash_type = random.choice(hash_types)
        
        if hash_type == 'md5':
            return ''.join(random.choices('0123456789abcdef', k=32))
        elif hash_type == 'sha1':
            return ''.join(random.choices('0123456789abcdef', k=40))
        else:  # sha256
            return ''.join(random.choices('0123456789abcdef', k=64))

    def generate_email(self):
        """Generate a realistic malicious email"""
        usernames = ['admin', 'support', 'security', 'noreply', 'info', 'alert']
        username = random.choice(usernames)
        domain = self.generate_domain()
        return f"{username}@{domain}"

    def generate_url(self):
        """Generate a realistic malicious URL"""
        protocols = ['http', 'https']
        protocol = random.choice(protocols)
        domain = self.generate_domain()
        paths = ['/login', '/secure', '/update', '/verify', '/download', '/confirm']
        path = random.choice(paths)
        
        return f"{protocol}://{domain}{path}"

    def generate_observables(self):
        """Generate realistic observables for a sighting"""
        observables = {'network': [], 'file': [], 'email': []}
        
        # Add 1-3 network observables
        network_count = random.randint(1, 3)
        for _ in range(network_count):
            obs_type = random.choice(['ipv4', 'domain', 'url'])
            
            if obs_type == 'ipv4':
                value = self.generate_ip_address()
            elif obs_type == 'domain':
                value = self.generate_domain()
            else:  # url
                value = self.generate_url()
            
            observables['network'].append({
                'id': f"{obs_type}-{str(uuid.uuid4())}",
                'type': obs_type,
                'value': value,
                'role': random.choice(self.roles)
            })
        
        # Add file observables sometimes
        if random.random() < 0.4:
            observables['file'].append({
                'id': f"file-{str(uuid.uuid4())}",
                'type': 'file_hash',
                'value': self.generate_file_hash(),
                'role': 'malicious_file'
            })
        
        # Add email observables sometimes
        if random.random() < 0.3:
            observables['email'].append({
                'id': f"email-{str(uuid.uuid4())}",
                'type': 'email',
                'value': self.generate_email(),
                'role': 'phishing_sender'
            })
        
        # Clean up empty categories
        return {k: v for k, v in observables.items() if v}

    def generate_submission(self, index):
        """Generate a single mock submission"""
        # Random timestamp within last 30 days
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        
        timestamp = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
        
        # Generate organisation ID
        org_id = f"org-{random.randint(1000, 9999)}-{random.choice(['alpha', 'beta', 'gamma', 'delta'])}"
        
        submission = {
            "submission": {
                "submitter": {
                    "organisation_id": org_id,
                    "access_level": random.choice(self.access_levels),
                    "sector": random.choice(self.sectors)
                },
                "sighting": {
                    "sighting_id": f"sighting-{str(uuid.uuid4())}",
                    "timestamp": timestamp.isoformat() + "Z",
                    "confidence": random.randint(60, 98),  # Realistic confidence range
                    "observables": self.generate_observables()
                }
            }
        }
        
        return submission

    def submit_single(self, submission_data, index):
        """Submit a single submission to the API"""
        try:
            response = self.session.post(
                f"{self.base_url}/v1/submission",
                json=submission_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'index': index,
                    'success': True,
                    'submission_id': result.get('submission_id'),
                    'status_code': response.status_code
                }
            else:
                return {
                    'index': index,
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'response': response.text[:200]
                }
                
        except Exception as e:
            return {
                'index': index,
                'success': False,
                'error': str(e)
            }

    def ingest_mock_data(self, total_submissions=2000, batch_size=50, max_workers=10):
        """Ingest mock data with progress tracking"""
        print(f"🚀 Starting ingestion of {total_submissions} mock submissions...")
        print(f"📊 Batch size: {batch_size}, Workers: {max_workers}")
        print(f"🎯 Target API: {self.base_url}")
        print("-" * 60)
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        # Process in batches to avoid overwhelming the API
        for batch_start in range(0, total_submissions, batch_size):
            batch_end = min(batch_start + batch_size, total_submissions)
            batch_submissions = []
            
            # Generate batch of submissions
            for i in range(batch_start, batch_end):
                submission = self.generate_submission(i)
                batch_submissions.append((submission, i))
            
            # Submit batch with thread pool
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_index = {
                    executor.submit(self.submit_single, sub_data, index): index 
                    for sub_data, index in batch_submissions
                }
                
                for future in as_completed(future_to_index):
                    result = future.result()
                    if result['success']:
                        successful += 1
                        if successful % 100 == 0:
                            print(f"✅ {successful} submissions successful...")
                    else:
                        failed += 1
                        if failed <= 10:  # Only print first 10 errors
                            print(f"❌ Submission {result['index']} failed: {result.get('error', 'Unknown error')}")
            
            # Progress update
            completed = batch_end
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total_submissions - completed) / rate if rate > 0 else 0
            
            print(f"📈 Progress: {completed}/{total_submissions} ({completed/total_submissions*100:.1f}%) "
                  f"| Rate: {rate:.1f}/sec | ETA: {eta/60:.1f}min")
            
            # Small delay between batches
            time.sleep(0.5)
        
        # Final summary
        total_time = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"🎉 Ingestion Complete!")
        print(f"✅ Successful: {successful}/{total_submissions} ({successful/total_submissions*100:.1f}%)")
        print(f"❌ Failed: {failed}/{total_submissions} ({failed/total_submissions*100:.1f}%)")
        print(f"⏱️  Total time: {total_time/60:.1f} minutes")
        print(f"📊 Average rate: {total_submissions/total_time:.1f} submissions/second")
        
        return {
            'total': total_submissions,
            'successful': successful,
            'failed': failed,
            'duration': total_time
        }

def main():
    """Main function"""
    # Configuration
    BASE_URL = "http://localhost:4566/restapis/j92a900j2y/local/_user_request_"
    API_KEY = "blFJ7peuDskgtcQ4OC5nE3LAI9KxYrMGdNiwz8fX"
    
    # Create generator
    generator = MockDataGenerator(BASE_URL, API_KEY)
    
    # Test connection first
    print("🔍 Testing API connection...")
    try:
        test_response = generator.session.get(f"{BASE_URL}/v1/stats", timeout=10)
        if test_response.status_code == 200:
            print("✅ API connection successful!")
        else:
            print(f"⚠️  API returned status {test_response.status_code}")
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        print("Make sure LocalStack is running and the API is deployed!")
        return
    
    # Run ingestion
    try:
        result = generator.ingest_mock_data(
            total_submissions=2000,
            batch_size=25,  # Smaller batches for LocalStack
            max_workers=5   # Fewer workers for LocalStack
        )
        
        print(f"\n🎯 Check your database at: http://localhost:8001")
        print(f"📊 Query stats: {BASE_URL}/v1/stats")
        print(f"🔍 Query sightings: {BASE_URL}/v1/sighting?limit=20")
        
    except KeyboardInterrupt:
        print("\n⚠️  Ingestion interrupted by user")
    except Exception as e:
        print(f"\n❌ Ingestion failed: {e}")

if __name__ == "__main__":
    main()
