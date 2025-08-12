#!/usr/bin/env python3
"""
FRANK Platform - Load Testing Module
Comprehensive performance and load testing for the threat intelligence platform.
"""

import asyncio
import time
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import requests
from dataclasses import dataclass

@dataclass
class LoadTestResult:
    """Data class for load test results"""
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float

class LoadTester:
    """Load testing class for FRANK platform"""
    
    def __init__(self, base_url: str, auth_token: str = None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.session = requests.Session()
        if auth_token:
            self.session.headers.update({'Authorization': f'Bearer {auth_token}'})
    
    def single_request(self, endpoint: str, method: str = 'GET', 
                      payload: Dict = None, timeout: int = 30) -> Dict:
        """Execute a single request and measure performance"""
        start_time = time.time()
        try:
            if method == 'GET':
                response = self.session.get(
                    f"{self.base_url}{endpoint}", 
                    timeout=timeout
                )
            elif method == 'POST':
                response = self.session.post(
                    f"{self.base_url}{endpoint}", 
                    json=payload, 
                    timeout=timeout
                )
            elif method == 'PUT':
                response = self.session.put(
                    f"{self.base_url}{endpoint}", 
                    json=payload, 
                    timeout=timeout
                )
            elif method == 'DELETE':
                response = self.session.delete(
                    f"{self.base_url}{endpoint}", 
                    timeout=timeout
                )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            return {
                'success': response.status_code < 400,
                'status_code': response.status_code,
                'response_time': response_time,
                'error': None
            }
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            return {
                'success': False,
                'status_code': 0,
                'response_time': response_time,
                'error': str(e)
            }
    
    def load_test(self, endpoint: str, concurrent_users: int = 10, 
                  total_requests: int = 100, method: str = 'GET',
                  payload: Dict = None) -> LoadTestResult:
        """Execute load test with specified parameters"""
        print(f"Starting load test: {endpoint}")
        print(f"Concurrent users: {concurrent_users}")
        print(f"Total requests: {total_requests}")
        
        start_time = time.time()
        results = []
        
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = []
            for _ in range(total_requests):
                future = executor.submit(
                    self.single_request, endpoint, method, payload
                )
                futures.append(future)
            
            for future in as_completed(futures):
                results.append(future.result())
        
        end_time = time.time()
        test_duration = end_time - start_time
        
        # Calculate statistics
        successful_requests = sum(1 for r in results if r['success'])
        failed_requests = total_requests - successful_requests
        response_times = [r['response_time'] for r in results]
        
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Calculate percentiles
        sorted_times = sorted(response_times)
        p95_index = int(0.95 * len(sorted_times))
        p99_index = int(0.99 * len(sorted_times))
        p95_response_time = sorted_times[p95_index]
        p99_response_time = sorted_times[p99_index]
        
        requests_per_second = total_requests / test_duration
        error_rate = (failed_requests / total_requests) * 100
        
        return LoadTestResult(
            endpoint=endpoint,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate
        )
    
    def stress_test(self, endpoint: str, max_users: int = 100, 
                   step_size: int = 10, step_duration: int = 30) -> List[LoadTestResult]:
        """Execute stress test with gradually increasing load"""
        print(f"Starting stress test: {endpoint}")
        print(f"Max users: {max_users}, Step size: {step_size}")
        
        results = []
        current_users = step_size
        
        while current_users <= max_users:
            print(f"Testing with {current_users} concurrent users...")
            requests_for_step = current_users * step_duration
            
            result = self.load_test(
                endpoint=endpoint,
                concurrent_users=current_users,
                total_requests=requests_for_step
            )
            results.append(result)
            
            # Check if system is breaking down
            if result.error_rate > 50:
                print(f"High error rate detected ({result.error_rate:.2f}%), stopping stress test")
                break
            
            current_users += step_size
            time.sleep(5)  # Brief pause between steps
        
        return results

class PerformanceTestSuite:
    """Comprehensive performance test suite"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results = {}
    
    def run_api_performance_tests(self, auth_token: str = None):
        """Run performance tests for all API endpoints"""
        tester = LoadTester(self.base_url, auth_token)
        
        # Test scenarios
        test_scenarios = [
            {
                'name': 'threat_data_retrieval',
                'endpoint': '/api/v1/threats',
                'method': 'GET',
                'users': 20,
                'requests': 200
            },
            {
                'name': 'threat_submission',
                'endpoint': '/api/v1/threats',
                'method': 'POST',
                'payload': {
                    'type': 'malware',
                    'indicator': 'test-hash-123',
                    'severity': 'high',
                    'source': 'load-test'
                },
                'users': 10,
                'requests': 100
            },
            {
                'name': 'search_functionality',
                'endpoint': '/api/v1/search?q=malware',
                'method': 'GET',
                'users': 15,
                'requests': 150
            },
            {
                'name': 'user_authentication',
                'endpoint': '/api/v1/auth/login',
                'method': 'POST',
                'payload': {
                    'username': 'test@example.com',
                    'password': 'TestPassword123!'
                },
                'users': 5,
                'requests': 50
            }
        ]
        
        for scenario in test_scenarios:
            print(f"\n{'='*50}")
            print(f"Running performance test: {scenario['name']}")
            print(f"{'='*50}")
            
            result = tester.load_test(
                endpoint=scenario['endpoint'],
                method=scenario['method'],
                concurrent_users=scenario['users'],
                total_requests=scenario['requests'],
                payload=scenario.get('payload')
            )
            
            self.results[scenario['name']] = result
            self.print_result(result)
    
    def run_stress_tests(self, auth_token: str = None):
        """Run stress tests to find breaking points"""
        tester = LoadTester(self.base_url, auth_token)
        
        critical_endpoints = [
            '/api/v1/threats',
            '/api/v1/search',
            '/api/v1/auth/login'
        ]
        
        for endpoint in critical_endpoints:
            print(f"\n{'='*50}")
            print(f"Running stress test: {endpoint}")
            print(f"{'='*50}")
            
            stress_results = tester.stress_test(
                endpoint=endpoint,
                max_users=100,
                step_size=10,
                step_duration=30
            )
            
            self.results[f"stress_{endpoint.replace('/', '_')}"] = stress_results
            
            # Print summary
            print("\nStress Test Summary:")
            for i, result in enumerate(stress_results):
                users = (i + 1) * 10
                print(f"Users: {users:3d} | "
                      f"RPS: {result.requests_per_second:6.2f} | "
                      f"Avg RT: {result.avg_response_time*1000:6.1f}ms | "
                      f"Error Rate: {result.error_rate:5.1f}%")
    
    def print_result(self, result: LoadTestResult):
        """Print formatted test results"""
        print(f"\nLoad Test Results for: {result.endpoint}")
        print(f"{'='*50}")
        print(f"Total Requests:      {result.total_requests}")
        print(f"Successful:          {result.successful_requests}")
        print(f"Failed:              {result.failed_requests}")
        print(f"Error Rate:          {result.error_rate:.2f}%")
        print(f"Requests/Second:     {result.requests_per_second:.2f}")
        print(f"")
        print(f"Response Times (ms):")
        print(f"  Average:           {result.avg_response_time*1000:.1f}")
        print(f"  Minimum:           {result.min_response_time*1000:.1f}")
        print(f"  Maximum:           {result.max_response_time*1000:.1f}")
        print(f"  95th Percentile:   {result.p95_response_time*1000:.1f}")
        print(f"  99th Percentile:   {result.p99_response_time*1000:.1f}")
    
    def generate_report(self, output_file: str = "performance_report.json"):
        """Generate performance test report"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'base_url': self.base_url,
            'results': {}
        }
        
        for test_name, result in self.results.items():
            if isinstance(result, LoadTestResult):
                report['results'][test_name] = {
                    'endpoint': result.endpoint,
                    'total_requests': result.total_requests,
                    'successful_requests': result.successful_requests,
                    'failed_requests': result.failed_requests,
                    'error_rate': result.error_rate,
                    'requests_per_second': result.requests_per_second,
                    'avg_response_time_ms': result.avg_response_time * 1000,
                    'p95_response_time_ms': result.p95_response_time * 1000,
                    'p99_response_time_ms': result.p99_response_time * 1000
                }
            elif isinstance(result, list):  # Stress test results
                report['results'][test_name] = [
                    {
                        'concurrent_users': (i + 1) * 10,
                        'requests_per_second': r.requests_per_second,
                        'avg_response_time_ms': r.avg_response_time * 1000,
                        'error_rate': r.error_rate
                    }
                    for i, r in enumerate(result)
                ]
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nPerformance report saved to: {output_file}")

def main():
    """Main function to run performance tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FRANK Platform Load Testing')
    parser.add_argument('--url', required=True, help='Base URL of the API')
    parser.add_argument('--token', help='Authentication token')
    parser.add_argument('--test-type', choices=['load', 'stress', 'all'], 
                       default='all', help='Type of test to run')
    parser.add_argument('--output', default='performance_report.json',
                       help='Output file for results')
    
    args = parser.parse_args()
    
    suite = PerformanceTestSuite(args.url)
    
    if args.test_type in ['load', 'all']:
        print("Running load tests...")
        suite.run_api_performance_tests(args.token)
    
    if args.test_type in ['stress', 'all']:
        print("\nRunning stress tests...")
        suite.run_stress_tests(args.token)
    
    suite.generate_report(args.output)
    print("\nPerformance testing completed!")

if __name__ == '__main__':
    main()
