#!/bin/bash

# Configuration variables
AWS_PROFILE="spike-account"
AWS_REGION="eu-central-1"
STACK_NAME="frank-009-stage4"
APP_NAME="simple_api"
REPOSITORY_NAME=${STACK_NAME}
PLATFORM="linux/amd64"

# DNS and SSL Configuration
MAIN_DOMAIN="lab271.io"
SPIKE_SUBDOMAIN="${STACK_NAME}.lab271.io"
MAIN_ACCOUNT_PROFILE="main-account"  # Change this to your main account profile name

DOCKER_BUILDKIT=1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if jq is installed (for JSON parsing)
    if ! command -v jq &> /dev/null; then
        log_warning "jq is not installed. Some features may not work. Install with: brew install jq"
    fi
  
    # Check AWS credentials for spike account
    if ! aws sts get-caller-identity --profile ${AWS_PROFILE} &> /dev/null; then
        log_error "AWS credentials not configured for ${AWS_PROFILE}. Please run 'aws configure --profile ${AWS_PROFILE}'."
        exit 1
    fi
    
    # Check AWS credentials for main account (optional for SSL setup)
    if ! aws sts get-caller-identity --profile ${MAIN_ACCOUNT_PROFILE} &> /dev/null 2>&1; then
        log_warning "Main account profile '${MAIN_ACCOUNT_PROFILE}' not configured. SSL setup will be skipped."
        log_warning "To enable SSL setup, configure with: aws configure --profile ${MAIN_ACCOUNT_PROFILE}"
    fi
    
    log_success "All prerequisites are met."
}

