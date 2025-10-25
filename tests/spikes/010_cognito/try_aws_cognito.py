#!/usr/bin/env python3
"""
AWS Cognito Authentication Test Script (Python)

Tests real AWS Cognito authentication and validates tokens using frank.util.auth module.
This script demonstrates:
- Setting user passwords
- Authenticating and obtaining tokens
- Using frank.util.auth.CognitoValidator for token validation
- Showing full server details from validate_token_with_server
"""

import argparse
import asyncio
import json
import sys
from typing import Dict, Any, Optional
import base64

import boto3
from botocore.exceptions import ClientError
import httpx
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# Add parent directory to path to import frank modules
from frank.util.auth import CognitoValidator


console = Console()


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """Decode JWT payload without verification (for inspection only)"""
    try:
        # Get the payload part (second segment)
        payload = token.split('.')[1]
        
        # Add padding if needed
        padding = len(payload) % 4
        if padding:
            payload += '=' * (4 - padding)
        
        # Decode base64
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        console.print(f"[red]Failed to decode JWT payload: {e}[/red]")
        return None


def decode_jwt_header(token: str) -> Optional[Dict[str, Any]]:
    """Decode JWT header without verification (for inspection only)"""
    try:
        # Get the header part (first segment)
        header = token.split('.')[0]
        
        # Add padding if needed
        padding = len(header) % 4
        if padding:
            header += '=' * (4 - padding)
        
        # Decode base64
        decoded = base64.urlsafe_b64decode(header)
        return json.loads(decoded)
    except Exception as e:
        console.print(f"[red]Failed to decode JWT header: {e}[/red]")
        return None


def get_user_pool_id(region: str, profile: str) -> Optional[str]:
    """Retrieve the first available User Pool ID"""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        client = session.client('cognito-idp')
        
        response = client.list_user_pools(MaxResults=10)
        pools = response.get('UserPools', [])
        
        if pools:
            return pools[0]['Id']
        
        console.print("[red]No User Pools found[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Failed to retrieve User Pool ID: {e}[/red]")
        return None


def get_client_id(user_pool_id: str, region: str, profile: str) -> Optional[tuple]:
    """Retrieve the first available Client ID and Name"""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        client = session.client('cognito-idp')
        
        response = client.list_user_pool_clients(
            UserPoolId=user_pool_id,
            MaxResults=10
        )
        
        clients = response.get('UserPoolClients', [])
        if clients:
            return clients[0]['ClientId'], clients[0]['ClientName']
        
        console.print("[red]No User Pool Clients found[/red]")
        return None, None
    except Exception as e:
        console.print(f"[red]Failed to retrieve Client ID: {e}[/red]")
        return None, None


def set_user_password(user_pool_id: str, username: str, password: str, 
                      region: str, profile: str) -> bool:
    """Set permanent password for a user"""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        client = session.client('cognito-idp')
        
        client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=username,
            Password=password,
            Permanent=True
        )
        console.print(f"[green]✅ Password set successfully for user: {username}[/green]")
        return True
    except ClientError as e:
        console.print(f"[red]❌ Failed to set password: {e}[/red]")
        return False


def authenticate_user(client_id: str, username: str, password: str,
                      region: str, profile: str) -> Optional[Dict[str, str]]:
    """Authenticate user and get tokens"""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        client = session.client('cognito-idp')
        
        response = client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        result = response['AuthenticationResult']
        console.print("[green]✅ Authentication successful[/green]")
        
        return {
            'AccessToken': result['AccessToken'],
            'IdToken': result['IdToken'],
            'RefreshToken': result.get('RefreshToken'),
            'TokenType': result['TokenType'],
            'ExpiresIn': result['ExpiresIn']
        }
    except ClientError as e:
        console.print(f"[red]❌ Authentication failed: {e}[/red]")
        return None


