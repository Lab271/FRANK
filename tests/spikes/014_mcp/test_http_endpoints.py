#!/usr/bin/env python3
"""
HTTP Endpoint Test for Greeting MCP Server
Tests all HTTP endpoints including REST API and JSON-RPC
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

def test_http_endpoints(base_url="https://mcp.local"):
    """Test all HTTP endpoints of the greeting server"""
    greeting_url = f"{base_url}/greeting"
    
    print("🧪 Testing Greeting MCP Server HTTP Endpoints")
    print(f"Base URL: {base_url}")
    print(f"Greeting Service: {greeting_url}")
    print()
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Root endpoint
    print("1. Testing Root Endpoint...")
    tests_total += 1
    try:
        response = requests.get(f"{greeting_url}/", verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Root OK - Service: {data.get('service')}")
            print(f"      Available endpoints: {list(data.get('endpoints', {}).keys())}")
            tests_passed += 1
        else:
            print(f"   ❌ Root failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Root error: {e}")
    
    # Test 2: Health endpoint
    print("\n2. Testing Health Endpoint...")
    tests_total += 1
    try:
        response = requests.get(f"{greeting_url}/health", verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health OK - Status: {data.get('status')}")
            tests_passed += 1
        else:
            print(f"   ❌ Health failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Health error: {e}")
    
    # Test 3: Greet REST endpoint
    print("\n3. Testing Greet REST Endpoint...")
    tests_total += 1
    try:
        response = requests.get(f"{greeting_url}/greet/Alice", verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            greeting_text = data.get('greeting', '')
            print(f"   ✅ Greet REST OK - Greeting: {greeting_text[:50]}...")
            tests_passed += 1
        else:
            print(f"   ❌ Greet REST failed - Status: {response.status_code}")
            print(f"      Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Greet REST error: {e}")
    
    # Test 4: Farewell REST endpoint
    print("\n4. Testing Farewell REST Endpoint...")
    tests_total += 1
    try:
        response = requests.get(f"{greeting_url}/farewell/Bob", verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            farewell_text = data.get('farewell', '')
            print(f"   ✅ Farewell REST OK - Farewell: {farewell_text[:50]}...")
            tests_passed += 1
        else:
            print(f"   ❌ Farewell REST failed - Status: {response.status_code}")
            print(f"      Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Farewell REST error: {e}")
    
    # Test 5: Invalid name handling
    print("\n5. Testing Invalid Name Handling...")
    tests_total += 1
    try:
        response = requests.get(f"{greeting_url}/greet/123", verify=False, timeout=10)
        if response.status_code == 400:
            print("   ✅ Invalid name properly rejected")
            tests_passed += 1
        else:
            print(f"   ❌ Invalid name not properly rejected - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Invalid name test error: {e}")
    
    # Test 6: JSON-RPC Initialize
    print("\n6. Testing JSON-RPC Initialize...")
    tests_total += 1
    try:
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        response = requests.post(f"{greeting_url}/mcp", json=init_request, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            server_info = data.get('result', {}).get('serverInfo', {})
            print(f"   ✅ JSON-RPC Initialize OK - Server: {server_info.get('name')}")
            tests_passed += 1
        else:
            print(f"   ❌ JSON-RPC Initialize failed - Status: {response.status_code}")
            print(f"      Response: {response.text}")
    except Exception as e:
        print(f"   ❌ JSON-RPC Initialize error: {e}")
    
    # Test 7: JSON-RPC Tools List
    print("\n7. Testing JSON-RPC Tools List...")
    tests_total += 1
    try:
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        response = requests.post(f"{greeting_url}/mcp", json=tools_request, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            tools = data.get('result', {}).get('tools', [])
            tool_names = [tool.get('name') for tool in tools]
            print(f"   ✅ JSON-RPC Tools List OK - Tools: {tool_names}")
            tests_passed += 1
        else:
            print(f"   ❌ JSON-RPC Tools List failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ JSON-RPC Tools List error: {e}")
    
    # Test 8: JSON-RPC Tool Call (Greet)
    print("\n8. Testing JSON-RPC Tool Call (Greet)...")
    tests_total += 1
    try:
        greet_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "greet",
                "arguments": {"name": "Charlie"}
            }
        }
        response = requests.post(f"{greeting_url}/mcp", json=greet_request, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            content = data.get('result', {}).get('content', [])
            if content and content[0].get('text'):
                greeting_text = content[0]['text']
                print(f"   ✅ JSON-RPC Greet OK - Text: {greeting_text[:50]}...")
                tests_passed += 1
            else:
                print("   ❌ JSON-RPC Greet failed - No content returned")
        else:
            print(f"   ❌ JSON-RPC Greet failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ JSON-RPC Greet error: {e}")
    
    # Test 9: JSON-RPC Tool Call (Farewell)
    print("\n9. Testing JSON-RPC Tool Call (Farewell)...")
    tests_total += 1
    try:
        farewell_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "farewell",
                "arguments": {"name": "Diana"}
            }
        }
        response = requests.post(f"{greeting_url}/mcp", json=farewell_request, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            content = data.get('result', {}).get('content', [])
            if content and content[0].get('text'):
                farewell_text = content[0]['text']
                print(f"   ✅ JSON-RPC Farewell OK - Text: {farewell_text[:50]}...")
                tests_passed += 1
            else:
                print("   ❌ JSON-RPC Farewell failed - No content returned")
        else:
            print(f"   ❌ JSON-RPC Farewell failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ JSON-RPC Farewell error: {e}")
    
    # Test 10: 404 handling
    print("\n10. Testing 404 Handling...")
    tests_total += 1
    try:
        response = requests.get(f"{greeting_url}/nonexistent", verify=False, timeout=10)
        if response.status_code == 404:
            print("   ✅ 404 handling OK")
            tests_passed += 1
        else:
            print(f"   ❌ 404 handling failed - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 404 test error: {e}")
    
    print(f"\n🏁 Test Complete! Passed: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the logs for details.")
    
    print("\n📋 Available Endpoints:")
    print(f"  Root:           {greeting_url}/")
    print(f"  Health:         {greeting_url}/health")
    print(f"  Greet REST:     {greeting_url}/greet/{{name}}")
    print(f"  Farewell REST:  {greeting_url}/farewell/{{name}}")
    print(f"  JSON-RPC MCP:   {greeting_url}/mcp")
    print(f"  JSON-RPC Alt:   {greeting_url}/jsonrpc")
    
    print("\n🔧 Manual Test Commands:")
    print(f"  curl -sk {greeting_url}/")
    print(f"  curl -sk {greeting_url}/health")
    print(f"  curl -sk {greeting_url}/greet/Alice")
    print(f"  curl -sk {greeting_url}/farewell/Bob")
    
    return tests_passed == tests_total

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://mcp.local"
    success = test_http_endpoints(url)
    sys.exit(0 if success else 1)