setup_ssl() {
    log_info "=== Setting up SSL Certificate and DNS ==="
    
    # Check if main account profile is configured
    if ! aws sts get-caller-identity --profile ${MAIN_ACCOUNT_PROFILE} &> /dev/null 2>&1; then
        log_warning "Main account not configured. Skipping SSL setup."
        log_info "To set up SSL manually, see: main-account-ssl-setup.md"
        return 1
    fi
    
    # Step 1: Check/Create Main Hosted Zone
    log_info "Step 1: Checking main hosted zone for ${MAIN_DOMAIN}..."
    MAIN_HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
        --dns-name ${MAIN_DOMAIN} \
        --profile ${MAIN_ACCOUNT_PROFILE} \
        --query "HostedZones[?Name=='${MAIN_DOMAIN}.'].Id" \
        --output text | cut -d'/' -f3)
    
    if [ -z "$MAIN_HOSTED_ZONE_ID" ]; then
        log_info "Creating hosted zone for ${MAIN_DOMAIN}..."
        MAIN_HOSTED_ZONE_ID=$(aws route53 create-hosted-zone \
            --name ${MAIN_DOMAIN} \
            --caller-reference "lab271-$(date +%s)" \
            --profile ${MAIN_ACCOUNT_PROFILE} \
            --query 'HostedZone.Id' \
            --output text | cut -d'/' -f3)
        log_success "Main hosted zone created: ${MAIN_HOSTED_ZONE_ID}"
        
        # Display nameservers
        log_info "Update your domain registrar with these nameservers:"
        aws route53 get-hosted-zone \
            --id ${MAIN_HOSTED_ZONE_ID} \
            --profile ${MAIN_ACCOUNT_PROFILE} \
            --query 'DelegationSet.NameServers' \
            --output table
    else
        log_success "Main hosted zone already exists: ${MAIN_HOSTED_ZONE_ID}"
    fi
    
    # Step 2: Check/Request Main Certificate
    log_info "Step 2: Checking SSL certificate for ${MAIN_DOMAIN}..."
    MAIN_CERT_ARN=$(aws acm list-certificates \
        --region us-east-1 \
        --profile ${MAIN_ACCOUNT_PROFILE} \
        --query "CertificateSummaryList[?DomainName=='${MAIN_DOMAIN}'].CertificateArn" \
        --output text | head -1)
    
    if [ -z "$MAIN_CERT_ARN" ]; then
        log_info "Requesting SSL certificate for ${MAIN_DOMAIN} and *.${MAIN_DOMAIN}..."
        MAIN_CERT_ARN=$(aws acm request-certificate \
            --domain-name ${MAIN_DOMAIN} \
            --subject-alternative-names "*.${MAIN_DOMAIN}" \
            --validation-method DNS \
            --region us-east-1 \
            --profile ${MAIN_ACCOUNT_PROFILE} \
            --query 'CertificateArn' \
            --output text)
        log_success "Certificate requested: ${MAIN_CERT_ARN}"
        
        # Add validation record
        sleep 5
        log_info "Adding DNS validation record..."
        
        VALIDATION_NAME=$(aws acm describe-certificate \
            --certificate-arn ${MAIN_CERT_ARN} \
            --region us-east-1 \
            --profile ${MAIN_ACCOUNT_PROFILE} \
            --query 'Certificate.DomainValidationOptions[0].ResourceRecord.Name' \
            --output text)
        
        VALIDATION_VALUE=$(aws acm describe-certificate \
            --certificate-arn ${MAIN_CERT_ARN} \
            --region us-east-1 \
            --profile ${MAIN_ACCOUNT_PROFILE} \
            --query 'Certificate.DomainValidationOptions[0].ResourceRecord.Value' \
            --output text)
        
        cat > /tmp/cert-validation.json <<EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "$VALIDATION_NAME",
      "Type": "CNAME",
      "TTL": 300,
      "ResourceRecords": [{"Value": "$VALIDATION_VALUE"}]
    }
  }]
}
EOF
        
        aws route53 change-resource-record-sets \
            --hosted-zone-id ${MAIN_HOSTED_ZONE_ID} \
            --change-batch file:///tmp/cert-validation.json \
            --profile ${MAIN_ACCOUNT_PROFILE} > /dev/null
        
        log_info "Waiting for certificate validation (this may take several minutes)..."
        if aws acm wait certificate-validated \
            --certificate-arn ${MAIN_CERT_ARN} \
            --region us-east-1 \
            --profile ${MAIN_ACCOUNT_PROFILE}; then
            log_success "Certificate validated!"
        else
            log_warning "Certificate validation timed out. It may still be pending."
        fi
    else
        log_success "Main certificate already exists: ${MAIN_CERT_ARN}"
    fi
    
    # Step 3: Check/Create Spike Hosted Zone
    log_info "Step 3: Checking spike subdomain hosted zone..."
    SPIKE_HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
        --dns-name ${SPIKE_SUBDOMAIN} \
        --profile ${AWS_PROFILE} \
        --query "HostedZones[?Name=='${SPIKE_SUBDOMAIN}.'].Id" \
        --output text | cut -d'/' -f3)
    
    if [ -z "$SPIKE_HOSTED_ZONE_ID" ]; then
        log_info "Creating hosted zone for ${SPIKE_SUBDOMAIN}..."
        SPIKE_HOSTED_ZONE_ID=$(aws route53 create-hosted-zone \
            --name ${SPIKE_SUBDOMAIN} \
            --caller-reference "spike-test-$(date +%s)" \
            --profile ${AWS_PROFILE} \
            --query 'HostedZone.Id' \
            --output text | cut -d'/' -f3)
        log_success "Spike hosted zone created: ${SPIKE_HOSTED_ZONE_ID}"
    else
        log_success "Spike hosted zone already exists: ${SPIKE_HOSTED_ZONE_ID}"
    fi
    
    # Get spike nameservers
    SPIKE_NS=$(aws route53 get-hosted-zone \
        --id ${SPIKE_HOSTED_ZONE_ID} \
        --profile ${AWS_PROFILE} \
        --query 'DelegationSet.NameServers' \
        --output json)
    
    # Step 4: Delegate subdomain from main to spike
    log_info "Step 4: Setting up subdomain delegation..."
    NS1=$(echo $SPIKE_NS | jq -r '.[0]')
    NS2=$(echo $SPIKE_NS | jq -r '.[1]')
    NS3=$(echo $SPIKE_NS | jq -r '.[2]')
    NS4=$(echo $SPIKE_NS | jq -r '.[3]')
    
    cat > /tmp/subdomain-delegation.json <<EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "${SPIKE_SUBDOMAIN}",
      "Type": "NS",
      "TTL": 300,
      "ResourceRecords": [
        {"Value": "$NS1"},
        {"Value": "$NS2"},
        {"Value": "$NS3"},
        {"Value": "$NS4"}
      ]
    }
  }]
}
EOF
    
    aws route53 change-resource-record-sets \
        --hosted-zone-id ${MAIN_HOSTED_ZONE_ID} \
        --change-batch file:///tmp/subdomain-delegation.json \
        --profile ${MAIN_ACCOUNT_PROFILE} > /dev/null
    
    log_success "Subdomain delegation configured"
    
    # Step 5: Request certificate in spike account
    log_info "Step 5: Checking spike certificate..."
    SPIKE_CERT_ARN=$(aws acm list-certificates \
        --region ${AWS_REGION} \
        --profile ${AWS_PROFILE} \
        --query "CertificateSummaryList[?DomainName=='${SPIKE_SUBDOMAIN}'].CertificateArn" \
        --output text | head -1)
    
    if [ -z "$SPIKE_CERT_ARN" ]; then
        log_info "Requesting SSL certificate for ${SPIKE_SUBDOMAIN}..."
        SPIKE_CERT_ARN=$(aws acm request-certificate \
            --domain-name ${SPIKE_SUBDOMAIN} \
            --validation-method DNS \
            --region ${AWS_REGION} \
            --profile ${AWS_PROFILE} \
            --query 'CertificateArn' \
            --output text)
        log_success "Spike certificate requested: ${SPIKE_CERT_ARN}"
        
        sleep 5
        log_info "Adding DNS validation record to spike zone..."
        
        SPIKE_VALIDATION_NAME=$(aws acm describe-certificate \
            --certificate-arn ${SPIKE_CERT_ARN} \
            --region ${AWS_REGION} \
            --profile ${AWS_PROFILE} \
            --query 'Certificate.DomainValidationOptions[0].ResourceRecord.Name' \
            --output text)
        
        SPIKE_VALIDATION_VALUE=$(aws acm describe-certificate \
            --certificate-arn ${SPIKE_CERT_ARN} \
            --region ${AWS_REGION} \
            --profile ${AWS_PROFILE} \
            --query 'Certificate.DomainValidationOptions[0].ResourceRecord.Value' \
            --output text)
        
        cat > /tmp/spike-cert-validation.json <<EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "$SPIKE_VALIDATION_NAME",
      "Type": "CNAME",
      "TTL": 300,
      "ResourceRecords": [{"Value": "$SPIKE_VALIDATION_VALUE"}]
    }
  }]
}
EOF
        
        aws route53 change-resource-record-sets \
            --hosted-zone-id ${SPIKE_HOSTED_ZONE_ID} \
            --change-batch file:///tmp/spike-cert-validation.json \
            --profile ${AWS_PROFILE} > /dev/null
        
        log_info "Waiting for spike certificate validation..."
        if aws acm wait certificate-validated \
            --certificate-arn ${SPIKE_CERT_ARN} \
            --region ${AWS_REGION} \
            --profile ${AWS_PROFILE}; then
            log_success "Spike certificate validated!"
        else
            log_warning "Certificate validation timed out. It may still be pending."
        fi
    else
        log_success "Spike certificate already exists: ${SPIKE_CERT_ARN}"
    fi
    
    # Save values
    cat > /tmp/frank-ssl-values.txt <<EOF
