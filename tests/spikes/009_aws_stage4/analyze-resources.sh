#!/bin/bash

# analyze-resources.sh
# Analyzes CloudFormation template to categorize resources for change set management

set -euo pipefail

TEMPLATE_FILE="${1:-templates/frank-009-stage4-infra.yaml}"
STACK_NAME="${2:-frank-009-stage4}"
AWS_REGION="${3:-us-east-1}"
AWS_PROFILE="${4:-default}"

echo "🔍 Analyzing CloudFormation Resources for Change Set Management"
echo "=============================================================="
echo "Template: $TEMPLATE_FILE"
echo "Stack: $STACK_NAME"
echo "Region: $AWS_REGION"
echo "Profile: $AWS_PROFILE"
echo

# Extract all resources from the template
RESOURCES=$(yq eval '.Resources | keys' "$TEMPLATE_FILE" | grep -v "^---$" | sed 's/^- //')

echo "📊 Resource Analysis Summary"
echo "============================"

# Count total resources
TOTAL_RESOURCES=$(echo "$RESOURCES" | wc -l | tr -d ' ')
echo "Total Resources: $TOTAL_RESOURCES"
echo

# Tier 1: Critical resources that commonly exist independently
echo "🔴 Tier 1: Critical Resources (High CREATE_FAILED Risk)"
echo "======================================================="
TIER1_RESOURCES=(
    "VPC"
    "DynamoDBTable" 
    "DynamoDBAuditTable"
    "ECSCluster"
    "LogGroup"
)

TIER1_FOUND=0
for resource in "${TIER1_RESOURCES[@]}"; do
    if echo "$RESOURCES" | grep -q "^$resource$"; then
        echo "✓ $resource"
        TIER1_FOUND=$((TIER1_FOUND + 1))
    fi
done
echo "Tier 1 Resources Found: $TIER1_FOUND/${#TIER1_RESOURCES[@]}"
echo

# Tier 2: Expensive resources
echo "🟡 Tier 2: Expensive Resources (Cost Impact)"
echo "============================================"
TIER2_RESOURCES=(
    "NATGateway1"
    "NATGateway2" 
    "NATGateway3"
    "NATGatewayEIP1"
    "NATGatewayEIP2"
    "NATGatewayEIP3"
    "ApplicationLoadBalancer"
)

TIER2_FOUND=0
for resource in "${TIER2_RESOURCES[@]}"; do
    if echo "$RESOURCES" | grep -q "^$resource$"; then
        echo "✓ $resource"
        TIER2_FOUND=$((TIER2_FOUND + 1))
    fi
done
echo "Tier 2 Resources Found: $TIER2_FOUND/${#TIER2_RESOURCES[@]}"
echo

# Tier 3: Typically safe resources
echo "🟢 Tier 3: Typically Safe Resources (Low Conflict Risk)"
echo "======================================================="
TIER3_COUNT=$((TOTAL_RESOURCES - TIER1_FOUND - TIER2_FOUND))
echo "Tier 3 Resources: $TIER3_COUNT (Subnets, Routes, Security Groups, etc.)"
echo

# Check if resources actually exist in AWS
echo "🔍 Checking for Existing Resources in AWS"
echo "=========================================="

check_dynamodb_table() {
    local table_name="$1"
    if aws dynamodb describe-table --table-name "$table_name" --region "$AWS_REGION" --profile "$AWS_PROFILE" >/dev/null 2>&1; then
        echo "🔴 FOUND: DynamoDB table '$table_name' already exists"
        return 0
    else
        echo "✅ OK: DynamoDB table '$table_name' does not exist"
        return 1
    fi
}

check_ecs_cluster() {
    local cluster_name="$1"
    if aws ecs describe-clusters --clusters "$cluster_name" --region "$AWS_REGION" --profile "$AWS_PROFILE" --query 'clusters[0].clusterName' --output text 2>/dev/null | grep -q "$cluster_name"; then
        echo "🔴 FOUND: ECS cluster '$cluster_name' already exists"
        return 0
    else
        echo "✅ OK: ECS cluster '$cluster_name' does not exist"
        return 1
    fi
}

check_log_group() {
    local log_group_name="$1"
    if aws logs describe-log-groups --log-group-name-prefix "$log_group_name" --region "$AWS_REGION" --profile "$AWS_PROFILE" --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$log_group_name"; then
        echo "🔴 FOUND: CloudWatch log group '$log_group_name' already exists"
        return 0
    else
        echo "✅ OK: CloudWatch log group '$log_group_name' does not exist"
        return 1
    fi
}

