#!/bin/bash
# FRANK Platform - Get Cognito User Pool and App Client IDs
# Usage: ./get-cognito-ids.sh

PROFILE="spike-account"
REGION="eu-central-1"

echo "🔍 Finding Cognito User Pools with profile: $PROFILE in region: $REGION..."

# Check if AWS CLI is configured with the profile
if ! aws sts get-caller-identity --profile $PROFILE --region $REGION > /dev/null 2>&1; then
  echo "❌ Error: Cannot access AWS with profile '$PROFILE'"
  echo "   Make sure you have configured the profile with: aws configure --profile $PROFILE"
  exit 1
fi

echo "✅ AWS CLI access confirmed"

USER_POOLS=$(aws cognito-idp list-user-pools --max-results 60 --profile $PROFILE --region $REGION --output json 2>/dev/null)

if [ $? -ne 0 ]; then
  echo "❌ Error: Cannot list User Pools. Check your permissions."
  exit 1
fi

echo "📋 Available User Pools:"
echo "$USER_POOLS" | jq -r '.UserPools[] | "\(.Id) - \(.Name)"'

echo -e "\n🎯 Looking for pools containing 'frank', 'FRANK', or 'spike':"
FRANK_POOLS=$(echo "$USER_POOLS" | jq -r '.UserPools[] | select(.Name | test("frank|FRANK|spike|010"; "i")) | "\(.Id) - \(.Name)"')

if [ -n "$FRANK_POOLS" ]; then
  echo "$FRANK_POOLS"
  
  # Get the first matching pool ID
  POOL_ID=$(echo "$USER_POOLS" | jq -r '.UserPools[] | select(.Name | test("frank|FRANK|spike|010"; "i")) | .Id' | head -1)
  
  if [ -n "$POOL_ID" ]; then
    echo -e "\n🔧 Getting App Clients for User Pool: $POOL_ID"
    APP_CLIENTS=$(aws cognito-idp list-user-pool-clients --user-pool-id $POOL_ID --profile $PROFILE --region $REGION --output json 2>/dev/null)
    
    if [ $? -eq 0 ]; then
      echo "📱 App Clients:"
      echo "$APP_CLIENTS" | jq -r '.UserPoolClients[] | "\(.ClientId) - \(.ClientName)"'
      
      # Export commands
      echo -e "\n📋 Environment Variables to set:"
      echo "export USER_POOL_ID=$POOL_ID"
      
      CLIENT_ID=$(echo "$APP_CLIENTS" | jq -r '.UserPoolClients[0].ClientId')
      if [ -n "$CLIENT_ID" ] && [ "$CLIENT_ID" != "null" ]; then
        echo "export APP_CLIENT_ID=$CLIENT_ID"
      else
        echo "⚠️  No App Client found for this User Pool"
      fi
      
      echo "export AWS_REGION=$REGION"
      echo "export USE_AWS_COGNITO=true"
      
      echo -e "\n🚀 To use with the unified API:"
      echo "export USER_POOL_ID=$POOL_ID"
      echo "export APP_CLIENT_ID=${CLIENT_ID:-YOUR_CLIENT_ID}"
      echo "export AWS_REGION=$REGION"
      echo "export USE_AWS_COGNITO=true"
      echo "python simple_api_unified.py"
      
    else
      echo "❌ Error: Cannot list App Clients for User Pool $POOL_ID"
    fi
  fi
else
  echo "❌ No User Pools found matching 'frank', 'spike', or '010'"
  echo -e "\n📋 All available pools:"
  echo "$USER_POOLS" | jq -r '.UserPools[] | "\(.Id) - \(.Name)"'
  echo -e "\nℹ️  If you need to use a specific pool, run:"
  echo "aws cognito-idp list-user-pool-clients --user-pool-id YOUR_POOL_ID --profile $PROFILE --region $REGION"
fi

echo -e "\n✅ Script completed"