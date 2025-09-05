#!/bin/bash

# OpenSearch Domain Setup Script
# This script configures the OpenSearch domain with index templates, security roles, and dashboards

set -e

# Configuration
ENVIRONMENT=${ENVIRONMENT:-dev}
PROJECT_NAME=${PROJECT_NAME:-frank}
AWS_REGION=${AWS_REGION:-us-east-1}
DOMAIN_NAME="${PROJECT_NAME}-${ENVIRONMENT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to wait for OpenSearch domain to be ready
wait_for_domain() {
    log "Waiting for OpenSearch domain to be ready..."
    
    while true; do
        STATUS=$(aws opensearch describe-domain \
            --domain-name "$DOMAIN_NAME" \
            --region "$AWS_REGION" \
            --query 'DomainStatus.Processing' \
            --output text 2>/dev/null || echo "true")
        
        if [ "$STATUS" = "false" ]; then
            log "OpenSearch domain is ready"
            break
        fi
        
        log "Domain is still processing... waiting 30 seconds"
        sleep 30
    done
}

# Function to get domain endpoint
get_domain_endpoint() {
    aws opensearch describe-domain \
        --domain-name "$DOMAIN_NAME" \
        --region "$AWS_REGION" \
        --query 'DomainStatus.Endpoint' \
        --output text
}

# Function to create index template
create_index_template() {
    local template_name=$1
    local template_file=$2
    local endpoint=$3
    
    log "Creating index template: $template_name"
    
    curl -XPUT "https://$endpoint/_index_template/$template_name" \
        -H "Content-Type: application/json" \
        -d @"$template_file" \
        --aws-sigv4 "aws:amz:${AWS_REGION}:es" \
        --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
        -w "%{http_code}\n" -o /tmp/response.json
    
    if [ $? -eq 0 ]; then
        log "Index template $template_name created successfully"
    else
        error "Failed to create index template $template_name"
        cat /tmp/response.json
    fi
}

# Function to create security role
create_security_role() {
    local role_name=$1
    local role_file=$2
    local endpoint=$3
    
    log "Creating security role: $role_name"
    
    curl -XPUT "https://$endpoint/_plugins/_security/api/roles/$role_name" \
        -H "Content-Type: application/json" \
        -d @"$role_file" \
        --aws-sigv4 "aws:amz:${AWS_REGION}:es" \
        --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
        -w "%{http_code}\n" -o /tmp/response.json
    
    if [ $? -eq 0 ]; then
        log "Security role $role_name created successfully"
    else
        error "Failed to create security role $role_name"
        cat /tmp/response.json
    fi
}

# Function to import dashboard
import_dashboard() {
    local dashboard_file=$1
    local endpoint=$2
    
    log "Importing dashboard configuration"
    
    curl -XPOST "https://$endpoint/_dashboards/api/saved_objects/_import" \
        -H "Content-Type: application/json" \
        -H "osd-xsrf: true" \
        -d @"$dashboard_file" \
        --aws-sigv4 "aws:amz:${AWS_REGION}:es" \
        --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
        -w "%{http_code}\n" -o /tmp/response.json
    
    if [ $? -eq 0 ]; then
        log "Dashboard imported successfully"
    else
        error "Failed to import dashboard"
        cat /tmp/response.json
    fi
}

# Function to setup snapshot repository
setup_snapshot_repository() {
    local endpoint=$1
    local bucket_name=$2
    
    log "Setting up snapshot repository"
    
    cat > /tmp/snapshot_repo.json << EOF
{
  "type": "s3",
  "settings": {
    "bucket": "$bucket_name",
    "region": "$AWS_REGION",
    "role_arn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/${PROJECT_NAME}-opensearch-snapshot-role-${ENVIRONMENT}"
  }
}
EOF
    
    curl -XPUT "https://$endpoint/_snapshot/frank-snapshots" \
        -H "Content-Type: application/json" \
        -d @/tmp/snapshot_repo.json \
        --aws-sigv4 "aws:amz:${AWS_REGION}:es" \
        --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
        -w "%{http_code}\n" -o /tmp/response.json
    
    if [ $? -eq 0 ]; then
        log "Snapshot repository configured successfully"
    else
        error "Failed to configure snapshot repository"
        cat /tmp/response.json
    fi
}

