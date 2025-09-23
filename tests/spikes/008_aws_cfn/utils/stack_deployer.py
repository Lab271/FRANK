"""
CloudFormation Stack Deployer

Manages CloudFormation stack lifecycle with cross-account support.
Handles stack creation, updates, deletion, and monitoring.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError

from .aws_client import CrossAccountAWSClient

logger = logging.getLogger(__name__)

class CloudFormationStackDeployer:
    """Manages CloudFormation stack operations"""
    
    def __init__(self, aws_client: CrossAccountAWSClient):
        self.aws_client = aws_client
    
    def deploy_stack(self, stack_name: str, template_path: Path,
                    parameters: Dict[str, str], account: str,
                    tags: Dict[str, str] = None) -> Dict[str, Any]:
        """Deploy or update a CloudFormation stack"""
        logger.info(f"Deploying stack {stack_name} to {account} account")
        
        cfn_client = self.aws_client.get_client('cloudformation', account)
        
        # Load template
        with open(template_path, 'r') as f:
            template_body = f.read()
        
        # Prepare parameters
        cfn_parameters = [
            {'ParameterKey': key, 'ParameterValue': value}
            for key, value in parameters.items()
        ]
        
        # Prepare tags
        cfn_tags = [
            {'Key': key, 'Value': value}
            for key, value in (tags or {}).items()
        ]
        
        try:
            # Check if stack exists
            stack_exists = self._stack_exists(stack_name, account)
            
            if stack_exists:
                logger.info(f"Stack {stack_name} exists, updating...")
                
                # Create change set
                change_set_name = f"{stack_name}-changeset-{int(time.time())}"
                
                cfn_client.create_change_set(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=cfn_parameters,
                    Tags=cfn_tags,
                    ChangeSetName=change_set_name,
                    ChangeSetType='UPDATE',
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
                )
                
                # Wait for change set creation
                self._wait_for_change_set(stack_name, change_set_name, account)
                
                # Execute change set
                cfn_client.execute_change_set(
                    StackName=stack_name,
                    ChangeSetName=change_set_name
                )
                
                # Wait for update completion
                self._wait_for_stack_operation(stack_name, 'UPDATE_COMPLETE', account)
                
            else:
                logger.info(f"Stack {stack_name} does not exist, creating...")
                
                cfn_client.create_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=cfn_parameters,
                    Tags=cfn_tags,
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
                )
                
                # Wait for creation completion
                self._wait_for_stack_operation(stack_name, 'CREATE_COMPLETE', account)
            
            # Get stack information and outputs
            stack_info = self._get_stack_info(stack_name, account)
            logger.info(f"✅ Stack {stack_name} deployed successfully")
            
            return stack_info
            
        except ClientError as e:
            logger.error(f"❌ Failed to deploy stack {stack_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error deploying stack {stack_name}: {e}")
            raise
    
    def delete_stack(self, stack_name: str, account: str) -> None:
        """Delete a CloudFormation stack"""
        logger.info(f"Deleting stack {stack_name} from {account} account")
        
        cfn_client = self.aws_client.get_client('cloudformation', account)
        
        try:
            if not self._stack_exists(stack_name, account):
                logger.info(f"Stack {stack_name} does not exist, skipping deletion")
                return
            
            cfn_client.delete_stack(StackName=stack_name)
            
            # Wait for deletion completion
            self._wait_for_stack_operation(stack_name, 'DELETE_COMPLETE', account)
            
            logger.info(f"✅ Stack {stack_name} deleted successfully")
            
        except ClientError as e:
            logger.error(f"❌ Failed to delete stack {stack_name}: {e}")
            raise
    
    def get_stack_status(self, stack_name: str, account: str) -> str:
        """Get current status of a stack"""
        try:
            cfn_client = self.aws_client.get_client('cloudformation', account)
            response = cfn_client.describe_stacks(StackName=stack_name)
            return response['Stacks'][0]['StackStatus']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                return 'DOES_NOT_EXIST'
            raise
    
    def get_stack_output(self, stack_name: str, output_key: str, account: str) -> Optional[str]:
        """Get a specific output value from a stack"""
        try:
            stack_info = self._get_stack_info(stack_name, account)
            outputs = stack_info.get('outputs', {})
            return outputs.get(output_key)
        except Exception as e:
            logger.warning(f"Could not get output {output_key} from stack {stack_name}: {e}")
            return None
    
    def _stack_exists(self, stack_name: str, account: str) -> bool:
        """Check if a stack exists"""
        try:
            cfn_client = self.aws_client.get_client('cloudformation', account)
            cfn_client.describe_stacks(StackName=stack_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                return False
            raise
    
    def _wait_for_stack_operation(self, stack_name: str, target_status: str, account: str) -> None:
        """Wait for a stack operation to complete"""
        cfn_client = self.aws_client.get_client('cloudformation', account)
        
        logger.info(f"Waiting for stack {stack_name} to reach {target_status}...")
        
        max_attempts = 60  # 30 minutes maximum
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = cfn_client.describe_stacks(StackName=stack_name)
                current_status = response['Stacks'][0]['StackStatus']
                
                logger.info(f"Stack {stack_name} status: {current_status}")
                
                if current_status == target_status:
                    return
                
                # Check for failed states
                failed_states = [
                    'CREATE_FAILED', 'UPDATE_FAILED', 'DELETE_FAILED',
                    'ROLLBACK_FAILED', 'UPDATE_ROLLBACK_FAILED'
                ]
                
                if current_status in failed_states:
                    # Get stack events for debugging
                    self._log_stack_events(stack_name, account)
                    raise Exception(f"Stack {stack_name} operation failed with status: {current_status}")
                
                time.sleep(30)  # Wait 30 seconds
                attempt += 1
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ValidationError' and target_status == 'DELETE_COMPLETE':
                    # Stack was deleted
                    return
                raise
        
        raise Exception(f"Timeout waiting for stack {stack_name} to reach {target_status}")
    
    def _wait_for_change_set(self, stack_name: str, change_set_name: str, account: str) -> None:
        """Wait for change set creation to complete"""
        cfn_client = self.aws_client.get_client('cloudformation', account)
        
        logger.info(f"Waiting for change set {change_set_name} creation...")
        
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = cfn_client.describe_change_set(
                    StackName=stack_name,
                    ChangeSetName=change_set_name
                )
                
                status = response['Status']
                
                if status == 'CREATE_COMPLETE':
                    # Check if there are any changes
                    if not response.get('Changes'):
                        logger.info("No changes detected, skipping update")
                        cfn_client.delete_change_set(
                            StackName=stack_name,
                            ChangeSetName=change_set_name
                        )
                        return
                    else:
                        logger.info(f"Change set created with {len(response['Changes'])} changes")
                        return
                
                if status == 'FAILED':
                    reason = response.get('StatusReason', 'Unknown')
                    if 'No updates are to be performed' in reason:
                        logger.info("No updates needed")
                        cfn_client.delete_change_set(
                            StackName=stack_name,
                            ChangeSetName=change_set_name
                        )
                        return
                    else:
                        raise Exception(f"Change set creation failed: {reason}")
                
                time.sleep(5)
                attempt += 1
                
            except ClientError as e:
                logger.error(f"Error waiting for change set: {e}")
                raise
        
        raise Exception(f"Timeout waiting for change set {change_set_name}")
    
    def _get_stack_info(self, stack_name: str, account: str) -> Dict[str, Any]:
        """Get comprehensive stack information including outputs"""
        cfn_client = self.aws_client.get_client('cloudformation', account)
        
        response = cfn_client.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        
        # Extract outputs
        outputs = {}
        for output in stack.get('Outputs', []):
            outputs[output['OutputKey']] = output['OutputValue']
        
        return {
            'stack_id': stack['StackId'],
            'stack_name': stack['StackName'],
            'status': stack['StackStatus'],
            'creation_time': stack['CreationTime'],
            'outputs': outputs,
            'tags': {tag['Key']: tag['Value'] for tag in stack.get('Tags', [])}
        }
    
    def _log_stack_events(self, stack_name: str, account: str, limit: int = 10) -> None:
        """Log recent stack events for debugging"""
        try:
            cfn_client = self.aws_client.get_client('cloudformation', account)
            response = cfn_client.describe_stack_events(StackName=stack_name)
            
            logger.error(f"Recent events for stack {stack_name}:")
            for event in response['StackEvents'][:limit]:
                timestamp = event['Timestamp']
                resource_type = event.get('ResourceType', 'Unknown')
                logical_id = event.get('LogicalResourceId', 'Unknown')
                status = event.get('ResourceStatus', 'Unknown')
                reason = event.get('ResourceStatusReason', '')
                
                logger.error(f"  {timestamp}: {resource_type}/{logical_id} - {status} - {reason}")
                
        except Exception as e:
            logger.error(f"Could not retrieve stack events: {e}")
    
    def list_stacks(self, account: str, status_filter: List[str] = None) -> List[Dict[str, Any]]:
        """List stacks in an account with optional status filter"""
        cfn_client = self.aws_client.get_client('cloudformation', account)
        
        kwargs = {}
        if status_filter:
            kwargs['StackStatusFilter'] = status_filter
        
        response = cfn_client.list_stacks(**kwargs)
        
        return [
            {
                'name': stack['StackName'],
                'status': stack['StackStatus'],
                'creation_time': stack['CreationTime'],
                'template_description': stack.get('TemplateDescription', '')
            }
            for stack in response['StackSummaries']
        ]