==============================================
FRANK SSL Setup - Important Values
==============================================

MAIN ACCOUNT:
Main Hosted Zone ID: ${MAIN_HOSTED_ZONE_ID}
Main Certificate ARN: ${MAIN_CERT_ARN}

SPIKE ACCOUNT:
Spike Hosted Zone ID: ${SPIKE_HOSTED_ZONE_ID}
Spike Certificate ARN: ${SPIKE_CERT_ARN}
Spike Subdomain: ${SPIKE_SUBDOMAIN}

==============================================
EOF
    
    cat /tmp/frank-ssl-values.txt
    
    # Export for use in CloudFormation
    export SPIKE_CERT_ARN
    export SPIKE_HOSTED_ZONE_ID
}

create() {
    log_info "Starting stack creation process..."

    # 1. Get AWS Account ID dynamically
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile ${AWS_PROFILE} --query Account --output text)
    ECR_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    log_info "Using AWS Account ID: ${AWS_ACCOUNT_ID}"

    # 1.5. Set up SSL/HTTPS (optional)
    log_info "Setting up SSL certificates and DNS..."
    if setup_ssl; then
        log_success "SSL setup completed successfully."
    else
        log_warning "SSL setup failed or was skipped. Deploying without HTTPS."
        unset SPIKE_CERT_ARN
        unset SPIKE_HOSTED_ZONE_ID
    fi

    # 2. First, push your Docker image to ECR
    log_info "Creating ECR repository: ${REPOSITORY_NAME}"
    if aws ecr create-repository --repository-name ${REPOSITORY_NAME} --profile ${AWS_PROFILE} --region ${AWS_REGION} > /dev/null 2>&1; then
        log_success "ECR repository ${REPOSITORY_NAME} created."
    else
        log_warning "ECR repository ${REPOSITORY_NAME} already exists, continuing..."
    fi

    # 3. Build and push Docker image to ECR
    log_info "Building Docker image..."
    if docker buildx build --platform ${PLATFORM} -t ${APP_NAME}:latest . > /dev/null 2>&1; then
        log_success "Docker image built successfully."
    else
        log_error "Failed to build Docker image."
        exit 1
    fi

    log_info "Logging into ECR..."
    aws ecr get-login-password --profile ${AWS_PROFILE} --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URL} > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        log_error "Failed to log into ECR."
        exit 1
    fi
    docker tag ${APP_NAME}:latest ${ECR_URL}/${REPOSITORY_NAME}:latest > /dev/null 2>&1

    log_info "Pushing Docker image to ECR..."
    docker push ${ECR_URL}/${REPOSITORY_NAME}:latest > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        log_success "Docker image pushed to ECR: ${ECR_URL}/${REPOSITORY_NAME}:latest"
    else
        log_error "Failed to push Docker image to ECR."
        exit 1
    fi

    # 4. Deploy CloudFormation stack
    log_info "Creating CloudFormation stack: ${STACK_NAME}"
    
    # Build CloudFormation parameters
    CF_PARAMS="ParameterKey=ContainerImage,ParameterValue=${ECR_URL}/${REPOSITORY_NAME}:latest ParameterKey=StackName,ParameterValue=${STACK_NAME}"
    
    # Add SSL parameters if available
    if [ -n "$SPIKE_CERT_ARN" ]; then
        log_info "Adding SSL certificate to deployment: ${SPIKE_CERT_ARN}"
        CF_PARAMS="${CF_PARAMS} ParameterKey=CertificateArn,ParameterValue=${SPIKE_CERT_ARN}"
        CF_PARAMS="${CF_PARAMS} ParameterKey=DomainName,ParameterValue=${SPIKE_SUBDOMAIN}"
        CF_PARAMS="${CF_PARAMS} ParameterKey=HostedZoneId,ParameterValue=${SPIKE_HOSTED_ZONE_ID}"
    else
        log_info "No SSL certificate found. Deploying HTTP-only."
    fi
    
    # Capture CloudFormation error output
    CF_OUTPUT=$(aws cloudformation create-stack \
        --stack-name ${STACK_NAME} \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} \
        --template-body file://ansible/templates/${STACK_NAME}-infra.yaml \
        --parameters ${CF_PARAMS} \
        --capabilities CAPABILITY_IAM 2>&1)
    
    if [ $? -eq 0 ]; then
        log_success "CloudFormation stack ${STACK_NAME} creation initiated."
    else
        # Check if it's a ValidationError
        if echo "$CF_OUTPUT" | grep -q "ValidationError"; then
            log_error "CloudFormation template validation failed:"
            echo "$CF_OUTPUT" | grep -A 5 -B 5 "ValidationError"
            exit 1
        elif echo "$CF_OUTPUT" | grep -q "AlreadyExistsException"; then
            log_warning "CloudFormation stack ${STACK_NAME} already exists."
        else
            log_error "Failed to create CloudFormation stack:"
            echo "$CF_OUTPUT"
            log_info "You can check the stack status with: aws cloudformation describe-stacks --stack-name ${STACK_NAME} --profile ${AWS_PROFILE} --region ${AWS_REGION}"
            exit 1
        fi
    fi

    # 5. Wait for stack creation
    log_info "Waiting for stack creation to complete..."
    aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME} --profile ${AWS_PROFILE} --region ${AWS_REGION}

    # 6. Get the ALB URL from CloudFormation outputs
    log_info "Getting Application Load Balancer URL..."
    ALB_URL=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} \
        --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
        --output text)
    
    if [ "$ALB_URL" != "None" ] && [ -n "$ALB_URL" ]; then
        log_success "Application is accessible at: ${ALB_URL}"
        log_success "Health check: ${ALB_URL}/v1/health"
        log_info "ALB provides a stable endpoint that doesn't change when ECS tasks restart."
    else
        log_warning "Could not retrieve ALB URL from CloudFormation outputs. The stack might still be creating."
        log_info "You can check the stack outputs manually with:"
        log_info "aws cloudformation describe-stacks --stack-name ${STACK_NAME} --profile ${AWS_PROFILE} --region ${AWS_REGION}"
    fi
}