# Function to create index lifecycle policy
create_lifecycle_policy() {
    local endpoint=$1
    
    log "Creating index lifecycle policy"
    
    cat > /tmp/lifecycle_policy.json << EOF
{
  "policy": {
    "description": "FRANK index lifecycle policy",
    "default_state": "hot",
    "states": [
      {
        "name": "hot",
        "actions": [
          {
            "rollover": {
              "min_size": "50gb",
              "min_doc_count": 1000000,
              "min_index_age": "7d"
            }
          }
        ],
        "transitions": [
          {
            "state_name": "warm",
            "conditions": {
              "min_index_age": "30d"
            }
          }
        ]
      },
      {
        "name": "warm",
        "actions": [
          {
            "replica_count": {
              "number_of_replicas": 0
            }
          }
        ],
        "transitions": [
          {
            "state_name": "cold",
            "conditions": {
              "min_index_age": "90d"
            }
          }
        ]
      },
      {
        "name": "cold",
        "actions": [],
        "transitions": [
          {
            "state_name": "delete",
            "conditions": {
              "min_index_age": "365d"
            }
          }
        ]
      },
      {
        "name": "delete",
        "actions": [
          {
            "delete": {}
          }
        ]
      }
    ],
    "ism_template": {
      "index_patterns": ["frank-sightings-*", "frank-indicators-*"],
      "priority": 100
    }
  }
}
EOF
    
    curl -XPUT "https://$endpoint/_plugins/_ism/policies/frank-lifecycle" \
        -H "Content-Type: application/json" \
        -d @/tmp/lifecycle_policy.json \
        --aws-sigv4 "aws:amz:${AWS_REGION}:es" \
        --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
        -w "%{http_code}\n" -o /tmp/response.json
    
    if [ $? -eq 0 ]; then
        log "Lifecycle policy created successfully"
    else
        error "Failed to create lifecycle policy"
        cat /tmp/response.json
    fi
}

# Main execution
main() {
    log "Starting OpenSearch domain configuration for environment: $ENVIRONMENT"
    
    # Check if domain exists
    if ! aws opensearch describe-domain --domain-name "$DOMAIN_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
        error "OpenSearch domain $DOMAIN_NAME not found. Please deploy the CloudFormation template first."
        exit 1
    fi
    
    # Wait for domain to be ready
    wait_for_domain
    
    # Get domain endpoint
    ENDPOINT=$(get_domain_endpoint)
    if [ -z "$ENDPOINT" ]; then
        error "Failed to get domain endpoint"
        exit 1
    fi
    
    log "Domain endpoint: $ENDPOINT"
    
    # Get snapshot bucket name
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "${PROJECT_NAME}-opensearch-${ENVIRONMENT}" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`SnapshotBucketName`].OutputValue' \
        --output text)
    
    # Create index templates
    if [ -f "templates/sightings-template.json" ]; then
        create_index_template "frank-sightings" "templates/sightings-template.json" "$ENDPOINT"
    fi
    
    if [ -f "templates/indicators-template.json" ]; then
        create_index_template "frank-indicators" "templates/indicators-template.json" "$ENDPOINT"
    fi
    
    if [ -f "templates/tenants-template.json" ]; then
        create_index_template "frank-tenants" "templates/tenants-template.json" "$ENDPOINT"
    fi
    
    # Create security roles
    if [ -f "security/analyst-role.json" ]; then
        create_security_role "frank_analyst" "security/analyst-role.json" "$ENDPOINT"
    fi
    
    if [ -f "security/admin-role.json" ]; then
        create_security_role "frank_admin" "security/admin-role.json" "$ENDPOINT"
    fi
    
    # Setup snapshot repository
    if [ ! -z "$BUCKET_NAME" ]; then
        setup_snapshot_repository "$ENDPOINT" "$BUCKET_NAME"
    fi
    
    # Create lifecycle policy
    create_lifecycle_policy "$ENDPOINT"
    
    # Import dashboards
    if [ -f "dashboards/frank-dashboards.json" ]; then
        import_dashboard "dashboards/frank-dashboards.json" "$ENDPOINT"
    fi
    
    log "OpenSearch domain configuration completed successfully!"
    log "Dashboard URL: https://$ENDPOINT/_dashboards"
    
    # Clean up temporary files
    rm -f /tmp/response.json /tmp/snapshot_repo.json /tmp/lifecycle_policy.json
}

# Run main function
main "$@"
