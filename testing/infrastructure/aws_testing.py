#!/usr/bin/env python3
"""
FRANK Platform - AWS Infrastructure Testing Module
Testing AWS services configuration, security, and reliability.
"""

import boto3
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

@dataclass
class AWSTestResult:
    """Data class for AWS test results"""
    service: str
    test_name: str
    status: str  # PASS, FAIL, WARNING
    message: str
    details: Dict = None

class AWSInfrastructureTester:
    """AWS infrastructure testing class"""
    
    def __init__(self, region: str = 'us-west-2'):
        self.region = region
        self.session = boto3.Session()
        self.results = []
        
        # Initialize AWS clients
        self.lambda_client = self.session.client('lambda', region_name=region)
        self.apigateway_client = self.session.client('apigateway', region_name=region)
        self.dynamodb_client = self.session.client('dynamodb', region_name=region)
        self.s3_client = self.session.client('s3', region_name=region)
        self.cognito_client = self.session.client('cognito-idp', region_name=region)
        self.kms_client = self.session.client('kms', region_name=region)
        self.opensearch_client = self.session.client('opensearch', region_name=region)
        self.stepfunctions_client = self.session.client('stepfunctions', region_name=region)
        self.ecs_client = self.session.client('ecs', region_name=region)
        self.cloudwatch_client = self.session.client('cloudwatch', region_name=region)
    
    def add_result(self, service: str, test_name: str, status: str, message: str, details: Dict = None):
        """Add test result"""
        result = AWSTestResult(service, test_name, status, message, details)
        self.results.append(result)
        
        # Log result
        log_level = logging.INFO if status == 'PASS' else logging.WARNING if status == 'WARNING' else logging.ERROR
        logging.log(log_level, f"{service} - {test_name}: {status} - {message}")
    
    def test_lambda_functions(self, function_names: List[str]):
        """Test Lambda functions"""
        print("Testing Lambda Functions...")
        
        for function_name in function_names:
            try:
                # Check if function exists
                response = self.lambda_client.get_function(FunctionName=function_name)
                self.add_result('Lambda', f'Function Exists: {function_name}', 'PASS', 
                              f'Function {function_name} exists and is accessible')
                
                # Check function configuration
                config = response['Configuration']
                
                # Test memory configuration
                memory_size = config.get('MemorySize', 0)
                if memory_size < 128:
                    self.add_result('Lambda', f'Memory Config: {function_name}', 'WARNING',
                                  f'Memory size ({memory_size}MB) might be too low')
                else:
                    self.add_result('Lambda', f'Memory Config: {function_name}', 'PASS',
                                  f'Memory size ({memory_size}MB) is appropriate')
                
                # Test timeout configuration
                timeout = config.get('Timeout', 0)
                if timeout > 900:
                    self.add_result('Lambda', f'Timeout Config: {function_name}', 'WARNING',
                                  f'Timeout ({timeout}s) is at maximum limit')
                elif timeout < 30:
                    self.add_result('Lambda', f'Timeout Config: {function_name}', 'WARNING',
                                  f'Timeout ({timeout}s) might be too low')
                else:
                    self.add_result('Lambda', f'Timeout Config: {function_name}', 'PASS',
                                  f'Timeout ({timeout}s) is appropriate')
                
                # Test environment variables (security check)
                env_vars = config.get('Environment', {}).get('Variables', {})
                sensitive_keys = ['password', 'secret', 'key', 'token']
                for key in env_vars.keys():
                    if any(sensitive in key.lower() for sensitive in sensitive_keys):
                        self.add_result('Lambda', f'Security: {function_name}', 'WARNING',
                                      f'Potentially sensitive environment variable: {key}')
                
                # Test function invocation
                try:
                    test_payload = json.dumps({"test": True, "source": "infrastructure_test"})
                    invoke_response = self.lambda_client.invoke(
                        FunctionName=function_name,
                        InvocationType='RequestResponse',
                        Payload=test_payload
                    )
                    
                    if invoke_response['StatusCode'] == 200:
                        self.add_result('Lambda', f'Invocation: {function_name}', 'PASS',
                                      f'Function invocation successful')
                    else:
                        self.add_result('Lambda', f'Invocation: {function_name}', 'FAIL',
                                      f'Function invocation failed: {invoke_response["StatusCode"]}')
                except Exception as e:
                    self.add_result('Lambda', f'Invocation: {function_name}', 'WARNING',
                                  f'Function invocation test failed: {str(e)}')
                
            except Exception as e:
                self.add_result('Lambda', f'Function Check: {function_name}', 'FAIL',
                              f'Function {function_name} not found or inaccessible: {str(e)}')
    
    def test_api_gateway(self, api_name: str):
        """Test API Gateway configuration"""
        print("Testing API Gateway...")
        
        try:
            # Find API by name
            apis = self.apigateway_client.get_rest_apis()
            target_api = None
            
            for api in apis['items']:
                if api['name'] == api_name:
                    target_api = api
                    break
            
            if not target_api:
                self.add_result('API Gateway', 'API Exists', 'FAIL',
                              f'API {api_name} not found')
                return
            
            api_id = target_api['id']
            self.add_result('API Gateway', 'API Exists', 'PASS',
                          f'API {api_name} found with ID: {api_id}')
            
            # Test API deployment
            deployments = self.apigateway_client.get_deployments(restApiId=api_id)
            if deployments['items']:
                self.add_result('API Gateway', 'Deployment', 'PASS',
                              f'API has {len(deployments["items"])} deployment(s)')
            else:
                self.add_result('API Gateway', 'Deployment', 'FAIL',
                              f'API has no deployments')
            
            # Test stages
            stages = self.apigateway_client.get_stages(restApiId=api_id)
            if stages['item']:
                stage_names = [stage['stageName'] for stage in stages['item']]
                self.add_result('API Gateway', 'Stages', 'PASS',
                              f'API has stages: {", ".join(stage_names)}')
                
                # Check for production stage
                if 'prod' not in stage_names and 'production' not in stage_names:
                    self.add_result('API Gateway', 'Production Stage', 'WARNING',
                                  f'No production stage found')
            else:
                self.add_result('API Gateway', 'Stages', 'FAIL',
                              f'API has no stages')
            
            # Test resources and methods
            resources = self.apigateway_client.get_resources(restApiId=api_id)
            resource_count = len(resources['items'])
            self.add_result('API Gateway', 'Resources', 'PASS',
                          f'API has {resource_count} resource(s)')
            
            # Check for CORS configuration
            cors_configured = False
            for resource in resources['items']:
                if 'resourceMethods' in resource:
                    if 'OPTIONS' in resource['resourceMethods']:
                        cors_configured = True
                        break
            
            if cors_configured:
                self.add_result('API Gateway', 'CORS', 'PASS', 'CORS is configured')
            else:
                self.add_result('API Gateway', 'CORS', 'WARNING', 'CORS not configured')
                
        except Exception as e:
            self.add_result('API Gateway', 'General', 'FAIL',
                          f'API Gateway test failed: {str(e)}')
    
    def test_dynamodb_tables(self, table_names: List[str]):
        """Test DynamoDB tables"""
        print("Testing DynamoDB Tables...")
        
        for table_name in table_names:
            try:
                # Check if table exists
                response = self.dynamodb_client.describe_table(TableName=table_name)
                table_info = response['Table']
                
                self.add_result('DynamoDB', f'Table Exists: {table_name}', 'PASS',
                              f'Table {table_name} exists')
                
                # Check table status
                status = table_info['TableStatus']
                if status == 'ACTIVE':
                    self.add_result('DynamoDB', f'Table Status: {table_name}', 'PASS',
                                  f'Table is ACTIVE')
                else:
                    self.add_result('DynamoDB', f'Table Status: {table_name}', 'WARNING',
                                  f'Table status is {status}')
                
                # Check encryption
                if 'SSEDescription' in table_info:
                    sse_status = table_info['SSEDescription']['Status']
                    self.add_result('DynamoDB', f'Encryption: {table_name}', 'PASS',
                                  f'Encryption is {sse_status}')
                else:
                    self.add_result('DynamoDB', f'Encryption: {table_name}', 'WARNING',
                                  f'Encryption not configured')
                
                # Check backup settings
                backup_response = self.dynamodb_client.describe_continuous_backups(
                    TableName=table_name
                )
                backup_status = backup_response['ContinuousBackupsDescription']['ContinuousBackupsStatus']
                
                if backup_status == 'ENABLED':
                    self.add_result('DynamoDB', f'Backup: {table_name}', 'PASS',
                                  f'Continuous backups enabled')
                else:
                    self.add_result('DynamoDB', f'Backup: {table_name}', 'WARNING',
                                  f'Continuous backups not enabled')
                
                # Test read/write capacity
                if 'BillingModeSummary' in table_info:
                    billing_mode = table_info['BillingModeSummary']['BillingMode']
                    self.add_result('DynamoDB', f'Billing: {table_name}', 'PASS',
                                  f'Billing mode: {billing_mode}')
                
            except Exception as e:
                self.add_result('DynamoDB', f'Table Check: {table_name}', 'FAIL',
                              f'Table {table_name} check failed: {str(e)}')
    
    def test_s3_buckets(self, bucket_names: List[str]):
        """Test S3 buckets"""
        print("Testing S3 Buckets...")
        
        for bucket_name in bucket_names:
            try:
                # Check if bucket exists
                self.s3_client.head_bucket(Bucket=bucket_name)
                self.add_result('S3', f'Bucket Exists: {bucket_name}', 'PASS',
                              f'Bucket {bucket_name} exists and is accessible')
                
                # Check bucket encryption
                try:
                    encryption = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
                    self.add_result('S3', f'Encryption: {bucket_name}', 'PASS',
                                  f'Bucket encryption is configured')
                except self.s3_client.exceptions.ClientError as e:
                    if e.response['Error']['Code'] == 'ServerSideEncryptionConfigurationNotFoundError':
                        self.add_result('S3', f'Encryption: {bucket_name}', 'WARNING',
                                      f'Bucket encryption not configured')
                
                # Check public access block
                try:
                    public_access = self.s3_client.get_public_access_block(Bucket=bucket_name)
                    pab = public_access['PublicAccessBlockConfiguration']
                    
                    if all([pab['BlockPublicAcls'], pab['IgnorePublicAcls'],
                           pab['BlockPublicPolicy'], pab['RestrictPublicBuckets']]):
                        self.add_result('S3', f'Public Access: {bucket_name}', 'PASS',
                                      f'Public access is properly blocked')
                    else:
                        self.add_result('S3', f'Public Access: {bucket_name}', 'WARNING',
                                      f'Public access block not fully configured')
                except Exception:
                    self.add_result('S3', f'Public Access: {bucket_name}', 'WARNING',
                                  f'Could not check public access block')
                
                # Check versioning
                try:
                    versioning = self.s3_client.get_bucket_versioning(Bucket=bucket_name)
                    status = versioning.get('Status', 'Disabled')
                    
                    if status == 'Enabled':
                        self.add_result('S3', f'Versioning: {bucket_name}', 'PASS',
                                      f'Versioning is enabled')
                    else:
                        self.add_result('S3', f'Versioning: {bucket_name}', 'WARNING',
                                      f'Versioning is {status}')
                except Exception:
                    self.add_result('S3', f'Versioning: {bucket_name}', 'WARNING',
                                  f'Could not check versioning status')
                
            except Exception as e:
                self.add_result('S3', f'Bucket Check: {bucket_name}', 'FAIL',
                              f'Bucket {bucket_name} check failed: {str(e)}')
    
    def test_cognito_user_pools(self, pool_names: List[str]):
        """Test Cognito User Pools"""
        print("Testing Cognito User Pools...")
        
        try:
            # List all user pools
            pools = self.cognito_client.list_user_pools(MaxResults=50)
            
            for pool_name in pool_names:
                pool_found = False
                for pool in pools['UserPools']:
                    if pool['Name'] == pool_name:
                        pool_found = True
                        pool_id = pool['Id']
                        
                        self.add_result('Cognito', f'Pool Exists: {pool_name}', 'PASS',
                                      f'User pool {pool_name} exists')
                        
                        # Get detailed pool information
                        pool_details = self.cognito_client.describe_user_pool(UserPoolId=pool_id)
                        pool_config = pool_details['UserPool']
                        
                        # Check MFA configuration
                        mfa_config = pool_config.get('MfaConfiguration', 'OFF')
                        if mfa_config == 'OFF':
                            self.add_result('Cognito', f'MFA: {pool_name}', 'WARNING',
                                          f'MFA is disabled')
                        else:
                            self.add_result('Cognito', f'MFA: {pool_name}', 'PASS',
                                          f'MFA is configured: {mfa_config}')
                        
                        # Check password policy
                        password_policy = pool_config.get('Policies', {}).get('PasswordPolicy', {})
                        min_length = password_policy.get('MinimumLength', 0)
                        
                        if min_length >= 8:
                            self.add_result('Cognito', f'Password Policy: {pool_name}', 'PASS',
                                          f'Minimum password length: {min_length}')
                        else:
                            self.add_result('Cognito', f'Password Policy: {pool_name}', 'WARNING',
                                          f'Weak password policy: minimum length {min_length}')
                        
                        break
                
                if not pool_found:
                    self.add_result('Cognito', f'Pool Check: {pool_name}', 'FAIL',
                                  f'User pool {pool_name} not found')
                    
        except Exception as e:
            self.add_result('Cognito', 'General', 'FAIL',
                          f'Cognito test failed: {str(e)}')
    
    def test_cloudwatch_monitoring(self):
        """Test CloudWatch monitoring setup"""
        print("Testing CloudWatch Monitoring...")
        
        try:
            # Check for custom metrics
            metrics = self.cloudwatch_client.list_metrics(
                Namespace='FRANK/Platform'
            )
            
            if metrics['Metrics']:
                self.add_result('CloudWatch', 'Custom Metrics', 'PASS',
                              f'Found {len(metrics["Metrics"])} custom metrics')
            else:
                self.add_result('CloudWatch', 'Custom Metrics', 'WARNING',
                              f'No custom metrics found')
            
            # Check for alarms
            alarms = self.cloudwatch_client.describe_alarms()
            
            if alarms['MetricAlarms']:
                alarm_count = len(alarms['MetricAlarms'])
                self.add_result('CloudWatch', 'Alarms', 'PASS',
                              f'Found {alarm_count} CloudWatch alarms')
                
                # Check alarm states
                ok_alarms = sum(1 for alarm in alarms['MetricAlarms'] if alarm['StateValue'] == 'OK')
                alarm_alarms = sum(1 for alarm in alarms['MetricAlarms'] if alarm['StateValue'] == 'ALARM')
                
                if alarm_alarms > 0:
                    self.add_result('CloudWatch', 'Alarm States', 'WARNING',
                                  f'{alarm_alarms} alarm(s) in ALARM state')
                else:
                    self.add_result('CloudWatch', 'Alarm States', 'PASS',
                                  f'All {ok_alarms} alarms in OK state')
            else:
                self.add_result('CloudWatch', 'Alarms', 'WARNING',
                              f'No CloudWatch alarms configured')
                
        except Exception as e:
            self.add_result('CloudWatch', 'General', 'FAIL',
                          f'CloudWatch test failed: {str(e)}')
    
    def generate_report(self, output_file: str = "aws_infrastructure_report.json"):
        """Generate infrastructure test report"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'region': self.region,
            'summary': {
                'total_tests': len(self.results),
                'passed': sum(1 for r in self.results if r.status == 'PASS'),
                'failed': sum(1 for r in self.results if r.status == 'FAIL'),
                'warnings': sum(1 for r in self.results if r.status == 'WARNING')
            },
            'results': [
                {
                    'service': r.service,
                    'test_name': r.test_name,
                    'status': r.status,
                    'message': r.message,
                    'details': r.details
                }
                for r in self.results
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nAWS Infrastructure test report saved to: {output_file}")
        
        # Print summary
        print(f"\nTest Summary:")
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Warnings: {report['summary']['warnings']}")

def main():
    """Main function to run AWS infrastructure tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FRANK Platform AWS Infrastructure Testing')
    parser.add_argument('--region', default='us-west-2', help='AWS region')
    parser.add_argument('--output', default='aws_infrastructure_report.json',
                       help='Output file for results')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    tester = AWSInfrastructureTester(args.region)
    
    # Define FRANK platform resources
    lambda_functions = [
        'frank-threat-processor',
        'frank-auth-handler',
        'frank-search-engine',
        'frank-data-pipeline',
        'frank-notification-service'
    ]
    
    dynamodb_tables = [
        'frank-threats',
        'frank-users',
        'frank-organizations',
        'frank-audit-logs'
    ]
    
    s3_buckets = [
        'frank-threat-data',
        'frank-backups',
        'frank-logs'
    ]
    
    cognito_pools = [
        'frank-user-pool'
    ]
    
    # Run tests
    print("Starting AWS Infrastructure Tests for FRANK Platform")
    print("=" * 60)
    
    tester.test_lambda_functions(lambda_functions)
    tester.test_api_gateway('frank-api')
    tester.test_dynamodb_tables(dynamodb_tables)
    tester.test_s3_buckets(s3_buckets)
    tester.test_cognito_user_pools(cognito_pools)
    tester.test_cloudwatch_monitoring()
    
    tester.generate_report(args.output)
    print("\nAWS Infrastructure testing completed!")

if __name__ == '__main__':
    main()