destroy() {
    log_info "Starting destruction process..."
    
    # Delete CloudFormation stack first
    log_info "Deleting CloudFormation stack: ${STACK_NAME}"
    aws cloudformation delete-stack \
        --stack-name ${STACK_NAME} \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION}
    
    log_success "CloudFormation stack ${STACK_NAME} deletion initiated."
    
    # Delete ECR repository
    log_info "Deleting ECR repository: ${REPOSITORY_NAME}"
    if aws ecr delete-repository \
        --repository-name "${REPOSITORY_NAME}" \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} \
        --force > /dev/null 2>&1; then
        log_success "ECR repository ${REPOSITORY_NAME} deleted."
    else
        log_warning "ECR repository ${REPOSITORY_NAME} not found or already deleted."
    fi
    
    log_info "Note: DynamoDB tables, DNS records, and certificates are NOT deleted."
    log_info "To clean up DynamoDB: $0 cleanup-dynamodb"
    log_info "To clean up SSL: $0 cleanup-ssl"
}

setup_dynamodb() {
    log_info "=== Setting up DynamoDB Tables ==="
    
    # Create main_table
    log_info "Creating main_table..."
    if aws dynamodb create-table \
        --table-name "${STACK_NAME}-main-table" \
        --attribute-definitions \
            AttributeName=id,AttributeType=S \
        --key-schema \
            AttributeName=id,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} \
        --tags Key=Name,Value="${STACK_NAME}-main-table" Key=StackName,Value="${STACK_NAME}" \
        > /dev/null 2>&1; then
        log_success "main_table created successfully"
    else
        log_warning "main_table already exists or creation failed"
    fi
    
    # Create audit_table
    log_info "Creating audit_table..."
    if aws dynamodb create-table \
        --table-name "${STACK_NAME}-audit-table" \
        --attribute-definitions \
            AttributeName=request_id,AttributeType=S \
            AttributeName=timestamp,AttributeType=N \
        --key-schema \
            AttributeName=request_id,KeyType=HASH \
            AttributeName=timestamp,KeyType=RANGE \
        --billing-mode PAY_PER_REQUEST \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} \
        --tags Key=Name,Value="${STACK_NAME}-audit-table" Key=StackName,Value="${STACK_NAME}" \
        > /dev/null 2>&1; then
        log_success "audit_table created successfully"
    else
        log_warning "audit_table already exists or creation failed"
    fi
    
    # Wait for tables to be active
    log_info "Waiting for tables to become active..."
    aws dynamodb wait table-exists \
        --table-name "${STACK_NAME}-main-table" \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} 2>/dev/null
    
    aws dynamodb wait table-exists \
        --table-name "${STACK_NAME}-audit-table" \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} 2>/dev/null
    
    log_success "DynamoDB tables are ready"
    
    # Export table names for CloudFormation
    export MAIN_TABLE_NAME="${STACK_NAME}-main-table"
    export AUDIT_TABLE_NAME="${STACK_NAME}-audit-table"
}

