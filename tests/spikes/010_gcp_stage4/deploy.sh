#!/bin/bash

# Configuration variables
export GCP_PROJECT_ID="your-gcp-project-id" # CHANGE THIS
export GCP_REGION="europe-west4"
export AR_REPO="frank-gcp-repo"
export SERVICE_NAME="frank-gcp-service"
export IMAGE_NAME="simple-api"
export DEPLOYMENT_NAME="frank-gcp-deployment"

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

    if [ "$GCP_PROJECT_ID" == "your-gcp-project-id" ]; then
        log_error "Please set your GCP_PROJECT_ID in this script."
        exit 1
    fi

    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud is not installed. Please install it first."
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi

    log_success "All prerequisites are met."
}

enable_apis() {
    log_info "Enabling necessary GCP APIs..."
    gcloud services enable artifactregistry.googleapis.com \
                        run.googleapis.com \
                        deploymentmanager.googleapis.com \
                        cloudbuild.googleapis.com --project=$GCP_PROJECT_ID
    log_success "APIs enabled."
}

build_and_push_image() {
    log_info "Building and pushing Docker image..."

    # Configure Docker to use gcloud as a credential helper
    gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev -q

    # Build the image
    docker build -t ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest .

    # Push the image
    docker push ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest

    log_success "Image pushed to Artifact Registry."
}

deploy_infra() {
    log_info "Deploying infrastructure..."

    # Replace placeholder in gcp-infra.yaml
    sed -i.bak "s/your-gcp-project-id/${GCP_PROJECT_ID}/g" gcp-infra.yaml

    # Deploy using Deployment Manager
    gcloud deployment-manager deployments create ${DEPLOYMENT_NAME} \
        --config gcp-infra.yaml \
        --project=${GCP_PROJECT_ID}

    log_success "Infrastructure deployment initiated."

    # Clean up backup file
    rm gcp-infra.yaml.bak
}

destroy_infra() {
    log_info "Destroying infrastructure..."

    gcloud deployment-manager deployments delete ${DEPLOYMENT_NAME} --project=${GCP_PROJECT_ID} -q

    log_success "Infrastructure deployment deleted."
}

# Handle script arguments
case "${1:-help}" in
    "check")
        check_prerequisites
        ;;
    "deploy")
        check_prerequisites
        enable_apis
        build_and_push_image
        deploy_infra
        ;;
    "destroy")
        check_prerequisites
        destroy_infra
        ;;
    *)
        echo "Usage: $0 {check|deploy|destroy|help}"
        ;;
esac
