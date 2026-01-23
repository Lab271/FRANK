#!/bin/bash
# Fix trust policy for existing FRANK security roles
# This script updates the trust policy to use the correct account ID

set -e

PROFILE="spike-account"
ACCOUNT_ID="350012230634"  # Your actual account ID
EXTERNAL_ID="frank-deployment-access"

echo "🔧 Fixing trust policies for FRANK security roles"
echo "Account ID: ${ACCOUNT_ID}"
echo "Profile: ${PROFILE}"
echo "=========================================="

# Create corrected trust policy
cat > /tmp/corrected-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${ACCOUNT_ID}:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "${EXTERNAL_ID}"
        },
        "Bool": {
          "aws:MultiFactorAuthPresent": "true"
        },
        "NumericLessThan": {
          "aws:MultiFactorAuthAge": "3600"
        }
      }
    }
  ]
}
EOF

# List of roles to update
ROLES=(
    "frank-infra-creator"
    "frank-infra-destroyer"
    "frank-app-deployer"
    "frank-data-reader"
    "frank-emergency-admin"
)

# Update trust policy for each role
for role in "${ROLES[@]}"; do
    echo "🔄 Updating trust policy for role: ${role}"
    
    # Check if role exists
    if aws iam get-role --role-name ${role} --profile ${PROFILE} >/dev/null 2>&1; then
        # Update the assume role policy
        aws iam update-assume-role-policy \
            --profile ${PROFILE} \
            --role-name ${role} \
            --policy-document file:///tmp/corrected-trust-policy.json
        echo "✅ Updated ${role}"
    else
        echo "❌ Role ${role} does not exist, skipping"
    fi
done

# Clean up
rm /tmp/corrected-trust-policy.json

echo ""
echo "✅ Trust policy fix complete!"
echo ""
echo "🧪 Test role assumption:"
echo "aws sts assume-role \\"
echo "    --role-arn arn:aws:iam::${ACCOUNT_ID}:role/frank-data-reader \\"
echo "    --role-session-name test-session \\"
echo "    --external-id ${EXTERNAL_ID} \\"
echo "    --profile ${PROFILE}"
echo ""
echo "📋 Update your ~/.aws/config with:"
echo ""
echo "[profile frank-deploy]"
echo "role_arn = arn:aws:iam::${ACCOUNT_ID}:role/frank-app-deployer"
echo "source_profile = ${PROFILE}"
echo "external_id = ${EXTERNAL_ID}"
echo "duration_seconds = 14400"
echo "region = eu-central-1"