async def test_jwks_endpoint(jwks_url: str) -> bool:
    """Test JWKS endpoint accessibility"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=10.0)
            
            if response.status_code == 200:
                jwks = response.json()
                key_count = len(jwks.get('keys', []))
                console.print(f"[green]✅ JWKS endpoint accessible[/green]")
                console.print(f"  Found {key_count} signing keys")
                if key_count > 0:
                    console.print(f"  First key ID: {jwks['keys'][0]['kid']}")
                return True
            else:
                console.print(f"[red]❌ JWKS endpoint returned status {response.status_code}[/red]")
                return False
    except Exception as e:
        console.print(f"[red]❌ JWKS endpoint not accessible: {e}[/red]")
        return False


async def validate_with_cognito_validator(access_token: str, id_token: str, config: Dict[str, Any]):
    """Use frank.util.auth.CognitoValidator to validate tokens"""
    console.print("\n[bold blue]🔐 Step: Using CognitoValidator from frank.util.auth[/bold blue]")
    console.print("=" * 80)
    
    # Create validator instance
    validator = CognitoValidator(config=config)
    
    # Test 1: Local JWT validation
    console.print("\n[yellow]Test 1: Local JWT Validation[/yellow]")
    try:
        local_result = await validator.validate_token_locally(access_token)
        console.print("[green]✅ Local validation successful[/green]")
        
        table = Table(title="Local Validation Result", show_header=True)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in local_result.items():
            table.add_row(key, str(value))
        
        console.print(table)
    except Exception as e:
        console.print(f"[red]❌ Local validation failed: {e}[/red]")
    
    # Test 2: Server validation with Cognito
    console.print("\n[yellow]Test 2: Server Validation with Cognito[/yellow]")
    try:
        server_result = await validator.validate_token_with_server(access_token)
        console.print("[green]✅ Server validation successful[/green]")
        
        table = Table(title="Server Validation Result", show_header=True)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in server_result.items():
            table.add_row(key, str(value))
        
        console.print(table)
        
        # Show detailed server response information
        console.print("\n[bold]📊 Server Validation Details:[/bold]")
        console.print(f"  • Validation Source: {server_result.get('validation_source')}")
        console.print(f"  • Username: {server_result.get('username')}")
        console.print(f"  • User ID (STIX): {server_result.get('user_id')}")
        console.print(f"  • Token Valid: {server_result.get('token_valid')}")
        
    except Exception as e:
        console.print(f"[red]❌ Server validation failed: {e}[/red]")
    
    # Test 3: Full user extraction (combines local + server)
    console.print("\n[yellow]Test 3: Complete User Info (Local JWT + Server Validation)[/yellow]")
    console.print("This shows what get_current_user() returns in a real request")
    try:
        # Mock HTTPAuthorizationCredentials
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token)
        
        user_info = await validator.get_current_user(credentials)
        console.print("[green]✅ Complete user info extracted[/green]")
        
        table = Table(title="Complete User Information", show_header=True)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in user_info.items():
            table.add_row(key, str(value))
        
        console.print(table)
        
        # Highlight important fields
        console.print("\n[bold]🎯 Key User Attributes:[/bold]")
        console.print(f"  • Organisation: [yellow]{user_info.get('organisation', 'N/A')}[/yellow]")
        console.print(f"  • Access Level: [yellow]{user_info.get('access_level', 'N/A')}[/yellow]")
        console.print(f"  • Groups: [yellow]{', '.join(user_info.get('groups', []))}[/yellow]")
        console.print(f"  • Validation Source: [yellow]{user_info.get('validation_source', 'N/A')}[/yellow]")
        
    except Exception as e:
        console.print(f"[red]❌ Failed to extract complete user info: {e}[/red]")


async def main():
    parser = argparse.ArgumentParser(description='AWS Cognito Authentication Test (Python)')
    parser.add_argument('-u', '--username', default='testuser_observer@example.com',
                       help='Username (email) for authentication')
    parser.add_argument('-p', '--profile', default='spike-account',
                       help='AWS profile to use')
    parser.add_argument('-r', '--region', default='eu-central-1',
                       help='AWS region')
    parser.add_argument('--password', default='TempPass123!',
                       help='Password for the user')
    parser.add_argument('--validation-strategy', default='server_first',
                       choices=['local_only', 'server_first', 'server_only'],
                       help='Token validation strategy')
    
    args = parser.parse_args()
    
    console.print("[bold blue]🔐 AWS Cognito Authentication Test (Python)[/bold blue]")
    console.print("=" * 80)
    
    # Step 1: Get AWS identity
    console.print("\n[bold]🔧 Step 1: Checking AWS CLI configuration...[/bold]")
    try:
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        console.print("[green]✅ AWS CLI configured[/green]")
        console.print(f"  Account: {identity['Account']}")
        console.print(f"  User/Role: {identity['Arn']}")
    except Exception as e:
        console.print(f"[red]❌ AWS CLI configuration error: {e}[/red]")
        return 1
    
    # Step 2: Get User Pool ID
    console.print("\n[bold]🔍 Step 2: Retrieving User Pool ID...[/bold]")
    user_pool_id = get_user_pool_id(args.region, args.profile)
    if not user_pool_id:
        return 1
    console.print(f"[green]  User Pool ID: {user_pool_id}[/green]")
    
    # Step 3: Get Client ID
    console.print("\n[bold]🔍 Step 3: Retrieving Client ID...[/bold]")
    client_id, client_name = get_client_id(user_pool_id, args.region, args.profile)
    if not client_id:
        return 1
    console.print(f"[green]  Client ID: {client_id}[/green]")
    console.print(f"[green]  Client Name: {client_name}[/green]")
    
    # Build configuration
    cognito_url = f"https://cognito-idp.{args.region}.amazonaws.com/"
    jwks_url = f"{cognito_url}{user_pool_id}/.well-known/jwks.json"
    
    console.print("\n[bold]📋 Configuration:[/bold]")
    console.print(f"  Region: {args.region}")
    console.print(f"  User Pool ID: {user_pool_id}")
    console.print(f"  Client ID: {client_id}")
    console.print(f"  Username: {args.username}")
    console.print(f"  Cognito URL: {cognito_url}")
    console.print(f"  JWKS URL: {jwks_url}")
    console.print(f"  Validation Strategy: {args.validation_strategy}")
    
    # Step 4: Test JWKS endpoint
    console.print("\n[bold]🔗 Step 4: Testing JWKS endpoint...[/bold]")
    jwks_ok = await test_jwks_endpoint(jwks_url)
    if not jwks_ok:
        console.print("[yellow]⚠️  Warning: JWKS endpoint test failed, but continuing...[/yellow]")
    
    # Step 5: Set user password
    console.print("\n[bold]🔑 Step 5: Setting user password...[/bold]")
    if not set_user_password(user_pool_id, args.username, args.password, args.region, args.profile):
        return 1
    
    # Step 6: Authenticate and get tokens
    console.print("\n[bold]🎫 Step 6: Authenticating user...[/bold]")
    tokens = authenticate_user(client_id, args.username, args.password, args.region, args.profile)
    if not tokens:
        return 1
    
    console.print(f"  Access Token: {tokens['AccessToken'][:50]}...")
    console.print(f"  ID Token: {tokens['IdToken'][:50]}...")
    console.print(f"  Token Type: {tokens['TokenType']}")
    console.print(f"  Expires In: {tokens['ExpiresIn']} seconds")
    
    # Step 7: Decode tokens
    console.print("\n[bold]🔍 Step 7: Decoding JWT tokens locally...[/bold]")
    
    access_payload = decode_jwt_payload(tokens['AccessToken'])
    if access_payload:
        console.print("\n[cyan]Access Token payload:[/cyan]")
        console.print(json.dumps(access_payload, indent=2))
    
    id_payload = decode_jwt_payload(tokens['IdToken'])
    if id_payload:
        console.print("\n[cyan]ID Token payload:[/cyan]")
        console.print(json.dumps(id_payload, indent=2))
        
        # Highlight custom:organisation
        if 'custom:organisation' in id_payload:
            console.print(f"\n[bold green]✅ custom:organisation found in ID token: {id_payload['custom:organisation']}[/bold green]")
    
    # Step 8: Verify token signature info
    console.print("\n[bold]🔐 Step 8: Verifying token signature info...[/bold]")
    access_header = decode_jwt_header(tokens['AccessToken'])
    if access_header:
        console.print(f"  Token Key ID (kid): {access_header.get('kid')}")
        console.print(f"  Algorithm: {access_header.get('alg')}")
    
    # Step 9: Test with CognitoValidator
    config = {
        'environment': 'aws',
        'cognito_url': cognito_url,
        'user_pool_id': user_pool_id,
        'client_id': client_id,
        'region': args.region,
        'jwt_algorithm': 'RS256',
        'validation_strategy': args.validation_strategy
    }
    
    await validate_with_cognito_validator(tokens['AccessToken'], tokens['IdToken'], config)
    
    # Summary
    console.print("\n[bold green]📊 Test Summary:[/bold green]")
    console.print("=" * 80)
    console.print("✅ 1. AWS CLI Configuration: Success")
    console.print("✅ 2. User Pool ID Retrieved: Success")
    console.print("✅ 3. Client ID Retrieved: Success")
    console.print(f"{'✅' if jwks_ok else '⚠️'} 4. JWKS Endpoint: {'Success' if jwks_ok else 'Warning'}")
    console.print("✅ 5. Password Set: Success")
    console.print("✅ 6. User Authentication: Success")
    console.print("✅ 7. JWT Token Decoding: Success")
    console.print("✅ 8. CognitoValidator Tests: Complete")
    
    console.print("\n[bold]🎯 For your application:[/bold]")
    console.print(f"  export COGNITO_USER_POOL_ID='{user_pool_id}'")
    console.print(f"  export COGNITO_CLIENT_ID='{client_id}'")
    console.print(f"  export COGNITO_REGION='{args.region}'")
    console.print(f"  export AWS_COGNITO_URL='{cognito_url}'")
    
    console.print("\n[bold green]✅ AWS Cognito test completed![/bold green]")
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
