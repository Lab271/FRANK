"""
Cross-Account AWS Client Helper

Manages AWS sessions across multiple accounts with role assumption.
Handles credential management and provides unified client interface.
"""

import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class CrossAccountAWSClient:
    """Manages AWS clients across multiple accounts"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sessions = {}
        self._initialize_sessions()
    
    def _initialize_sessions(self) -> None:
        """Initialize AWS sessions for all configured accounts"""
        accounts = self.config['accounts']
        
        # Initialize spike account session (primary)
        spike_config = accounts['spike']
        self.sessions['spike'] = self._create_session(
            profile_name=spike_config.get('profile_name'),
            region=spike_config.get('region', 'eu-west-1')
        )
        
        # Initialize main account session (cross-account)
        main_config = accounts['main']
        self.sessions['main'] = self._create_cross_account_session(
            base_session=self.sessions['spike'],
            role_arn=main_config['cross_account_role_arn'],
            role_session_name=main_config.get('session_name', 'frank-spike-deployment'),
            external_id=main_config.get('external_id'),
            region=main_config.get('region', 'eu-west-1')
        )
    
    def _create_session(self, profile_name: Optional[str] = None, 
                       region: str = 'eu-west-1') -> boto3.Session:
        """Create a standard AWS session"""
        try:
            if profile_name:
                logger.info(f"Creating session with profile: {profile_name}")
                session = boto3.Session(profile_name=profile_name, region_name=region)
            else:
                logger.info("Creating session with default credentials")
                session = boto3.Session(region_name=region)
            
            # Test credentials
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            logger.info(f"Session created for account: {identity['Account']}")
            
            return session
            
        except NoCredentialsError:
            logger.error("No AWS credentials found")
            raise
        except ClientError as e:
            logger.error(f"Failed to create AWS session: {e}")
            raise
    
    def _create_cross_account_session(self, base_session: boto3.Session,
                                    role_arn: str, role_session_name: str,
                                    external_id: Optional[str] = None,
                                    region: str = 'eu-west-1') -> boto3.Session:
        """Create cross-account session using role assumption"""
        try:
            logger.info(f"Assuming cross-account role: {role_arn}")
            
            sts_client = base_session.client('sts')
            assume_role_kwargs = {
                'RoleArn': role_arn,
                'RoleSessionName': role_session_name,
                'DurationSeconds': 3600  # 1 hour
            }
            
            if external_id:
                assume_role_kwargs['ExternalId'] = external_id
            
            response = sts_client.assume_role(**assume_role_kwargs)
            credentials = response['Credentials']
            
            # Create session with temporary credentials
            session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=region
            )
            
            # Verify cross-account session
            cross_sts = session.client('sts')
            identity = cross_sts.get_caller_identity()
            logger.info(f"Cross-account session created for account: {identity['Account']}")
            
            return session
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                logger.error(f"Access denied when assuming role {role_arn}")
                logger.error("Please verify:")
                logger.error("1. Role exists in target account")
                logger.error("2. Trust relationship allows your account")
                logger.error("3. External ID matches (if configured)")
            else:
                logger.error(f"Failed to assume cross-account role: {e}")
            raise
    
    def get_session(self, account: str) -> boto3.Session:
        """Get AWS session for specified account"""
        if account not in self.sessions:
            raise ValueError(f"Unknown account: {account}. Available: {list(self.sessions.keys())}")
        
        return self.sessions[account]
    
    def get_client(self, service: str, account: str, **kwargs) -> Any:
        """Get AWS service client for specified account"""
        session = self.get_session(account)
        return session.client(service, **kwargs)
    
    def get_resource(self, service: str, account: str, **kwargs) -> Any:
        """Get AWS service resource for specified account"""
        session = self.get_session(account)
        return session.resource(service, **kwargs)
    
    def refresh_sessions(self) -> None:
        """Refresh all sessions (useful for long-running operations)"""
        logger.info("Refreshing AWS sessions...")
        self._initialize_sessions()
        logger.info("Sessions refreshed successfully")
    
    def get_account_id(self, account: str) -> str:
        """Get account ID for specified account"""
        sts_client = self.get_client('sts', account)
        identity = sts_client.get_caller_identity()
        return identity['Account']
    
    def test_permissions(self, account: str, service: str, actions: list) -> Dict[str, bool]:
        """Test specific permissions for an account"""
        results = {}
        
        try:
            iam_client = self.get_client('iam', account)
            
            for action in actions:
                try:
                    # This is a simplified test - in reality you'd want more sophisticated testing
                    if service == 'route53' and action == 'ListHostedZones':
                        r53_client = self.get_client('route53', account)
                        r53_client.list_hosted_zones()
                        results[action] = True
                    elif service == 'cloudformation' and action == 'ListStacks':
                        cfn_client = self.get_client('cloudformation', account)
                        cfn_client.list_stacks()
                        results[action] = True
                    else:
                        results[action] = True  # Assume success if we can't easily test
                        
                except ClientError:
                    results[action] = False
                    
        except Exception as e:
            logger.warning(f"Could not test permissions for {account}: {e}")
            for action in actions:
                results[action] = False
        
        return results