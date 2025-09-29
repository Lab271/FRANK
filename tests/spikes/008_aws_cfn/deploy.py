#!/usr/bin/env python3
"""
FRANK 008 AWS Spike - Python CloudFormation Deployer

Cross-account deployment orchestrator for FRANK spike infrastructure.
Handles deployment across spike account (infrastructure) and main account (Route53).

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import json
import logging
import os
import sys
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from utils.aws_client import CrossAccountAWSClient
from utils.stack_deployer import CloudFormationStackDeployer
from utils.domain_validator import DomainValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FRANKDeployer:
    """Main orchestrator for FRANK spike deployment"""
    
    def __init__(self, config_dir: str = 'config'):
        self.config_dir = Path(config_dir)
        self.templates_dir = Path('templates')
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize AWS clients
        self.aws_client = CrossAccountAWSClient(self.config)
        self.stack_deployer = CloudFormationStackDeployer(self.aws_client)
        self.domain_validator = DomainValidator(self.aws_client)
        
        # Stack definitions
        self.stacks = {
            'networking': {
                'template': 'networking.yaml',
                'account': 'spike',
                'dependencies': []
            },
            'load-balancer': {
                'template': 'load-balancer.yaml', 
                'account': 'spike',
                'dependencies': ['networking']
            },
            'ssl-cert': {
                'template': 'ssl-cert.yaml',
                'account': 'spike', 
                'dependencies': []
            },
            'route53': {
                'template': 'route53.yaml',
                'account': 'main',
                'dependencies': ['load-balancer', 'ssl-cert']
            },
            'ecs': {
                'template': 'ecs.yaml',
                'account': 'spike',
                'dependencies': ['networking', 'load-balancer']
            }
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML files"""
        try:
            # Load account configuration
            with open(self.config_dir / 'accounts.yaml', 'r') as f:
                accounts = yaml.safe_load(f)
            
            # Load deployment parameters
            with open(self.config_dir / 'spike-params.yaml', 'r') as f:
                params = yaml.safe_load(f)
            
            return {
                'accounts': accounts,
                'parameters': params,
                'project_name': 'frank-008-aws',
                'environment': 'spike'
            }
        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {e}")
            sys.exit(1)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration: {e}")
            sys.exit(1)
    
    def setup_accounts(self) -> None:
        """Set up cross-account access and verify permissions"""
        logger.info("🔧 Setting up cross-account access...")
        
        try:
            # Test spike account access
            logger.info("Testing spike account access...")
            spike_sts = self.aws_client.get_client('sts', 'spike')
            spike_identity = spike_sts.get_caller_identity()
            logger.info(f"✅ Spike account: {spike_identity['Account']}")
            
            # Test main account cross-account role
            logger.info("Testing main account cross-account access...")
            main_sts = self.aws_client.get_client('sts', 'main')
            main_identity = main_sts.get_caller_identity()
            logger.info(f"✅ Main account: {main_identity['Account']}")
            
            # Deploy cross-account IAM role if needed
            self._ensure_cross_account_role()
            
            # Verify Route53 permissions
            self._verify_route53_permissions()
            
            logger.info("✅ Cross-account setup complete!")
            
        except Exception as e:
            logger.error(f"❌ Cross-account setup failed: {e}")
            raise
    
    def _ensure_cross_account_role(self) -> None:
        """Ensure cross-account IAM role exists in main account"""
        try:
            iam_client = self.aws_client.get_client('iam', 'main')
            role_name = self.config['accounts']['main']['cross_account_role_name']
            
            try:
                role = iam_client.get_role(RoleName=role_name)
                logger.info(f"✅ Cross-account role exists: {role['Role']['Arn']}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    logger.warning(f"⚠️ Cross-account role {role_name} not found")
                    logger.info("Please create the role manually or run setup-role command")
                else:
                    raise
        except Exception as e:
            logger.warning(f"Could not verify cross-account role: {e}")
    
    def _verify_route53_permissions(self) -> None:
        """Verify Route53 permissions in main account"""
        try:
            route53_client = self.aws_client.get_client('route53', 'main')
            hosted_zone_name = self.config['parameters']['domain']['hosted_zone']
            
            # List hosted zones to verify access
            response = route53_client.list_hosted_zones()
            zones = [zone for zone in response['HostedZones'] 
                    if zone['Name'].rstrip('.') == hosted_zone_name]
            
            if zones:
                logger.info(f"✅ Route53 access verified for {hosted_zone_name}")
            else:
                logger.warning(f"⚠️ Hosted zone {hosted_zone_name} not found")
                
        except Exception as e:
            logger.warning(f"Could not verify Route53 permissions: {e}")
    
    def deploy_all(self, dry_run: bool = False) -> None:
        """Deploy all infrastructure stacks"""
        logger.info("🚀 Starting FRANK spike deployment...")
        
        if dry_run:
            logger.info("🔍 DRY RUN MODE - No actual resources will be created")
        
        try:
            # Build deployment order based on dependencies
            deployment_order = self._calculate_deployment_order()
            logger.info(f"Deployment order: {' -> '.join(deployment_order)}")
            
            deployed_stacks = {}
            
            for stack_name in deployment_order:
                stack_config = self.stacks[stack_name]
                logger.info(f"📦 Deploying {stack_name} stack...")
                
                # Prepare stack parameters
                parameters = self._prepare_stack_parameters(
                    stack_name, stack_config, deployed_stacks
                )
                
                # Deploy stack
                if not dry_run:
                    stack_info = self.stack_deployer.deploy_stack(
                        stack_name=f"{self.config['project_name']}-{stack_name}",
                        template_path=self.templates_dir / stack_config['template'],
                        parameters=parameters,
                        account=stack_config['account'],
                        tags={
                            'Project': 'FRANK',
                            'Environment': self.config['environment'],
                            'ManagedBy': 'PythonCloudFormation',
                            'Owner': 'SchubergPhilis'
                        }
                    )
                    deployed_stacks[stack_name] = stack_info
                    
                    # Handle SSL certificate validation
                    if stack_name == 'ssl-cert':
                        self._handle_ssl_validation(stack_info, deployed_stacks)
                else:
                    logger.info(f"[DRY RUN] Would deploy {stack_name}")
                    deployed_stacks[stack_name] = {'outputs': {}}
            
            if not dry_run:
                # Deploy container application
                self._deploy_application()
                
                # Final validation
                self._validate_deployment(deployed_stacks)
            
            logger.info("✅ FRANK spike deployment complete!")
            self._show_deployment_info(deployed_stacks)
            
        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            raise
    
    def _calculate_deployment_order(self) -> List[str]:
        """Calculate deployment order based on dependencies"""
        ordered = []
        remaining = set(self.stacks.keys())
        
        while remaining:
            # Find stacks with no unmet dependencies
            ready = [
                stack for stack in remaining 
                if all(dep in ordered for dep in self.stacks[stack]['dependencies'])
            ]
            
            if not ready:
                raise ValueError(f"Circular dependency detected in stacks: {remaining}")
            
            # Add first ready stack
            next_stack = ready[0]
            ordered.append(next_stack)
            remaining.remove(next_stack)
        
        return ordered
    
    def _prepare_stack_parameters(self, stack_name: str, stack_config: Dict,
                                 deployed_stacks: Dict) -> Dict[str, str]:
        """Prepare parameters for stack deployment"""
        params = self.config['parameters'].copy()
        
        # Add outputs from dependent stacks
        for dep_stack in stack_config['dependencies']:
            if dep_stack in deployed_stacks:
                dep_outputs = deployed_stacks[dep_stack].get('outputs', {})
                params.update(dep_outputs)
        
        # Convert nested dict to flat string parameters
        flat_params = {}
        for key, value in params.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    flat_params[f"{key.title()}{subkey.title()}"] = str(subvalue)
            else:
                flat_params[key.title()] = str(value)
        
        return flat_params
    
    def _handle_ssl_validation(self, ssl_stack_info: Dict, deployed_stacks: Dict) -> None:
        """Handle SSL certificate validation"""
        logger.info("🔒 Handling SSL certificate validation...")
        
        # Get certificate validation records from stack outputs
        validation_records = ssl_stack_info.get('outputs', {}).get('ValidationRecords')
        
        if validation_records:
            # Parse validation records and create DNS records in main account
            self.domain_validator.create_validation_records(
                validation_records, 'main'
            )
            
            # Wait for certificate validation
            cert_arn = ssl_stack_info.get('outputs', {}).get('CertificateArn')
            if cert_arn:
                self.domain_validator.wait_for_validation(cert_arn, 'spike')
    
    def _deploy_application(self) -> None:
        """Deploy the FastAPI application container"""
        logger.info("🐳 Deploying application container...")
        
        try:
            # Build and push container image
            self._build_and_push_container()
            
            # Update ECS service
            self._update_ecs_service()
            
            logger.info("✅ Application deployment complete!")
            
        except Exception as e:
            logger.error(f"Application deployment failed: {e}")
            raise
    
    def _build_and_push_container(self) -> None:
        """Build and push container image to ECR"""
        import subprocess
        
        # Get ECR repository URL
        ecr_repo_url = self._get_ecr_repository_url()
        
        # Build container for correct architecture
        logger.info("Building container image...")
        build_cmd = [
            'docker', 'buildx', 'build',
            '--platform', 'linux/amd64',
            '--load',
            '-t', f'frank-spike:latest',
            '.'
        ]
        subprocess.run(build_cmd, check=True)
        
        # Login to ECR
        logger.info("Logging into ECR...")
        ecr_client = self.aws_client.get_client('ecr', 'spike')
        login_response = ecr_client.get_authorization_token()
        
        import base64
        token = login_response['authorizationData'][0]['authorizationToken']
        username, password = base64.b64decode(token).decode().split(':')
        
        login_cmd = [
            'docker', 'login',
            '--username', username,
            '--password-stdin',
            ecr_repo_url.split('/')[0]
        ]
        subprocess.run(login_cmd, input=password, text=True, check=True)
        
        # Tag and push image
        logger.info("Pushing container image...")
        subprocess.run(['docker', 'tag', 'frank-spike:latest', f'{ecr_repo_url}:latest'], check=True)
        subprocess.run(['docker', 'push', f'{ecr_repo_url}:latest'], check=True)
    
    def _get_ecr_repository_url(self) -> str:
        """Get ECR repository URL from ECS stack"""
        stack_name = f"{self.config['project_name']}-ecs"
        return self.stack_deployer.get_stack_output(stack_name, 'ECRRepositoryURL', 'spike')
    
    def _update_ecs_service(self) -> None:
        """Force ECS service update to deploy new container"""
        ecs_client = self.aws_client.get_client('ecs', 'spike')
        
        cluster_name = f"{self.config['project_name']}-cluster"
        service_name = f"{self.config['project_name']}-service"
        
        logger.info("Updating ECS service...")
        ecs_client.update_service(
            cluster=cluster_name,
            service=service_name,
            forceNewDeployment=True
        )
        
        # Wait for service to stabilize
        logger.info("Waiting for ECS service to stabilize...")
        waiter = ecs_client.get_waiter('services_stable')
        waiter.wait(
            cluster=cluster_name,
            services=[service_name],
            WaiterConfig={'maxAttempts': 30, 'delay': 30}
        )
    
    def _validate_deployment(self, deployed_stacks: Dict) -> None:
        """Validate the deployment is working"""
        logger.info("🔍 Validating deployment...")
        
        try:
            # Get application URL
            app_url = self._get_application_url(deployed_stacks)
            
            if app_url:
                # Test health endpoint
                import requests
                health_url = f"{app_url}/health"
                
                logger.info(f"Testing health endpoint: {health_url}")
                response = requests.get(health_url, timeout=30)
                
                if response.status_code == 200:
                    logger.info("✅ Health check passed!")
                else:
                    logger.warning(f"⚠️ Health check returned {response.status_code}")
            
        except Exception as e:
            logger.warning(f"Validation failed: {e}")
    
    def _get_application_url(self, deployed_stacks: Dict) -> Optional[str]:
        """Get the application URL from deployed stacks"""
        if 'route53' in deployed_stacks:
            domain_name = self.config['parameters']['domain']['name']
            return f"https://{domain_name}"
        elif 'load-balancer' in deployed_stacks:
            alb_dns = deployed_stacks['load-balancer'].get('outputs', {}).get('LoadBalancerDNS')
            return f"http://{alb_dns}" if alb_dns else None
        return None
    
    def _show_deployment_info(self, deployed_stacks: Dict) -> None:
        """Show deployment information"""
        print("\n" + "="*50)
        print("🎉 FRANK SPIKE DEPLOYMENT COMPLETE!")
        print("="*50)
        
        app_url = self._get_application_url(deployed_stacks)
        if app_url:
            print(f"🌐 Application URL: {app_url}")
            print(f"❤️  Health Check: {app_url}/health")
            print(f"📚 API Docs: {app_url}/docs")
        
        print(f"📊 Deployed Stacks: {len(deployed_stacks)}")
        for stack_name in deployed_stacks:
            print(f"  ✅ {stack_name}")
        
        print("\n💡 Useful Commands:")
        print(f"  Status: python deploy.py status")
        print(f"  Destroy: python deploy.py destroy --confirm-destruction")
        print("="*50)
    
    def show_status(self) -> None:
        """Show current deployment status"""
        logger.info("📊 Checking deployment status...")
        
        for stack_name, stack_config in self.stacks.items():
            full_stack_name = f"{self.config['project_name']}-{stack_name}"
            account = stack_config['account']
            
            status = self.stack_deployer.get_stack_status(full_stack_name, account)
            print(f"{stack_name:15} ({account:>5}): {status}")
    
    def destroy_all(self, confirm: bool = False) -> None:
        """Destroy all deployed stacks"""
        if not confirm:
            logger.error("❌ Destroy requires --confirm-destruction flag")
            return
        
        logger.warning("🔥 DESTROYING ALL FRANK SPIKE INFRASTRUCTURE")
        
        # Reverse deployment order for destruction
        deployment_order = self._calculate_deployment_order()
        destruction_order = list(reversed(deployment_order))
        
        for stack_name in destruction_order:
            full_stack_name = f"{self.config['project_name']}-{stack_name}"
            account = self.stacks[stack_name]['account']
            
            logger.info(f"🗑️  Destroying {stack_name} stack...")
            self.stack_deployer.delete_stack(full_stack_name, account)
        
        logger.info("✅ All stacks destroyed!")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='FRANK 008 AWS Spike Deployer')
    parser.add_argument('command', choices=['setup-accounts', 'deploy', 'status', 'destroy', 'update-app'])
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deployed without actually deploying')
    parser.add_argument('--confirm-destruction', action='store_true', help='Confirm destruction of all resources')
    
    args = parser.parse_args()
    
    try:
        deployer = FRANKDeployer()
        
        if args.command == 'setup-accounts':
            deployer.setup_accounts()
        elif args.command == 'deploy':
            deployer.deploy_all(dry_run=args.dry_run)
        elif args.command == 'status':
            deployer.show_status()
        elif args.command == 'destroy':
            deployer.destroy_all(confirm=args.confirm_destruction)
        elif args.command == 'update-app':
            deployer._deploy_application()
            
    except KeyboardInterrupt:
        logger.info("❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Operation failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()