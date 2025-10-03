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
# Create new stack
ansible-playbook playbook.yml -e action=create

# Update existing stack
ansible-playbook playbook.yml -e action=update

# Delete stack
ansible-playbook playbook.yml -e action=delete
```

### Custom Configuration

You can override default variables:

```bash
ansible-playbook playbook.yml \
  -e action=create \
  -e stack_name=my-frank-stack \
  -e aws_region=us-west-2 \
  -e image_tag=v1.2.3 \
  -e ssl_domain=my-domain.com
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `action` | `create` | Action to perform: create, update, delete |
| `stack_name` | `frank-009-stage4` | CloudFormation stack name |
| `aws_region` | `eu-central-1` | AWS region |
| `aws_profile` | `spike-account` | AWS profile for deployment |
| `main_account_profile` | `default` | AWS profile for SSL certificates |
| `app_name` | `frank` | Application name for ECR repository |
| `image_tag` | `latest` | Docker image tag |
| `ssl_domain` | `frank.heitlager.eu` | Domain for SSL certificate |

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