check_vpc() {
    local vpc_tag_name="$1"
    if aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$vpc_tag_name" --region "$AWS_REGION" --profile "$AWS_PROFILE" --query 'Vpcs[0].VpcId' --output text 2>/dev/null | grep -q "vpc-"; then
        echo "🔴 FOUND: VPC with tag Name='$vpc_tag_name' already exists"
        return 0
    else
        echo "✅ OK: VPC with tag Name='$vpc_tag_name' does not exist"
        return 1
    fi
}

# Check each critical resource
EXISTING_RESOURCES=0

echo "Checking DynamoDB Tables..."
if check_dynamodb_table "${STACK_NAME}-data"; then
    EXISTING_RESOURCES=$((EXISTING_RESOURCES + 1))
fi

if check_dynamodb_table "${STACK_NAME}-audit"; then
    EXISTING_RESOURCES=$((EXISTING_RESOURCES + 1))
fi

echo
echo "Checking ECS Cluster..."
if check_ecs_cluster "${STACK_NAME}-cluster"; then
    EXISTING_RESOURCES=$((EXISTING_RESOURCES + 1))
fi

echo
echo "Checking CloudWatch Log Group..."
if check_log_group "/ecs/${STACK_NAME}"; then
    EXISTING_RESOURCES=$((EXISTING_RESOURCES + 1))
fi

echo
echo "Checking VPC..."
if check_vpc "${STACK_NAME}-vpc"; then
    EXISTING_RESOURCES=$((EXISTING_RESOURCES + 1))
fi

echo
echo "📋 Recommendation Summary"
echo "========================"

if [ $EXISTING_RESOURCES -eq 0 ]; then
    echo "✅ No existing critical resources found. Safe to deploy normally."
    echo "   Recommended action: Standard CloudFormation deployment"
else
    echo "⚠️  Found $EXISTING_RESOURCES existing critical resource(s)."
    echo "   Recommended actions:"
    echo "   1. Use CloudFormation change sets for review"
    echo "   2. Consider resource import for DynamoDB tables" 
    echo "   3. Use stack policies to prevent accidental deletions"
    echo "   4. Enable backup before making changes"
fi

echo
echo "🎯 Resource Check Priority"
echo "========================="
echo "Essential checks (do these first): $TIER1_FOUND resources"
echo "Cost-impact checks: $TIER2_FOUND resources" 
echo "Optional checks: $TIER3_COUNT resources"
echo
echo "Total resources requiring management: $((TIER1_FOUND + TIER2_FOUND)) out of $TOTAL_RESOURCES"

# Generate commands for manual resource import if needed
if [ $EXISTING_RESOURCES -gt 0 ]; then
    echo
    echo "🔧 Manual Resource Import Commands"
    echo "=================================="
    
    echo "# Create resources-to-import.json:"
    echo "cat > resources-to-import.json << 'EOF'"
    echo "["
    
    FIRST_ITEM=true
    if check_dynamodb_table "${STACK_NAME}-data" >/dev/null 2>&1; then
        if [ "$FIRST_ITEM" = false ]; then echo ","; fi
        echo "  {"
        echo "    \"ResourceType\": \"AWS::DynamoDB::Table\","
        echo "    \"LogicalResourceId\": \"DynamoDBTable\","
        echo "    \"ResourceIdentifier\": {"
        echo "      \"TableName\": \"${STACK_NAME}-data\""
        echo "    }"
        echo "  }"
        FIRST_ITEM=false
    fi
    
    if check_dynamodb_table "${STACK_NAME}-audit" >/dev/null 2>&1; then
        if [ "$FIRST_ITEM" = false ]; then echo ","; fi
        echo "  {"
        echo "    \"ResourceType\": \"AWS::DynamoDB::Table\","
        echo "    \"LogicalResourceId\": \"DynamoDBAuditTable\","
        echo "    \"ResourceIdentifier\": {"
        echo "      \"TableName\": \"${STACK_NAME}-audit\""
        echo "    }"
        echo "  }"
        FIRST_ITEM=false
    fi
    
    echo "]"
    echo "EOF"
    echo
    echo "# Create import change set:"
    echo "aws cloudformation create-change-set \\"
    echo "  --stack-name $STACK_NAME \\"
    echo "  --template-body file://$TEMPLATE_FILE \\"
    echo "  --change-set-name ${STACK_NAME}-import-$(date +%s) \\"
    echo "  --change-set-type IMPORT \\"
    echo "  --resources-to-import file://resources-to-import.json \\"
    echo "  --capabilities CAPABILITY_IAM \\"
    echo "  --region $AWS_REGION \\"
    echo "  --profile $AWS_PROFILE"
fi