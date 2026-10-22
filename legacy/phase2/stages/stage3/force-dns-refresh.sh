#!/bin/bash

# force-dns-refresh.sh - Force refresh of DNS record

set -euo pipefail

STACK_NAME="${1:-frank-stage3}"
DOMAIN="${2:-frank-stage3.lab271.io}"
AWS_REGION="${3:-eu-central-1}"
AWS_PROFILE="${4:-spike-account}"

echo "🔧 Force refreshing DNS record for $DOMAIN"
echo "==========================================="

# Get the hosted zone ID
HOSTED_ZONE_ID="Z00346102V3OPWCVJPSR8"

# Get ALB details
ALB_DNS="frank-stage3-alb-851737434.eu-central-1.elb.amazonaws.com"
ALB_ZONE_ID="Z215JYRZR1TBD5"

echo "ALB DNS: $ALB_DNS"
echo "ALB Zone ID: $ALB_ZONE_ID"
echo "Domain Hosted Zone ID: $HOSTED_ZONE_ID"

# First, delete any existing A record
echo "Deleting existing A record..."
aws route53 change-resource-record-sets \
    --hosted-zone-id "$HOSTED_ZONE_ID" \
    --change-batch "{
        \"Changes\": [{
            \"Action\": \"DELETE\",
            \"ResourceRecordSet\": {
                \"Name\": \"$DOMAIN\",
                \"Type\": \"A\",
                \"AliasTarget\": {
                    \"DNSName\": \"$ALB_DNS\",
                    \"HostedZoneId\": \"$ALB_ZONE_ID\",
                    \"EvaluateTargetHealth\": false
                }
            }
        }]
    }" \
    --profile "$AWS_PROFILE" || echo "No existing record to delete"

echo "Waiting 10 seconds..."
sleep 10

# Create the new A record
echo "Creating fresh DNS A record..."
aws route53 change-resource-record-sets \
    --hosted-zone-id "$HOSTED_ZONE_ID" \
    --change-batch "{
        \"Changes\": [{
            \"Action\": \"CREATE\",
            \"ResourceRecordSet\": {
                \"Name\": \"$DOMAIN\",
                \"Type\": \"A\",
                \"AliasTarget\": {
                    \"DNSName\": \"$ALB_DNS\",
                    \"HostedZoneId\": \"$ALB_ZONE_ID\",
                    \"EvaluateTargetHealth\": false
                }
            }
        }]
    }" \
    --profile "$AWS_PROFILE"

echo "✅ DNS record refreshed successfully!"
echo "🕐 Wait 2-3 minutes for DNS propagation, then test:"
echo "curl -v https://$DOMAIN"
echo
echo "You can also test the ALB directly:"
echo "curl -s -k https://$ALB_DNS/v1/health"