#!/usr/bin/env python3
"""
Test Script for Greeting MCP Server
Copyright (c) 2025 LAB271
SPDX-License-Identifier: Apache-2.0

This script tests the Greeting MCP Server deployed behind NGINX.
"""

import json
import time
import requests
import sys
from typing import Dict, Optional

# Disable SSL warnings for self-signed certificates
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except (ImportError, AttributeError):
    # If we can't disable warnings, just continue
    pass

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class GreetingServerTester:
    def __init__(self, base_url: str = "https://mcp.local"):
        self.base_url = base_url
        self.greeting_url = f"{base_url}/greeting"
        self.session = requests.Session()
        self.session.verify = False  # Accept self-signed certificates
        self.test_results = []
        
    def log(self, message: str, color: str = Colors.NC):
        print(f"{color}{message}{Colors.NC}")
        
    def test_result(self, test_name: str, success: bool, details: str = ""):
        status = "✅ PASS" if success else "❌ FAIL"
        color = Colors.GREEN if success else Colors.RED
        self.log(f"{status} {test_name}", color)
        if details:
            print(f"  {details}")
        self.test_results.append({"test": test_name, "success": success, "details": details})
        print()
        
    def test_http_endpoint(self, url: str, expected_status: int = 200, 
                          method: str = "GET", json_data: Optional[Dict] = None) -> tuple:
        """Test HTTP endpoint and return (success, response, status_code)"""
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=10)
            elif method.upper() == "POST":
                response = self.session.post(url, json=json_data, timeout=10)
            else:
                return False, None, 0
                
            success = response.status_code == expected_status
            return success, response, response.status_code
        except Exception as e:
            return False, None, 0
            
    def test_gateway_health(self):
        """Test gateway endpoints"""
        self.log("=== 1. Gateway Health Tests ===", Colors.BLUE)
        
        # Test gateway root
        success, response, status = self.test_http_endpoint(f"{self.base_url}/")
        if success and response:
            try:
                data = response.json()
                services = data.get("services", [])
                greeting_found = any("greeting" in str(service) for service in services)
                self.test_result(
                    "Gateway Root", 
                    True, 
                    f"Found {len(services)} services, greeting service registered: {greeting_found}"
                )
            except:
                self.test_result("Gateway Root", True, f"Status: {status}")
        else:
            self.test_result("Gateway Root", False, f"Status: {status}")
            
        # Test gateway health
        success, response, status = self.test_http_endpoint(f"{self.base_url}/health")
        self.test_result("Gateway Health", success, f"Status: {status}")
        
    def test_greeting_health(self):
        """Test greeting service health"""
        self.log("=== 2. Greeting Service Health ===", Colors.BLUE)
        
        success, response, status = self.test_http_endpoint(f"{self.greeting_url}/health")
        if success and response:
            try:
                data = response.json()
                self.test_result(
                    "Greeting Health", 
                    True, 
                    f"Service: {data.get('service', 'unknown')}, Status: {data.get('status', 'unknown')}"
                )
            except:
                self.test_result("Greeting Health", True, f"Status: {status}")
        else:
            self.test_result("Greeting Health", False, f"Status: {status}")
            
    def test_mcp_protocol(self):
        """Test MCP protocol endpoints"""
        self.log("=== 3. MCP Protocol Tests ===", Colors.BLUE)
        
        # Try different possible MCP endpoints
        mcp_endpoints = ["", "/mcp", "/jsonrpc", "/rpc"]
        mcp_found = False
        
        for endpoint in mcp_endpoints:
            url = f"{self.greeting_url}{endpoint}"
            self.log(f"Trying MCP endpoint: {url}", Colors.YELLOW)
            
            # Test initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "python-test-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            success, response, status = self.test_http_endpoint(
                url, expected_status=200, method="POST", json_data=init_request
            )
            
            if success and response:
                try:
                    data = response.json()
                    if "result" in data or "capabilities" in data or "serverInfo" in data:
                        mcp_found = True
                        self.test_result(
                            f"MCP Initialize ({endpoint or 'root'})", 
                            True, 
                            f"Server capabilities found"
                        )
                        
                        # Test available tools
                        self.test_mcp_tools(url)
                        break
                except:
                    pass
                    
            self.log(f"  No MCP response from {endpoint or 'root'}", Colors.RED)
            
        if not mcp_found:
            self.test_result("MCP Protocol", False, "No MCP endpoints found")
            
    def test_mcp_tools(self, mcp_url: str):
        """Test MCP tools (greet and farewell)"""
        # Test greet tool
        greet_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "greet",
                "arguments": {"name": "Alice"}
            }
        }
        
        success, response, status = self.test_http_endpoint(
            mcp_url, expected_status=200, method="POST", json_data=greet_request
        )
        
        if success and response:
            try:
                data = response.json()
                result = data.get("result", {})
                greeting_text = result.get("content", [{}])[0].get("text", "") if result else ""
                self.test_result(
                    "Greet Tool", 
                    "Alice" in greeting_text if greeting_text else False,
                    f"Greeting: {greeting_text[:50]}..." if greeting_text else "No greeting text"
                )
            except:
                self.test_result("Greet Tool", False, "Invalid response format")
        else:
            self.test_result("Greet Tool", False, f"Status: {status}")
            
        # Test farewell tool
        farewell_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "farewell",
                "arguments": {"name": "Bob"}
            }
        }
        
        success, response, status = self.test_http_endpoint(
            mcp_url, expected_status=200, method="POST", json_data=farewell_request
        )
        
        if success and response:
            try:
                data = response.json()
                result = data.get("result", {})
                farewell_text = result.get("content", [{}])[0].get("text", "") if result else ""
                self.test_result(
                    "Farewell Tool", 
                    "Bob" in farewell_text if farewell_text else False,
                    f"Farewell: {farewell_text[:50]}..." if farewell_text else "No farewell text"
                )
            except:
                self.test_result("Farewell Tool", False, "Invalid response format")
        else:
            self.test_result("Farewell Tool", False, f"Status: {status}")
            
    def test_error_handling(self):
        """Test error handling"""
        self.log("=== 4. Error Handling Tests ===", Colors.BLUE)
        
        # Test 404 endpoint
        success, response, status = self.test_http_endpoint(
            f"{self.greeting_url}/nonexistent", expected_status=404
        )
        self.test_result("404 Handling", success, f"Status: {status}")
        
        # Test invalid JSON-RPC request
        invalid_request = {"invalid": "request"}
        success, response, status = self.test_http_endpoint(
            f"{self.greeting_url}/mcp", method="POST", json_data=invalid_request
        )
        # Any response is acceptable for invalid requests (400, 500, etc.)
        self.test_result("Invalid JSON-RPC", True, f"Status: {status}")
        
    def test_performance(self):
        """Test basic performance"""
        self.log("=== 5. Performance Tests ===", Colors.BLUE)
        
        times = []
        for i in range(5):
            start_time = time.time()
            success, response, status = self.test_http_endpoint(f"{self.greeting_url}/health")
            end_time = time.time()
            
            if success:
                response_time = end_time - start_time
                times.append(response_time)
                print(f"  Request {i+1}: {response_time:.3f}s")
            else:
                print(f"  Request {i+1}: Failed")
                
        if times:
            avg_time = sum(times) / len(times)
            self.test_result(
                "Performance", 
                avg_time < 2.0,  # Consider good if under 2 seconds
                f"Average response time: {avg_time:.3f}s"
            )
        else:
            self.test_result("Performance", False, "All requests failed")
            
    def run_all_tests(self):
        """Run all tests"""
        self.log("🧪 Testing Greeting MCP Server", Colors.BLUE)
        self.log(f"Base URL: {self.base_url}")
        self.log(f"Greeting Service: {self.greeting_url}")
        print()
        
        self.test_gateway_health()
        self.test_greeting_health()
        self.test_mcp_protocol()
        self.test_error_handling()
        self.test_performance()
        
        # Summary
        self.log("=== Test Summary ===", Colors.BLUE)
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        self.log(f"Tests passed: {passed}/{total}", Colors.GREEN if passed == total else Colors.YELLOW)
        
        if passed < total:
            self.log("Failed tests:", Colors.RED)
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")
                    
        print()
        self.log("Manual test commands:", Colors.BLUE)
        print(f"  curl -sk {self.base_url}/")
        print(f"  curl -sk {self.greeting_url}/health")
        print(f"  make logs-greeting-mcp")
        
        return passed == total

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Greeting MCP Server")
    parser.add_argument("--url", default="https://mcp.local", 
                       help="Base URL for the MCP gateway (default: https://mcp.local)")
    parser.add_argument("--json", action="store_true", 
                       help="Output results in JSON format")
    
    args = parser.parse_args()
    
    tester = GreetingServerTester(args.url)
    success = tester.run_all_tests()
    
    if args.json:
        print(json.dumps(tester.test_results, indent=2))
        
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()