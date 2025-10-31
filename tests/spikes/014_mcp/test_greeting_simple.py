#!/usr/bin/env python3
"""
Simple Test Script for Greeting MCP Server
Copyright (c) 2025 LAB271
"""

import requests
import json
import sys

# Disable SSL warnings
try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

def test_greeting_server(base_url="https://mcp.local"):
    """Simple test function for greeting server"""
    greeting_url = f"{base_url}/greeting"
    
    print("🧪 Testing Greeting MCP Server")
    print(f"Base URL: {base_url}")
    print(f"Greeting Service: {greeting_url}")
    print()
    
    # Test 1: Gateway root
    print("1. Testing Gateway Root...")
    try:
        response = requests.get(f"{base_url}/", verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            services = data.get("services", [])
            print(f"   ✅ Gateway OK - Found {len(services)} services")
            for service in services:
                print(f"      - {service}")
        else:
            print(f"   ❌ Gateway failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Gateway error: {e}")
    
    # Test 2: Gateway health
    print("\n2. Testing Gateway Health...")
    try:
        response = requests.get(f"{base_url}/health", verify=False, timeout=10)
        if response.status_code == 200:
            print("   ✅ Gateway health OK")
        else:
            print(f"   ❌ Gateway health failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Gateway health error: {e}")
    
    # Test 3: Greeting service health
    print("\n3. Testing Greeting Service Health...")
    try:
        response = requests.get(f"{greeting_url}/health", verify=False, timeout=10)
        if response.status_code == 200:
            try:
                data = response.json()
                service = data.get("service", "unknown")
                status = data.get("status", "unknown")
                print(f"   ✅ Greeting service OK - Service: {service}, Status: {status}")
            except Exception:
                print("   ✅ Greeting service OK (non-JSON response)")
        else:
            print(f"   ❌ Greeting service failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Greeting service error: {e}")
    
    # Test 4: 404 handling
    print("\n4. Testing 404 Handling...")
    try:
        response = requests.get(f"{greeting_url}/nonexistent", verify=False, timeout=10)
        if response.status_code == 404:
            print("   ✅ 404 handling OK")
        else:
            print(f"   ⚠️  Unexpected status for 404 test: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 404 test error: {e}")
    
    print("\n🏁 Test Complete!")
    print("\nManual test commands:")
    print(f"  curl -sk {base_url}/")
    print(f"  curl -sk {greeting_url}/health")
    print("  make logs-greeting-mcp")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://mcp.local"
    test_greeting_server(url)