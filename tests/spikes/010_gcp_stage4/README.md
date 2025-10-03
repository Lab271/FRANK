# FRANK Application - Stage 4: GCP Deployment

This document describes the deployment of the FRANK application to Google Cloud Platform (GCP), as an alternative to the AWS deployment in spike 009.

## Architecture

The GCP architecture uses the following services:

- **Google Artifact Registry:** Stores the Docker container image for the application.
- **Google Cloud Run:** A serverless platform to run the containerized application. It automatically scales and is highly available.
- **Google Cloud Firestore:** A serverless, scalable NoSQL document database for data persistence.
- **Google Cloud Deployment Manager:** Used for infrastructure as code, similar to AWS CloudFormation.

## Local Development

A `Makefile` is provided for local development.

### Prerequisites

- Docker installed.
- Colima (or another Docker environment) installed.

### Commands

- `make up`: Start the local development environment using `docker-compose`.
- `make down`: Stop the local development environment.
- `make logs`: View logs from the application.
- `make call_root`: Test the root endpoint.
- `make call_health`: Test the health endpoint.
- `make help`: Show all available commands.

## Deployment

The deployment is automated using the `deploy.sh` script, which is called by the `Makefile`.

### Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured.
- Docker installed.
- A GCP project with billing enabled.

### Steps

1. **Configure Project ID:**
   Edit the `deploy.sh` script and replace `your-gcp-project-id` with your actual GCP project ID.

2. **Deploy:**
   Run the following command to deploy the application:
   ```bash
   make deploy
   ```
   This command will:
   - Enable the necessary GCP APIs.
   - Build the Docker image.
   - Push the image to Google Artifact Registry.
   - Deploy the infrastructure using Google Cloud Deployment Manager.

3. **Destroy:**
   To tear down the deployed infrastructure, run:
   ```bash
   make destroy-cloud
   ```

## API Endpoints

Once deployed, the application will provide the following endpoints:

- `GET /`: Welcome message.
- `GET /v1/health`: Health check.
- `POST /v1/data/{document_id}`: Create a document in Firestore.
- `GET /v1/data/{document_id}`: Read a document from Firestore.

## GCP vs. AWS Comparison

This section provides a critical evaluation of the GCP deployment approach compared to the AWS approach in spike 009.

### Key Differences

The most significant difference is the level of abstraction. The GCP approach uses serverless offerings like Cloud Run and Firestore, which require less infrastructure management compared to the AWS approach that uses ECS with Fargate, a VPC, and an Application Load Balancer.

### Advantages of GCP Approach (this spike)

- **Simplicity:** Cloud Run is simpler to set up and manage than ECS with Fargate. There is no need to configure VPCs, subnets, or load balancers for a basic setup.
- **Faster Deployments:** The `gcloud` CLI and Deployment Manager are generally faster than CloudFormation.
- **Cost-Effective for Low Traffic:** The pay-per-request model of Cloud Run and Firestore can be more cost-effective for applications with low or unpredictable traffic.
- **Integrated SSL:** Cloud Run provides managed SSL certificates out of the box, simplifying HTTPS setup.

### Advantages of AWS Approach (spike 009)

- **More Control:** The AWS approach provides more granular control over the networking and infrastructure components. This can be beneficial for complex applications with specific security or networking requirements.
- **Mature Ecosystem:** AWS has a more extensive and mature ecosystem of services and tools.
- **More Powerful IaC:** CloudFormation is more powerful and feature-rich than Google Cloud Deployment Manager.
- **VPC Security:** The use of a VPC with private subnets and VPC endpoints provides a higher level of network isolation and security.

### Comparison Table

| Feature | GCP (this spike) | AWS (spike 009) |
|---|---|---|
| **Container Orchestration** | Google Cloud Run | AWS ECS with Fargate |
| **Database** | Google Cloud Firestore | AWS DynamoDB |
| **Infrastructure as Code** | Google Cloud Deployment Manager | AWS CloudFormation |
| **Deployment Scripting** | `gcloud` CLI in `deploy.sh` | `aws` CLI in `deploy.sh` |
| **Networking** | Managed by Cloud Run | Custom VPC with ALB |
| **SSL/TLS** | Google-managed certificates | AWS Certificate Manager |
| **Complexity** | Lower | Higher |
| **Control** | Lower | Higher |
| **Cost Model** | Pay-per-request | Pay-per-resource (running tasks) |
