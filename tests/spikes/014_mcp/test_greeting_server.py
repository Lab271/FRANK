#!/usr/bin/env python3
"""
Test script for the greeting MCP server
Tests the greet tool functionality
"""
import subprocess
import json
import sys

def test_mcp_server():
    """Test the greeting MCP server by sending requests via stdio"""
    
    print("=" * 60)
    print("Testing Greeting MCP Server")
    print("=" * 60)
    
    # Test 1: Initialize connection
    print("\n[Test 1] Initializing connection...")
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    # Test 2: List available tools
    print("\n[Test 2] Listing available tools...")
    list_tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    # Test 3: Call greet tool with valid name
    print("\n[Test 3] Testing greet tool with name 'Alice'...")
    greet_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "greet",
            "arguments": {
                "name": "Alice"
            }
        }
    }
    
    # Test 4: Call greet tool with another name
    print("\n[Test 4] Testing greet tool with name 'Bob'...")
    greet_request2 = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "greet",
            "arguments": {
                "name": "Bob"
            }
        }
    }
    
    # Test 5: List resources
    print("\n[Test 5] Listing available resources...")
    list_resources_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "resources/list",
        "params": {}
    }
    
    # Test 6: List prompts
    print("\n[Test 6] Listing available prompts...")
    list_prompts_request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "prompts/list",
        "params": {}
    }
    
    process = None
    try:
        # Start the MCP server
        process = subprocess.Popen(
            ['python3', 'greeting_mcp_server.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        def send_request(request):
            """Send a JSON-RPC request and get response"""
            if process.stdin is None or process.stdout is None:
                return None
            request_str = json.dumps(request) + '\n'
            process.stdin.write(request_str)
            process.stdin.flush()
            
            response_line = process.stdout.readline()
            if response_line:
                return json.loads(response_line)
            return None
        
        # Send all requests
        responses = []
        requests = [
            ("Initialize", init_request),
            ("List Tools", list_tools_request),
            ("Greet Alice", greet_request),
            ("Greet Bob", greet_request2),
            ("List Resources", list_resources_request),
            ("List Prompts", list_prompts_request)
        ]
        
        for test_name, request in requests:
            print(f"\nSending {test_name} request...")
            response = send_request(request)
            if response:
                print(f"✓ Received response for {test_name}")
                responses.append((test_name, response))
                if "result" in response:
                    print(f"  Result: {json.dumps(response['result'], indent=2)}")
                elif "error" in response:
                    print(f"  Error: {response['error']}")
            else:
                print(f"✗ No response received for {test_name}")
        
        # Terminate the process
        if process.stdin:
            process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Total requests sent: {len(requests)}")
        print(f"Total responses received: {len(responses)}")
        
        # Check if greet tool responses contain expected greeting formats
        greet_responses = [r for name, r in responses if "Greet" in name and "result" in r]
        if greet_responses:
            print(f"\n✓ Successfully received {len(greet_responses)} greeting(s):")
            for name, response in [(n, r) for n, r in responses if "Greet" in n and "result" in r]:
                if "content" in response["result"]:
                    for content in response["result"]["content"]:
                        if content.get("type") == "text":
                            print(f"  - {content.get('text')}")
        
        print("\n" + "=" * 60)
        return True
        
    except subprocess.TimeoutExpired:
        print("\n✗ Error: Server process timed out")
        if process:
            process.kill()
        return False
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        if process:
            process.kill()
        return False

if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)
