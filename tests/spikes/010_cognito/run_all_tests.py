#!/usr/bin/env python3
"""
Combined test runner for both mock_cognito and simple_api tests

Runs all tests in the correct order and provides summary results.
"""

import subprocess
import sys
import os
import time

def run_test_file(test_file, description):
    """Run a single test file and return success status"""
    print(f"\n🧪 {description}")
    print("=" * (len(description) + 4))
    
    if not os.path.exists(test_file):
        print(f"❌ Test file {test_file} not found!")
        return False
    
    start_time = time.time()
    
    try:
        # Try with pytest first, fallback to unittest
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                test_file, 
                "-v", 
                "--tb=short", 
                "--disable-warnings"
            ], check=False, capture_output=False)
        except FileNotFoundError:
            # Fallback to unittest
            result = subprocess.run([
                sys.executable, "-m", "unittest", 
                test_file.replace('.py', ''), 
                "-v"
            ], check=False, capture_output=False)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} PASSED (took {duration:.2f}s)")
            return True
        else:
            print(f"❌ {description} FAILED (took {duration:.2f}s)")
            return False
            
    except Exception as e:
        print(f"💥 Error running {test_file}: {e}")
        return False

def main():
    """Run all test suites"""
    print("🚀 FRANK Platform - Cognito Spike Test Suite")
    print("=" * 50)
    
    total_start = time.time()
    
    # Test configurations: (file, description)
    test_configs = [
        ("test_mock_cognito.py", "Mock Cognito Service Tests"),
        ("test_simple_api.py", "Simple API Service Tests")
    ]
    
    results = []
    
    for test_file, description in test_configs:
        success = run_test_file(test_file, description)
        results.append((test_file, description, success))
    
    total_end = time.time()
    total_duration = total_end - total_start
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUITE SUMMARY")
    print("=" * 50)
    print(f"⏱️  Total execution time: {total_duration:.2f} seconds")
    
    passed_count = sum(1 for _, _, success in results if success)
    total_count = len(results)
    
    print(f"✅ Test suites passed: {passed_count}/{total_count}")
    
    for test_file, description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {description}")
    
    if passed_count == total_count:
        print("\n🎉 ALL TEST SUITES PASSED!")
        return 0
    else:
        print(f"\n❌ {total_count - passed_count} TEST SUITE(S) FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())