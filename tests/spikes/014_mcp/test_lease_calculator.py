#!/usr/bin/env python3
"""Test script for the lease calculator MCP server"""

# Test the calculate_lease_fee function directly
from lease_calculator_mcp_server import calculate_lease_fee

def test_lease_calculator():
    """Test various scenarios for the lease calculator"""
    
    print("Testing Lease Calculator MCP Server")
    print("=" * 50)
    
    # Test 1: Basic case - 100,000 salary, age 35
    print("\nTest 1: Age 35, Salary 100,000")
    result = calculate_lease_fee(35, 100000)
    print(f"Result: {result}")
    print(f"Expected: €1000.00")
    
    # Test 2: Under 30 discount - age 25, salary 100,000
    print("\nTest 2: Age 25, Salary 100,000 (under 30 discount)")
    result = calculate_lease_fee(25, 100000)
    print(f"Result: {result}")
    print(f"Expected: €800.00 with age discount")
    
    # Test 3: Higher salary - age 35, salary 150,000
    print("\nTest 3: Age 35, Salary 150,000")
    result = calculate_lease_fee(35, 150000)
    print(f"Result: {result}")
    print(f"Expected: €1500.00")
    
    # Test 4: Lower salary with discount - age 28, salary 80,000
    print("\nTest 4: Age 28, Salary 80,000 (under 30 discount)")
    result = calculate_lease_fee(28, 80000)
    print(f"Result: {result}")
    print(f"Expected: €600.00 with age discount")
    
    # Test 5: Boundary case - age 29 (just under 30)
    print("\nTest 5: Age 29, Salary 100,000 (boundary case)")
    result = calculate_lease_fee(29, 100000)
    print(f"Result: {result}")
    print(f"Expected: €800.00 with age discount")
    
    # Test 6: Boundary case - age 30 (no discount)
    print("\nTest 6: Age 30, Salary 100,000 (boundary case)")
    result = calculate_lease_fee(30, 100000)
    print(f"Result: {result}")
    print(f"Expected: €1000.00 (no discount)")
    
    # Test 7: Low salary with discount (edge case)
    print("\nTest 7: Age 25, Salary 15,000 (low salary with discount)")
    result = calculate_lease_fee(25, 15000)
    print(f"Result: {result}")
    print(f"Expected: €0.00 (150 base - 200 discount = 0)")
    
    # Test 8: Invalid age
    print("\nTest 8: Invalid age (-5)")
    result = calculate_lease_fee(-5, 100000)
    print(f"Result: {result}")
    print(f"Expected: Error message")
    
    # Test 9: Invalid salary
    print("\nTest 9: Invalid salary (-50000)")
    result = calculate_lease_fee(35, -50000)
    print(f"Result: {result}")
    print(f"Expected: Error message")
    
    print("\n" + "=" * 50)
    print("All tests completed!")

if __name__ == "__main__":
    test_lease_calculator()
