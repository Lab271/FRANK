#!/usr/bin/env python3
"""
Quick test to populate database with a few real submissions
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import sys
import os

# Add the current directory to path
sys.path.append(os.path.dirname(__file__))
from simple_mock_ingestion import generate_mock_submission

def main():
    API_URL = "http://localhost:4566/restapis/j92a900j2y/local/_user_request_"
    API_KEY = "blFJ7peuDskgtcQ4OC5nE3LAI9KxYrMGdNiwz8fX"
    
    print("🔄 Adding 10 sample submissions to database...")
    
    for i in range(10):
        submission = generate_mock_submission(i)
        
        # Submit to API
        data = json.dumps(submission).encode('utf-8')
        req = urllib.request.Request(f"{API_URL}/v1/submission")
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-Api-Key', API_KEY)
        
        try:
            with urllib.request.urlopen(req, data, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                print(f"✅ {i+1}/10: {result['submission_id']}")
        except Exception as e:
            print(f"❌ {i+1}/10: Failed - {e}")
    
    print("\n🎉 Done! Check the web interface at http://localhost:8001")

if __name__ == "__main__":
    main()