list_dynamodb() {
    log_info "=== DynamoDB Tables ==="
    
    # List tables
    log_info "Listing DynamoDB tables for ${STACK_NAME}..."
    
    MAIN_TABLE="${STACK_NAME}-main-table"
    AUDIT_TABLE="${STACK_NAME}-audit-table"
    
    # Check main_table
    if aws dynamodb describe-table \
        --table-name ${MAIN_TABLE} \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} &> /dev/null; then
        
        MAIN_ITEM_COUNT=$(aws dynamodb describe-table \
            --table-name ${MAIN_TABLE} \
            --profile ${AWS_PROFILE} \
            --region ${AWS_REGION} \
            --query 'Table.ItemCount' \
            --output text)
        
        log_success "main_table: ${MAIN_TABLE} (${MAIN_ITEM_COUNT} items)"
    else
        log_warning "main_table not found"
    fi
    
    # Check audit_table
    if aws dynamodb describe-table \
        --table-name ${AUDIT_TABLE} \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} &> /dev/null; then
        
        AUDIT_ITEM_COUNT=$(aws dynamodb describe-table \
            --table-name ${AUDIT_TABLE} \
            --profile ${AWS_PROFILE} \
            --region ${AWS_REGION} \
            --query 'Table.ItemCount' \
            --output text)
        
        log_success "audit_table: ${AUDIT_TABLE} (${AUDIT_ITEM_COUNT} items)"
        
        # Show recent audit entries
        log_info "Recent audit entries:"
        aws dynamodb scan \
            --table-name ${AUDIT_TABLE} \
            --profile ${AWS_PROFILE} \
            --region ${AWS_REGION} \
            --max-items 5 \
            --query 'Items[*].[timestamp.N, method.S, path.S, status_code.N, user_ip.S]' \
            --output table 2>/dev/null || log_warning "No audit entries yet"
    else
        log_warning "audit_table not found"
    fi
}

