#!/usr/bin/env python3
"""
Simple Mock Data Ingestion Script for FRANK API
Generates and submits mock threat intelligence via API calls only
"""

import json
import time
import random
import uuid
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import urllib.error

def generate_mock_submission(index):
    """Generate a single mock submission"""
    sectors = ['finance', 'healthcare', 'manufacturing', 'government', 'technology', 'energy']
    tiers = ['partner', 'premium', 'enterprise', 'community']
    
    # Random timestamp within last 30 days
    days_ago = random.randint(0, 30)
    hours_ago = random.randint(0, 23)
    timestamp = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
    
    # Generate realistic IP
    ip_parts = [random.randint(1, 254) for _ in range(4)]
    ip_address = '.'.join(map(str, ip_parts))
    
    # Generate domain
    malicious_words = ['bank-update', 'security-alert', 'paypal-verify', 'microsoft-login']
    domain = f"{random.choice(malicious_words)}{random.randint(1, 99)}.com"
    
    submission = {
        "submission": {
            "submitter": {
                "organization_id": f"org-{random.randint(1000, 9999)}-test",
                "access_level": random.choice(tiers),
                "sector": random.choice(sectors)
            },
            "sighting": {
                "sighting_id": f"sighting-{str(uuid.uuid4())}",
                "timestamp": timestamp.isoformat() + "Z",
                "confidence": random.randint(70, 98),
                "observables": {
                    "network": [
                        {
                            "id": f"ip-{str(uuid.uuid4())}",
                            "type": "ipv4",
                            "value": ip_address,
                            "role": "malicious_ip"
                        },
                        {
                            "id": f"domain-{str(uuid.uuid4())}",
                            "type": "domain", 
                            "value": domain,
                            "role": "phishing_domain"
                        }
                    ]
                }
            }
        }
    }
    
    return submission

def submit_to_api(submission_data, api_url, api_key):
    """Submit data to FRANK API using urllib"""
    try:
        # Prepare request
        data = json.dumps(submission_data).encode('utf-8')
        
        req = urllib.request.Request(
            f"{api_url}/v1/submission",
            data=data,
            headers={
                'Content-Type': 'application/json',
                'X-Api-Key': api_key
            }
        )
        
        # Make request
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {
                'success': True,
                'submission_id': result.get('submission_id', 'unknown'),
                'status_code': response.status
            }
            
    except urllib.error.HTTPError as e:
        return {
            'success': False,
            'error': f"HTTP {e.code}: {e.reason}",
            'response': e.read().decode('utf-8')[:200]
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def main():
    """Main execution"""
    # Configuration
    API_URL = "http://localhost:4566/restapis/j92a900j2y/local/_user_request_"
    API_KEY = "blFJ7peuDskgtcQ4OC5nE3LAI9KxYrMGdNiwz8fX"
    TOTAL_SUBMISSIONS = 2000
    
    print("🚀 FRANK Mock Data Ingestion")
    print("=" * 50)
    print(f"Target: {API_URL}")
    print(f"Total submissions: {TOTAL_SUBMISSIONS}")
    print("-" * 50)
    
    # Test API connection
    print("🔍 Testing API connection...")
    try:
        # Test with submission endpoint instead of stats
        test_data = json.dumps({"test": "connection"}).encode('utf-8')
        test_req = urllib.request.Request(f"{API_URL}/v1/submission", data=test_data)
        test_req.add_header('X-Api-Key', API_KEY)
        test_req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(test_req, timeout=5) as response:
            if response.status == 200:
                print("✅ API connection successful!")
            else:
                print(f"⚠️  API returned status {response.status}")
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        print("Make sure LocalStack is running!")
        return
    
    # Start ingestion
    start_time = time.time()
    successful = 0
    failed = 0
    
    print(f"\n🏁 Starting ingestion of {TOTAL_SUBMISSIONS} submissions...")
    
    for i in range(TOTAL_SUBMISSIONS):
        # Generate submission
        submission = generate_mock_submission(i)
        
        # Submit to API
        result = submit_to_api(submission, API_URL, API_KEY)
        
        if result['success']:
            successful += 1
            if successful % 100 == 0:
                elapsed = time.time() - start_time
                rate = successful / elapsed
                eta = (TOTAL_SUBMISSIONS - i) / rate
                print(f"✅ {successful} successful | Rate: {rate:.1f}/sec | ETA: {eta/60:.1f}min")
        else:
            failed += 1
            if failed <= 5:  # Only show first 5 errors
                print(f"❌ Submission {i} failed: {result.get('error', 'Unknown')}")
        
        # Small delay to avoid overwhelming LocalStack
        if i % 50 == 0:
            time.sleep(0.1)
    
    # Final summary
    total_time = time.time() - start_time
    print(f"\n🎉 Ingestion Complete!")
    print(f"✅ Successful: {successful}/{TOTAL_SUBMISSIONS} ({successful/TOTAL_SUBMISSIONS*100:.1f}%)")
    print(f"❌ Failed: {failed}/{TOTAL_SUBMISSIONS} ({failed/TOTAL_SUBMISSIONS*100:.1f}%)")
    print(f"⏱️  Total time: {total_time/60:.1f} minutes")
    print(f"📊 Average rate: {TOTAL_SUBMISSIONS/total_time:.1f} submissions/second")
    
    print(f"\n🔗 Check results:")
    print(f"   Database: http://localhost:8001")
    print(f"   API: {API_URL}/v1/submission")

if __name__ == "__main__":
    main()
