# FRANK Ansible Deployment

This directory contains Ansible automation for deploying the FRANK AWS infrastructure.

## Structure

```
ansible/
├── playbook.yml              # Main deployment playbook
├── requirements.yml          # Ansible collections requirements
└── tasks/
    ├── prerequisites.yml     # Check prerequisites and setup
    ├── ssl.yml              # SSL certificate management
    ├── docker.yml           # Docker build and push
    ├── cloudformation.yml   # CloudFormation deployment
    └── cleanup.yml          # Resource cleanup
```

## Prerequisites

1. **Install Ansible**:
   ```bash
   pip install ansible
   ```

2. **Install required collections**:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

3. **AWS CLI configured** with profiles:
   - `spike-account`: For the deployment account
   - `default` (or your main account): For SSL certificates

4. **Docker** installed and running

## Usage

### Deploy Infrastructure

```bash
# Create new stack (or update if exists)
ansible-playbook playbook.yml --tags "create"

# Update existing stack
ansible-playbook playbook.yml --tags "update"

# Deploy (smart create/update)
ansible-playbook playbook.yml --tags "deploy"

# Delete stack
ansible-playbook playbook.yml --tags "delete"

# Run only Docker operations
ansible-playbook playbook.yml --tags "docker"

# Run only SSL setup
ansible-playbook playbook.yml --tags "ssl"

# Run only CloudFormation deployment
ansible-playbook playbook.yml --tags "cloudformation"

# Run cleanup operations
ansible-playbook playbook.yml --tags "cleanup"
```

### Tag Combinations

You can combine multiple tags:

```bash
# Run SSL setup and Docker operations only
ansible-playbook playbook.yml --tags "ssl,docker"

# Run full deployment pipeline
ansible-playbook playbook.yml --tags "ssl,docker,cloudformation"
```

### Custom Configuration

You can override default variables while using tags:

```bash
ansible-playbook playbook.yml --tags "deploy" \
  -e stack_name=my-frank-stack \
  -e aws_region=us-west-2 \
  -e image_tag=v1.2.3 \
  -e ssl_domain=my-domain.com
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `stack_name` | `frank-009-stage4` | CloudFormation stack name |
| `aws_region` | `eu-central-1` | AWS region |
| `aws_profile` | `spike-account` | AWS profile for deployment |
| `main_account_profile` | `main-account` | AWS profile for SSL certificates |
| `app_name` | `simple_api` | Application name for ECR repository |
| `image_tag` | `latest` | Docker image tag |
| `ssl_domain` | `frank-009-stage4.lab271.io` | Domain for SSL certificate |

## Tags

| Tag | Description | Tasks Included |
|-----|-------------|----------------|
| `always` | Always runs | Prerequisites, Display info |
| `create` | Create deployment | SSL, Docker, CloudFormation |
| `update` | Update deployment | SSL, Docker, CloudFormation |
| `deploy` | Smart create/update | SSL, Docker, CloudFormation |
| `ssl` | SSL operations only | SSL certificate lookup |
| `docker` | Docker operations only | ECR, Build, Push |
| `cloudformation` | Infrastructure only | CloudFormation deployment |
| `delete` | Delete resources | Cleanup operations |
| `cleanup` | Cleanup operations | Delete stack and ECR |

## Features

- **Idempotent**: Safe to run multiple times
- **Error Handling**: Comprehensive error checking and validation
- **SSL Support**: Automatic SSL certificate lookup and configuration
- **Logging**: Operations logged to `logs/` directory
- **Cleanup**: Complete resource cleanup with delete action

## Logs

The playbook creates logs in the `logs/` directory:
- `docker.log`: Docker operations
- `deployment.log`: CloudFormation deployments
- `cleanup.log`: Cleanup operations

## Troubleshooting

1. **AWS Credentials**: Ensure your AWS profiles are configured correctly
2. **Docker**: Make sure Docker is running and buildx is available
3. **SSL**: SSL certificate must exist in the main account (us-east-1)
4. **Permissions**: Ensure AWS credentials have necessary permissions for ECS, ECR, CloudFormation, etc.