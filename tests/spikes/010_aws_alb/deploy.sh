
#!/bin/bash

# Configuration variables
AWS_PROFILE="spike-account"
AWS_REGION="eu-central-1"
STACK_NAME="frank-009-stage2"
APP_NAME="simple_api"
REPOSITORY_NAME=${STACK_NAME}
PLATFORM="linux/amd64"

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
    
  
    # Check AWS credentials
    if ! aws sts get-caller-identity --profile ${AWS_PROFILE} &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi
    
    log_success "All prerequisites are met."
}

create()
{
  log_info "Starting stack creation process..."

  # 1. Get AWS Account ID dynamically
  AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile ${AWS_PROFILE} --query Account --output text)
  ECR_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
  log_info "Using AWS Account ID: ${AWS_ACCOUNT_ID}"

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
  
  # Capture CloudFormation error output
  CF_OUTPUT=$(aws cloudformation create-stack \
    --stack-name ${STACK_NAME} \
    --profile ${AWS_PROFILE} \
    --region ${AWS_REGION} \
    --template-body file://${STACK_NAME}-infra.yaml \
    --parameters ParameterKey=ContainerImage,ParameterValue=${ECR_URL}/${REPOSITORY_NAME}:latest \
                 ParameterKey=StackName,ParameterValue=${STACK_NAME} \
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

destroy()
{
    aws ecr delete-repository \
      --repository-name "${REPOSITORY_NAME}" --profile ${AWS_PROFILE} --region ${AWS_REGION}\
      --force > /dev/null 2>&1

    log_info "ECR repository ${REPOSITORY_NAME} deleted."

    aws cloudformation delete-stack --stack-name ${STACK_NAME} --profile ${AWS_PROFILE} --region ${AWS_REGION}

    log_info "CloudFormation stack ${STACK_NAME} deletion initiated."
}

# Handle script arguments
case "${1:-help}" in
    "create")
        create
        ;;
    "check")
        check_prerequisites
        ;;
    "destroy")
        destroy
        ;;
    *)
        echo "Usage: $0 {check|create|destroy|help}"
        echo ""
        echo "Commands:"
        echo "  check              - Check prerequisites"
        echo "  create             - Create full infrastructure"
        echo "  destroy            - Destroy all infrastructure"
        echo "  help               - Show this help message (default)"
        exit 1
        ;;
esac