cleanup_ssl() {
    log_warning "=== Cleaning up SSL resources ==="
    log_warning "This will delete certificates and hosted zones. Are you sure? (yes/no)"
    read -r confirmation
    
    if [ "$confirmation" != "yes" ]; then
        log_info "Cleanup cancelled."
        return
    fi
    
    # Get IDs if they exist
    SPIKE_HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
        --dns-name ${SPIKE_SUBDOMAIN} \
        --profile ${AWS_PROFILE} \
        --query "HostedZones[?Name=='${SPIKE_SUBDOMAIN}.'].Id" \
        --output text | cut -d'/' -f3)
    
    if [ -n "$SPIKE_HOSTED_ZONE_ID" ]; then
        log_info "Deleting spike hosted zone: ${SPIKE_HOSTED_ZONE_ID}"
        # Delete all records except NS and SOA
        aws route53 list-resource-record-sets \
            --hosted-zone-id ${SPIKE_HOSTED_ZONE_ID} \
            --profile ${AWS_PROFILE} \
            --query "ResourceRecordSets[?Type != 'NS' && Type != 'SOA']" \
            --output json > /tmp/records.json
        
        # Delete hosted zone
        if aws route53 delete-hosted-zone \
            --id ${SPIKE_HOSTED_ZONE_ID} \
            --profile ${AWS_PROFILE} > /dev/null 2>&1; then
            log_success "Spike hosted zone deleted."
        else
            log_warning "Could not delete spike hosted zone."
        fi
    fi
    
    log_info "SSL cleanup complete. Main account resources must be cleaned up manually if needed."
}

cleanup_dynamodb() {
    log_warning "=== Cleaning up DynamoDB Tables ==="
    log_warning "This will delete all data. Are you sure? (yes/no)"
    read -r confirmation
    
    if [ "$confirmation" != "yes" ]; then
        log_info "Cleanup cancelled."
        return
    fi
    
    MAIN_TABLE="${STACK_NAME}-main-table"
    AUDIT_TABLE="${STACK_NAME}-audit-table"
    
    log_info "Deleting main_table..."
    if aws dynamodb delete-table \
        --table-name ${MAIN_TABLE} \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} > /dev/null 2>&1; then
        log_success "main_table deleted"
    else
        log_warning "main_table not found or already deleted"
    fi
    
    log_info "Deleting audit_table..."
    if aws dynamodb delete-table \
        --table-name ${AUDIT_TABLE} \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION} > /dev/null 2>&1; then
        log_success "audit_table deleted"
    else
        log_warning "audit_table not found or already deleted"
    fi
}

# Handle script arguments
case "${1:-help}" in
    "check")
        check_prerequisites
        ;;
    "setup-ssl")
        check_prerequisites
        setup_ssl
        ;;
    "create")
        check_prerequisites
        create
        ;;
    "destroy")
        destroy
        ;;
    "cleanup-ssl")
        cleanup_ssl
        ;;
    *)
        echo "Usage: $0 {check|setup-ssl|create|destroy|cleanup-ssl|help}"
        echo ""
        echo "Commands:"
        echo "  check              - Check prerequisites"
        echo "  setup-ssl          - Set up SSL certificates and DNS (main + spike accounts)"
        echo "  create             - Create full infrastructure (includes DynamoDB + SSL)"
        echo "  destroy            - Destroy all infrastructure (keeps SSL/DNS)"
        echo "  cleanup-ssl        - Remove SSL certificates and hosted zones (destructive)"
        echo "  help               - Show this help message (default)"
        echo ""
        echo "Configuration:"
        echo "  Main Account Profile: ${MAIN_ACCOUNT_PROFILE}"
        echo "  Spike Account Profile: ${AWS_PROFILE}"
        echo "  Main Domain: ${MAIN_DOMAIN}"
        echo "  Spike Subdomain: ${SPIKE_SUBDOMAIN}"
        echo ""
        echo "Stage 4 Features:"
        echo "  ✅ DynamoDB table (managed by CloudFormation)"
        echo "  ✅ HTTPS/SSL support with custom domain"
        echo "  ✅ 3-AZ high availability"
        echo "  ✅ VPC endpoints for secure DynamoDB access"
        exit 1
        ;;
esac