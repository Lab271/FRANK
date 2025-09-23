"""
Domain Validator for SSL Certificates

Handles SSL certificate validation across accounts by managing
DNS validation records in Route53.
"""

import json
import logging
import time
from typing import Dict, List, Any
from botocore.exceptions import ClientError

from .aws_client import CrossAccountAWSClient

logger = logging.getLogger(__name__)

class DomainValidator:
    """Handles SSL certificate domain validation"""
    
    def __init__(self, aws_client: CrossAccountAWSClient):
        self.aws_client = aws_client
    
    def create_validation_records(self, validation_records: str, dns_account: str) -> None:
        """Create DNS validation records for SSL certificate"""
        logger.info("🔒 Creating SSL certificate validation DNS records...")
        
        try:
            # Parse validation records (assume JSON format from CloudFormation output)
            if isinstance(validation_records, str):
                records = json.loads(validation_records)
            else:
                records = validation_records
            
            route53_client = self.aws_client.get_client('route53', dns_account)
            
            # Get hosted zone ID
            hosted_zone_id = self._get_hosted_zone_id(dns_account)
            
            for record in records:
                self._create_dns_record(
                    route53_client,
                    hosted_zone_id,
                    record['Name'],
                    record['Value'],
                    record['Type']
                )
                
            logger.info(f"✅ Created {len(records)} validation DNS records")
            
        except Exception as e:
            logger.error(f"❌ Failed to create validation records: {e}")
            raise
    
    def wait_for_validation(self, certificate_arn: str, cert_account: str, 
                           timeout_minutes: int = 10) -> None:
        """Wait for SSL certificate validation to complete"""
        logger.info(f"⏳ Waiting for SSL certificate validation...")
        
        acm_client = self.aws_client.get_client('acm', cert_account)
        
        max_attempts = timeout_minutes * 2  # Check every 30 seconds
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = acm_client.describe_certificate(CertificateArn=certificate_arn)
                status = response['Certificate']['Status']
                
                logger.info(f"Certificate status: {status}")
                
                if status == 'ISSUED':
                    logger.info("✅ SSL certificate validated successfully!")
                    return
                elif status == 'FAILED':
                    failure_reason = response['Certificate'].get('FailureReason', 'Unknown')
                    raise Exception(f"Certificate validation failed: {failure_reason}")
                
                # Check domain validation status
                domain_validations = response['Certificate'].get('DomainValidationOptions', [])
                for validation in domain_validations:
                    domain = validation['DomainName']
                    validation_status = validation.get('ValidationStatus', 'UNKNOWN')
                    logger.info(f"  {domain}: {validation_status}")
                
                time.sleep(30)
                attempt += 1
                
            except ClientError as e:
                logger.error(f"Error checking certificate status: {e}")
                raise
        
        raise Exception(f"Timeout waiting for certificate validation after {timeout_minutes} minutes")
    
    def _get_hosted_zone_id(self, dns_account: str) -> str:
        """Get the hosted zone ID for the domain"""
        route53_client = self.aws_client.get_client('route53', dns_account)
        
        try:
            # Get hosted zone name from config
            hosted_zone_name = self.aws_client.config['parameters']['domain']['hosted_zone']
            
            response = route53_client.list_hosted_zones()
            
            for zone in response['HostedZones']:
                if zone['Name'].rstrip('.') == hosted_zone_name:
                    zone_id = zone['Id'].split('/')[-1]  # Extract ID from ARN
                    logger.info(f"Found hosted zone {hosted_zone_name}: {zone_id}")
                    return zone_id
            
            raise Exception(f"Hosted zone {hosted_zone_name} not found")
            
        except ClientError as e:
            logger.error(f"Error getting hosted zone: {e}")
            raise
    
    def _create_dns_record(self, route53_client, hosted_zone_id: str,
                          name: str, value: str, record_type: str) -> None:
        """Create a single DNS validation record"""
        try:
            logger.info(f"Creating DNS record: {name} -> {value}")
            
            change_batch = {
                'Comment': 'SSL certificate validation record',
                'Changes': [
                    {
                        'Action': 'UPSERT',  # Create or update
                        'ResourceRecordSet': {
                            'Name': name,
                            'Type': record_type,
                            'TTL': 300,
                            'ResourceRecords': [
                                {'Value': value}
                            ]
                        }
                    }
                ]
            }
            
            response = route53_client.change_resource_record_sets(
                HostedZoneId=hosted_zone_id,
                ChangeBatch=change_batch
            )
            
            change_id = response['ChangeInfo']['Id']
            logger.info(f"DNS record change submitted: {change_id}")
            
            # Wait for the change to propagate
            self._wait_for_dns_change(route53_client, change_id)
            
        except ClientError as e:
            logger.error(f"Error creating DNS record {name}: {e}")
            raise
    
    def _wait_for_dns_change(self, route53_client, change_id: str) -> None:
        """Wait for DNS change to propagate"""
        logger.info("Waiting for DNS change propagation...")
        
        max_attempts = 20  # 10 minutes maximum
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = route53_client.get_change(Id=change_id)
                status = response['ChangeInfo']['Status']
                
                if status == 'INSYNC':
                    logger.info("✅ DNS change propagated successfully")
                    return
                
                time.sleep(30)
                attempt += 1
                
            except ClientError as e:
                logger.error(f"Error checking DNS change status: {e}")
                raise
        
        logger.warning("⚠️ DNS change propagation timeout, but continuing...")
    
    def create_application_dns_record(self, domain_name: str, alb_dns_name: str, 
                                    alb_zone_id: str, dns_account: str) -> None:
        """Create the main application DNS record pointing to ALB"""
        logger.info(f"🌐 Creating application DNS record: {domain_name}")
        
        try:
            route53_client = self.aws_client.get_client('route53', dns_account)
            hosted_zone_id = self._get_hosted_zone_id(dns_account)
            
            change_batch = {
                'Comment': 'FRANK application DNS record',
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': domain_name,
                            'Type': 'A',
                            'AliasTarget': {
                                'DNSName': alb_dns_name,
                                'EvaluateTargetHealth': True,
                                'HostedZoneId': alb_zone_id
                            }
                        }
                    }
                ]
            }
            
            response = route53_client.change_resource_record_sets(
                HostedZoneId=hosted_zone_id,
                ChangeBatch=change_batch
            )
            
            change_id = response['ChangeInfo']['Id']
            logger.info(f"Application DNS record created: {change_id}")
            
            # Wait for propagation
            self._wait_for_dns_change(route53_client, change_id)
            
            logger.info(f"✅ Application accessible at https://{domain_name}")
            
        except ClientError as e:
            logger.error(f"Error creating application DNS record: {e}")
            raise
    
    def cleanup_validation_records(self, certificate_arn: str, cert_account: str, 
                                  dns_account: str) -> None:
        """Clean up DNS validation records (optional cleanup)"""
        logger.info("🧹 Cleaning up SSL validation DNS records...")
        
        try:
            acm_client = self.aws_client.get_client('acm', cert_account)
            route53_client = self.aws_client.get_client('route53', dns_account)
            
            # Get certificate details
            response = acm_client.describe_certificate(CertificateArn=certificate_arn)
            domain_validations = response['Certificate'].get('DomainValidationOptions', [])
            
            hosted_zone_id = self._get_hosted_zone_id(dns_account)
            
            for validation in domain_validations:
                if 'ResourceRecord' in validation:
                    record = validation['ResourceRecord']
                    self._delete_dns_record(
                        route53_client,
                        hosted_zone_id,
                        record['Name'],
                        record['Value'],
                        record['Type']
                    )
            
            logger.info("✅ Validation records cleaned up")
            
        except Exception as e:
            logger.warning(f"Could not clean up validation records: {e}")
    
    def _delete_dns_record(self, route53_client, hosted_zone_id: str,
                          name: str, value: str, record_type: str) -> None:
        """Delete a DNS record"""
        try:
            change_batch = {
                'Comment': 'Delete SSL certificate validation record',
                'Changes': [
                    {
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': name,
                            'Type': record_type,
                            'TTL': 300,
                            'ResourceRecords': [
                                {'Value': value}
                            ]
                        }
                    }
                ]
            }
            
            route53_client.change_resource_record_sets(
                HostedZoneId=hosted_zone_id,
                ChangeBatch=change_batch
            )
            
            logger.info(f"Deleted DNS record: {name}")
            
        except ClientError as e:
            # Don't fail if record doesn't exist
            if e.response['Error']['Code'] == 'InvalidChangeBatch':
                logger.info(f"DNS record {name} already deleted or doesn't exist")
            else:
                raise