#!/usr/bin/env python3
"""
FRANK Platform - Chaos Engineering Test Module
Testing system resilience and failure recovery capabilities.
"""

import random
import time
import json
import subprocess
import threading
from typing import Dict, List, Any, Callable
from dataclasses import dataclass
import logging

@dataclass
class ChaosExperiment:
    """Data class for chaos experiments"""
    name: str
    description: str
    target: str
    action: Callable
    recovery_action: Callable
    expected_behavior: str
    duration_seconds: int = 60
    impact_level: str = "LOW"  # LOW, MEDIUM, HIGH

@dataclass
class ChaosResult:
    """Data class for chaos experiment results"""
    experiment_name: str
    start_time: str
    end_time: str
    duration: float
    status: str  # SUCCESS, FAILED, PARTIAL
    impact_observed: str
    recovery_time: float
    lessons_learned: List[str]
    metrics: Dict[str, Any]

class ChaosEngineer:
    """Chaos engineering test executor"""
    
    def __init__(self, environment: str = "staging"):
        self.environment = environment
        self.results = []
        self.active_experiments = []
        self.baseline_metrics = {}
        
        # Safety checks
        if environment.lower() == "production":
            raise ValueError("Chaos testing should not be run in production without proper safeguards!")
    
    def collect_baseline_metrics(self) -> Dict[str, Any]:
        """Collect baseline system metrics before experiments"""
        baseline = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'api_response_time': self._measure_api_response_time(),
            'error_rate': self._measure_error_rate(),
            'throughput': self._measure_throughput(),
            'resource_utilization': self._measure_resource_utilization()
        }
        
        self.baseline_metrics = baseline
        return baseline
    
    def _measure_api_response_time(self) -> float:
        """Measure average API response time"""
        # Simulate API response time measurement
        # In real implementation, this would make actual API calls
        return random.uniform(100, 300)  # milliseconds
    
    def _measure_error_rate(self) -> float:
        """Measure current error rate"""
        # Simulate error rate measurement
        return random.uniform(0, 2)  # percentage
    
    def _measure_throughput(self) -> float:
        """Measure current throughput"""
        # Simulate throughput measurement
        return random.uniform(100, 500)  # requests per second
    
    def _measure_resource_utilization(self) -> Dict[str, float]:
        """Measure resource utilization"""
        return {
            'cpu_percent': random.uniform(20, 60),
            'memory_percent': random.uniform(30, 70),
            'disk_percent': random.uniform(10, 40)
        }
    
    def run_experiment(self, experiment: ChaosExperiment) -> ChaosResult:
        """Execute a chaos experiment"""
        print(f"Starting chaos experiment: {experiment.name}")
        print(f"Description: {experiment.description}")
        print(f"Impact Level: {experiment.impact_level}")
        print(f"Duration: {experiment.duration_seconds} seconds")
        
        start_time = time.time()
        start_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Collect pre-experiment metrics
        pre_metrics = {
            'api_response_time': self._measure_api_response_time(),
            'error_rate': self._measure_error_rate(),
            'throughput': self._measure_throughput()
        }
        
        try:
            # Execute the chaos action
            print(f"Executing chaos action on {experiment.target}...")
            experiment.action()
            
            # Monitor during experiment
            monitoring_thread = threading.Thread(
                target=self._monitor_during_experiment,
                args=(experiment.duration_seconds,)
            )
            monitoring_thread.start()
            
            # Wait for experiment duration
            time.sleep(experiment.duration_seconds)
            
            # Execute recovery action
            print("Executing recovery action...")
            recovery_start = time.time()
            experiment.recovery_action()
            recovery_time = time.time() - recovery_start
            
            # Wait for monitoring to complete
            monitoring_thread.join()
            
            # Collect post-experiment metrics
            post_metrics = {
                'api_response_time': self._measure_api_response_time(),
                'error_rate': self._measure_error_rate(),
                'throughput': self._measure_throughput()
            }
            
            # Analyze results
            end_time = time.time()
            end_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
            duration = end_time - start_time
            
            # Determine experiment status
            status = self._analyze_experiment_results(pre_metrics, post_metrics)
            impact_observed = self._describe_impact(pre_metrics, post_metrics)
            lessons_learned = self._extract_lessons(experiment, pre_metrics, post_metrics)
            
            result = ChaosResult(
                experiment_name=experiment.name,
                start_time=start_time_str,
                end_time=end_time_str,
                duration=duration,
                status=status,
                impact_observed=impact_observed,
                recovery_time=recovery_time,
                lessons_learned=lessons_learned,
                metrics={
                    'pre_experiment': pre_metrics,
                    'post_experiment': post_metrics,
                    'baseline': self.baseline_metrics
                }
            )
            
            self.results.append(result)
            print(f"Experiment completed: {status}")
            return result
            
        except Exception as e:
            print(f"Experiment failed with error: {str(e)}")
            end_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
            duration = time.time() - start_time
            
            result = ChaosResult(
                experiment_name=experiment.name,
                start_time=start_time_str,
                end_time=end_time_str,
                duration=duration,
                status="FAILED",
                impact_observed=f"Experiment failed: {str(e)}",
                recovery_time=0,
                lessons_learned=[f"Experiment execution failed: {str(e)}"],
                metrics={'error': str(e)}
            )
            
            self.results.append(result)
            return result
    
    def _monitor_during_experiment(self, duration: int):
        """Monitor system during experiment"""
        interval = min(5, duration // 10)  # Monitor every 5 seconds or 10 times during experiment
        
        for i in range(duration // interval):
            time.sleep(interval)
            
            # Collect monitoring data
            current_metrics = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'api_response_time': self._measure_api_response_time(),
                'error_rate': self._measure_error_rate(),
                'throughput': self._measure_throughput()
            }
            
            # Log critical issues
            if current_metrics['error_rate'] > 50:
                print(f"WARNING: High error rate detected: {current_metrics['error_rate']:.2f}%")
            
            if current_metrics['api_response_time'] > 5000:
                print(f"WARNING: High response time detected: {current_metrics['api_response_time']:.0f}ms")
    
    def _analyze_experiment_results(self, pre_metrics: Dict, post_metrics: Dict) -> str:
        """Analyze experiment results to determine status"""
        # Compare key metrics
        response_time_change = post_metrics['api_response_time'] - pre_metrics['api_response_time']
        error_rate_change = post_metrics['error_rate'] - pre_metrics['error_rate']
        throughput_change = post_metrics['throughput'] - pre_metrics['throughput']
        
        # Determine if system recovered properly
        if (response_time_change < 100 and  # Response time increased by less than 100ms
            error_rate_change < 5 and      # Error rate increased by less than 5%
            throughput_change > -50):      # Throughput decreased by less than 50 RPS
            return "SUCCESS"
        elif (response_time_change < 500 and
              error_rate_change < 20 and
              throughput_change > -200):
            return "PARTIAL"
        else:
            return "FAILED"
    
    def _describe_impact(self, pre_metrics: Dict, post_metrics: Dict) -> str:
        """Describe the observed impact of the experiment"""
        impacts = []
        
        response_time_change = post_metrics['api_response_time'] - pre_metrics['api_response_time']
        if abs(response_time_change) > 50:
            direction = "increased" if response_time_change > 0 else "decreased"
            impacts.append(f"API response time {direction} by {abs(response_time_change):.0f}ms")
        
        error_rate_change = post_metrics['error_rate'] - pre_metrics['error_rate']
        if abs(error_rate_change) > 1:
            direction = "increased" if error_rate_change > 0 else "decreased"
            impacts.append(f"Error rate {direction} by {abs(error_rate_change):.1f}%")
        
        throughput_change = post_metrics['throughput'] - pre_metrics['throughput']
        if abs(throughput_change) > 20:
            direction = "increased" if throughput_change > 0 else "decreased"
            impacts.append(f"Throughput {direction} by {abs(throughput_change):.0f} RPS")
        
        if not impacts:
            return "No significant impact observed"
        
        return "; ".join(impacts)
    
    def _extract_lessons(self, experiment: ChaosExperiment, pre_metrics: Dict, post_metrics: Dict) -> List[str]:
        """Extract lessons learned from the experiment"""
        lessons = []
        
        # Analyze recovery characteristics
        if post_metrics['api_response_time'] <= pre_metrics['api_response_time'] * 1.1:
            lessons.append("System demonstrated good resilience with quick recovery")
        elif post_metrics['api_response_time'] <= pre_metrics['api_response_time'] * 1.5:
            lessons.append("System recovered but with some performance degradation")
        else:
            lessons.append("System recovery was slow or incomplete")
        
        # Analyze error handling
        if post_metrics['error_rate'] <= pre_metrics['error_rate'] * 1.2:
            lessons.append("Error handling remained stable during failure")
        else:
            lessons.append("Error rate increased significantly - review error handling")
        
        # Add experiment-specific lessons
        if experiment.name.lower().contains("network"):
            lessons.append("Network partitions affect system differently than expected")
        elif experiment.name.lower().contains("cpu"):
            lessons.append("CPU stress impacts require monitoring and auto-scaling")
        elif experiment.name.lower().contains("memory"):
            lessons.append("Memory pressure affects garbage collection and performance")
        
        return lessons

class FRANKChaosTestSuite:
    """Chaos engineering test suite for FRANK platform"""
    
    def __init__(self, environment: str = "staging"):
        self.engineer = ChaosEngineer(environment)
        self.experiments = self._define_experiments()
    
    def _define_experiments(self) -> List[ChaosExperiment]:
        """Define chaos experiments for FRANK platform"""
        experiments = []
        
        # Lambda function failure simulation
        experiments.append(ChaosExperiment(
            name="Lambda Cold Start Stress",
            description="Simulate Lambda cold starts during high traffic",
            target="Lambda Functions",
            action=self._simulate_lambda_cold_starts,
            recovery_action=self._restore_lambda_warmup,
            expected_behavior="System should handle cold starts gracefully with circuit breakers",
            duration_seconds=120,
            impact_level="MEDIUM"
        ))
        
        # API Gateway throttling
        experiments.append(ChaosExperiment(
            name="API Gateway Rate Limiting",
            description="Test API Gateway rate limiting and throttling behavior",
            target="API Gateway",
            action=self._simulate_api_throttling,
            recovery_action=self._restore_api_limits,
            expected_behavior="Rate limiting should be enforced without service disruption",
            duration_seconds=90,
            impact_level="LOW"
        ))
        
        # DynamoDB throttling
        experiments.append(ChaosExperiment(
            name="DynamoDB Write Throttling",
            description="Simulate DynamoDB write capacity exceeded",
            target="DynamoDB",
            action=self._simulate_dynamo_throttling,
            recovery_action=self._restore_dynamo_capacity,
            expected_behavior="System should handle throttling with exponential backoff",
            duration_seconds=180,
            impact_level="HIGH"
        ))
        
        # Network partition simulation
        experiments.append(ChaosExperiment(
            name="Network Partition",
            description="Simulate network connectivity issues between services",
            target="Network",
            action=self._simulate_network_partition,
            recovery_action=self._restore_network_connectivity,
            expected_behavior="Services should degrade gracefully with proper timeouts",
            duration_seconds=150,
            impact_level="HIGH"
        ))
        
        # S3 service degradation
        experiments.append(ChaosExperiment(
            name="S3 Service Degradation",
            description="Simulate S3 service slowdown and errors",
            target="S3",
            action=self._simulate_s3_degradation,
            recovery_action=self._restore_s3_performance,
            expected_behavior="System should fallback gracefully when S3 is slow",
            duration_seconds=120,
            impact_level="MEDIUM"
        ))
        
        # Cognito authentication failure
        experiments.append(ChaosExperiment(
            name="Authentication Service Failure",
            description="Simulate Cognito authentication service issues",
            target="Cognito",
            action=self._simulate_auth_failure,
            recovery_action=self._restore_auth_service,
            expected_behavior="Cached tokens should allow continued access",
            duration_seconds=60,
            impact_level="HIGH"
        ))
        
        return experiments
    
    # Chaos action implementations (simulated)
    def _simulate_lambda_cold_starts(self):
        """Simulate Lambda cold start conditions"""
        print("Simulating Lambda cold starts by clearing function caches...")
        time.sleep(2)  # Simulate action execution time
    
    def _restore_lambda_warmup(self):
        """Restore Lambda warmup mechanisms"""
        print("Restoring Lambda warmup mechanisms...")
        time.sleep(1)
    
    def _simulate_api_throttling(self):
        """Simulate API Gateway throttling"""
        print("Applying API Gateway rate limits...")
        time.sleep(1)
    
    def _restore_api_limits(self):
        """Restore normal API limits"""
        print("Restoring normal API rate limits...")
        time.sleep(1)
    
    def _simulate_dynamo_throttling(self):
        """Simulate DynamoDB throttling"""
        print("Simulating DynamoDB write capacity exceeded...")
        time.sleep(2)
    
    def _restore_dynamo_capacity(self):
        """Restore DynamoDB capacity"""
        print("Restoring DynamoDB write capacity...")
        time.sleep(1)
    
    def _simulate_network_partition(self):
        """Simulate network partition"""
        print("Simulating network partition between services...")
        time.sleep(3)
    
    def _restore_network_connectivity(self):
        """Restore network connectivity"""
        print("Restoring network connectivity...")
        time.sleep(2)
    
    def _simulate_s3_degradation(self):
        """Simulate S3 service degradation"""
        print("Simulating S3 service slowdown...")
        time.sleep(2)
    
    def _restore_s3_performance(self):
        """Restore S3 performance"""
        print("Restoring S3 service performance...")
        time.sleep(1)
    
    def _simulate_auth_failure(self):
        """Simulate authentication service failure"""
        print("Simulating Cognito authentication failures...")
        time.sleep(2)
    
    def _restore_auth_service(self):
        """Restore authentication service"""
        print("Restoring Cognito authentication service...")
        time.sleep(1)
    
    def run_all_experiments(self) -> List[ChaosResult]:
        """Run all chaos experiments"""
        print("Starting FRANK Platform Chaos Engineering Tests")
        print("=" * 60)
        
        # Collect baseline metrics
        print("Collecting baseline metrics...")
        baseline = self.engineer.collect_baseline_metrics()
        print(f"Baseline API Response Time: {baseline['api_response_time']:.0f}ms")
        print(f"Baseline Error Rate: {baseline['error_rate']:.1f}%")
        print(f"Baseline Throughput: {baseline['throughput']:.0f} RPS")
        
        results = []
        
        for i, experiment in enumerate(self.experiments, 1):
            print(f"\n{'='*20} Experiment {i}/{len(self.experiments)} {'='*20}")
            
            # Wait between experiments
            if i > 1:
                print("Waiting for system stabilization...")
                time.sleep(30)
            
            result = self.engineer.run_experiment(experiment)
            results.append(result)
            
            print(f"Result: {result.status}")
            print(f"Impact: {result.impact_observed}")
            print(f"Recovery Time: {result.recovery_time:.1f}s")
        
        return results
    
    def run_specific_experiments(self, experiment_names: List[str]) -> List[ChaosResult]:
        """Run specific chaos experiments by name"""
        selected_experiments = [
            exp for exp in self.experiments 
            if exp.name in experiment_names
        ]
        
        if not selected_experiments:
            print("No matching experiments found")
            return []
        
        print(f"Running {len(selected_experiments)} selected experiments")
        
        # Collect baseline metrics
        self.engineer.collect_baseline_metrics()
        
        results = []
        for experiment in selected_experiments:
            result = self.engineer.run_experiment(experiment)
            results.append(result)
            
            # Wait between experiments
            time.sleep(10)
        
        return results
    
    def generate_chaos_report(self, results: List[ChaosResult], output_file: str = "chaos_report.json"):
        """Generate chaos engineering report"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'platform': 'FRANK',
            'environment': self.engineer.environment,
            'baseline_metrics': self.engineer.baseline_metrics,
            'summary': {
                'total_experiments': len(results),
                'successful': sum(1 for r in results if r.status == 'SUCCESS'),
                'partial': sum(1 for r in results if r.status == 'PARTIAL'),
                'failed': sum(1 for r in results if r.status == 'FAILED'),
                'avg_recovery_time': sum(r.recovery_time for r in results) / len(results) if results else 0
            },
            'experiments': [
                {
                    'name': r.experiment_name,
                    'start_time': r.start_time,
                    'end_time': r.end_time,
                    'duration': r.duration,
                    'status': r.status,
                    'impact_observed': r.impact_observed,
                    'recovery_time': r.recovery_time,
                    'lessons_learned': r.lessons_learned,
                    'metrics': r.metrics
                }
                for r in results
            ],
            'recommendations': self._generate_recommendations(results)
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nChaos engineering report saved to: {output_file}")
        self._print_summary(report)
    
    def _generate_recommendations(self, results: List[ChaosResult]) -> List[str]:
        """Generate recommendations based on chaos experiment results"""
        recommendations = []
        
        failed_experiments = [r for r in results if r.status == 'FAILED']
        partial_experiments = [r for r in results if r.status == 'PARTIAL']
        
        if failed_experiments:
            recommendations.append(
                f"Review and improve resilience for {len(failed_experiments)} failed experiments"
            )
        
        if partial_experiments:
            recommendations.append(
                f"Investigate partial failures in {len(partial_experiments)} experiments"
            )
        
        # Analyze recovery times
        slow_recovery = [r for r in results if r.recovery_time > 60]
        if slow_recovery:
            recommendations.append(
                f"Improve recovery time for {len(slow_recovery)} slow-recovering experiments"
            )
        
        # Check for patterns
        auth_issues = [r for r in results if 'auth' in r.experiment_name.lower() and r.status != 'SUCCESS']
        if auth_issues:
            recommendations.append("Strengthen authentication and authorization resilience")
        
        db_issues = [r for r in results if 'dynamo' in r.experiment_name.lower() and r.status != 'SUCCESS']
        if db_issues:
            recommendations.append("Implement better database throttling and circuit breakers")
        
        if not recommendations:
            recommendations.append("System demonstrates good resilience across all tested scenarios")
        
        return recommendations
    
    def _print_summary(self, report: Dict):
        """Print chaos engineering summary"""
        summary = report['summary']
        
        print(f"\nChaos Engineering Summary:")
        print(f"Total Experiments: {summary['total_experiments']}")
        print(f"Successful: {summary['successful']}")
        print(f"Partial: {summary['partial']}")
        print(f"Failed: {summary['failed']}")
        print(f"Average Recovery Time: {summary['avg_recovery_time']:.1f}s")
        
        print(f"\nRecommendations:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")

def main():
    """Main function to run chaos engineering tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FRANK Platform Chaos Engineering')
    parser.add_argument('--environment', default='staging', 
                       choices=['staging', 'development'],
                       help='Environment to run chaos tests')
    parser.add_argument('--experiments', nargs='*',
                       help='Specific experiments to run (run all if not specified)')
    parser.add_argument('--output', default='chaos_report.json',
                       help='Output file for results')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    suite = FRANKChaosTestSuite(args.environment)
    
    if args.experiments:
        results = suite.run_specific_experiments(args.experiments)
    else:
        results = suite.run_all_experiments()
    
    suite.generate_chaos_report(results, args.output)
    print("\nChaos engineering testing completed!")

if __name__ == '__main__':
    main()
