# Stage 4: Cloud-Agnostic Scale - Kubernetes + ScyllaDB/MongoDB

## Status: ⏳ PLANNED

**Note**: Stage 4 is currently in the planning phase. This README documents the intended architecture and approach. Implementation will begin after Stage 3 is fully validated in production.

## Overview

Stage 4 represents FRANK's final evolutionary step: **cloud-agnostic, multi-cloud deployment at production scale**. It introduces Kubernetes orchestration and vendor-independent database choices (ScyllaDB or MongoDB), enabling deployment across any cloud provider or on-premises infrastructure.

**Purpose**: Multi-cloud production deployment, vendor independence, maximum scale
**Technology Stack**: ScyllaDB or MongoDB, FastAPI, Kubernetes, Supertokens
**Location**: Any cloud provider (AWS, GCP, Azure) or on-premises
**Submissions**: Maximum model (all features, full complexity)
**Key Learning Objectives**: Kubernetes orchestration, cloud-agnostic patterns, vendor independence
**Implementation Focus**: Portability, scalability, production resilience

## Architecture

### Cloud-Agnostic Stack

```
┌─────────────────────────────────────────────────────┐
│  Kubernetes Cluster (any cloud/on-prem)             │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────────────┐ │
│  │  FastAPI Pods    │  │  Supertokens Auth        │ │
│  │  - Auto-scaling  │  │  - JWT management        │ │
│  │  - Load balanced │  │  - Session handling      │ │
│  └────────┬─────────┘  └──────────────────────────┘ │
│           │                                          │
└───────────┼──────────────────────────────────────────┘
            │
            ↓
┌─────────────────────────────────────────────────────┐
│  Database Layer (ScyllaDB or MongoDB)                │
│  - Multi-region replication                          │
│  - High availability                                 │
│  - Vendor-independent                                │
└─────────────────────────────────────────────────────┘
```

### Key Components

1. **Kubernetes Orchestration**
   - Container management and scheduling
   - Auto-scaling based on load
   - Self-healing and rolling updates
   - Multi-zone deployment for resilience

2. **Database Options**
   - **ScyllaDB**: Cassandra-compatible, high-performance NoSQL
   - **MongoDB**: Document database with rich querying
   - Both support multi-region, high-availability deployments

3. **Authentication**
   - **Supertokens**: Open-source, vendor-independent auth
   - Session management and JWT handling
   - Replaces AWS Cognito for cloud-agnostic approach

4. **Observability**
   - **Prometheus**: Metrics collection
   - **Grafana**: Dashboards and visualization
   - **ELK/Loki**: Centralized logging
   - **Jaeger**: Distributed tracing

## Planned Features

### Maximum Submission Model

Stage 4 introduces the **complete submission model** with all features:

- ✅ All observable types (IPv4, IPv6, Domain, URL, Hash, Email, Process, Registry, Mutex)
- ✅ Complex sighting relationships
- ✅ Full ThreatContext with MITRE ATT&CK mapping
- ✅ Campaign attribution and tracking
- ✅ Advanced HitTarget privacy controls
- ✅ Multi-level access tier enforcement
- ✅ Submission versioning and history

### Production Capabilities

- **Multi-Region Deployment**: Active-active across regions
- **Disaster Recovery**: Automated failover and backup
- **Advanced Monitoring**: Full observability stack
- **Performance**: Sub-100ms query response times
- **Scalability**: Handles 10,000+ submissions/day
- **Security**: End-to-end encryption, audit logging

## Technology Stack

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Orchestration** | Kubernetes (K8s) | Container management, auto-scaling |
| **Database** | ScyllaDB or MongoDB | Vendor-independent, high-performance storage |
| **Authentication** | Supertokens | Cloud-agnostic auth and session management |
| **API** | FastAPI | High-performance Python web framework |
| **Service Mesh** | Istio (optional) | Traffic management, security, observability |
| **Ingress** | NGINX Ingress | Load balancing, SSL termination |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards |
| **Logging** | Loki or ELK | Centralized log aggregation |
| **Tracing** | Jaeger | Distributed request tracing |

### Database Comparison

| Feature | ScyllaDB | MongoDB |
|---------|----------|---------|
| **Type** | Wide-column NoSQL | Document NoSQL |
| **Query Language** | CQL (Cassandra) | MongoDB Query Language |
| **Performance** | Extremely high throughput | Very good performance |
| **Scalability** | Excellent horizontal scaling | Good horizontal scaling |
| **Replication** | Multi-datacenter support | Replica sets, sharding |
| **FRANK Fit** | Best for high write throughput | Best for complex queries |

**Recommendation**: Start with **MongoDB** for rich querying capabilities, migrate to **ScyllaDB** if write throughput becomes bottleneck.

## Key Learning Objectives

1. **Kubernetes Orchestration**
   - Deployment manifests and Helm charts
   - Auto-scaling and load balancing
   - Health checks and self-healing
   - Rolling updates and rollbacks

2. **Cloud-Agnostic Patterns**
   - Vendor-independent architecture
   - Portable deployment configurations
   - Multi-cloud networking
   - Provider abstraction layers

3. **Production Operations**
   - Disaster recovery planning
   - Backup and restore procedures
   - Security hardening
   - Performance optimization

4. **Observability**
   - Metrics collection and alerting
   - Distributed tracing
   - Log aggregation and analysis
   - Dashboard creation

## Implementation Focus

### Vendor Independence

Stage 4 prioritizes **vendor independence** over cloud-specific optimizations:

- Use open-source tools (Kubernetes, Supertokens, Prometheus)
- Avoid cloud-specific services (no AWS ECS, GCP Cloud Run, etc.)
- Standard container images (portable across clouds)
- Infrastructure as Code with cloud-agnostic tools (Terraform, Helm)

### Multi-Cloud Deployment

Support deployment to:
- **AWS**: EKS (Elastic Kubernetes Service)
- **GCP**: GKE (Google Kubernetes Engine)
- **Azure**: AKS (Azure Kubernetes Service)
- **On-Premises**: Self-managed Kubernetes cluster

## Success Criteria

Stage 4 is successful when:

- ✅ Kubernetes cluster deploys on AWS, GCP, or Azure
- ✅ Database replicates across multiple zones/regions
- ✅ Supertokens authentication works correctly
- ✅ Auto-scaling responds to load changes
- ✅ Monitoring dashboards show all metrics
- ✅ Rolling updates complete without downtime
- ✅ Disaster recovery tested successfully
- ✅ All unit/integration tests pass
- ✅ Can switch cloud providers within 24 hours

## Risk Mitigation

### Complexity Management

- **Incremental Deployment**: Start with single-region before multi-region
- **Thorough Testing**: Extensive integration and load testing
- **Documentation**: Comprehensive runbooks for operations

### Fallback Strategy

If Stage 4 proves too complex or unstable:
- **Fall back to Stage 3**: AWS ECS deployment (proven, stable)
- **Retain Infrastructure**: Keep Kubernetes cluster for future use
- **Gradual Migration**: Move services one at a time, not all at once

### Technology Validation

Before full implementation:
- **Spike Testing**: Validate Kubernetes, ScyllaDB/MongoDB, Supertokens
- **Load Testing**: Ensure performance meets requirements
- **Cost Analysis**: Compare operational costs across clouds

## Database Connection Guide

See [DATABASE_CONNECTION_GUIDE.md](DATABASE_CONNECTION_GUIDE.md) for detailed connection patterns and configuration for ScyllaDB and MongoDB.

## Contributing Spikes

Stage 4 will integrate future spikes validating:

- Kubernetes deployment patterns
- ScyllaDB/MongoDB data modeling
- Supertokens authentication integration
- Multi-region replication strategies
- Observability stack implementation

New spikes will be numbered 016+ and tracked in [tests/spikes/index.md](../../tests/spikes/index.md).

## Configuration

### Environment Variables (Planned)

```bash
# Environment
FRANK_ENVIRONMENT=aws-k8s          # Or gcp-k8s, azure-k8s
FRANK_STAGE=4                       # Stage 4

# Database
DB_TYPE=mongodb                     # Or scylladb
DB_HOSTS=mongo1,mongo2,mongo3       # Database cluster hosts
DB_PORT=27017                       # Database port
DB_NAME=frank                       # Database name
DB_USER=frank_app                   # Database user
DB_PASSWORD=<secret>                # Database password (from secrets)

# Authentication
SUPERTOKENS_URL=http://supertokens:3567
SUPERTOKENS_API_KEY=<secret>

# Kubernetes
K8S_NAMESPACE=frank-production
K8S_REPLICAS=3                      # Number of API pods
K8S_MAX_REPLICAS=10                 # Auto-scaling maximum

# Observability
PROMETHEUS_URL=http://prometheus:9090
GRAFANA_URL=http://grafana:3000
JAEGER_ENDPOINT=http://jaeger:14268
```

## Deployment (Planned)

### Prerequisites

- Kubernetes cluster (EKS, GKE, AKS, or self-managed)
- `kubectl` configured for cluster access
- Helm 3.x installed
- Database cluster deployed (MongoDB or ScyllaDB)
- Persistent storage provisioner configured

### Deployment Steps (Future)

```bash
# 1. Create namespace
kubectl create namespace frank-production

# 2. Deploy database (MongoDB example)
helm install mongodb bitnami/mongodb \
  --namespace frank-production \
  --set auth.rootPassword=<root-password> \
  --set replicaCount=3

# 3. Deploy Supertokens
helm install supertokens supertokens/supertokens \
  --namespace frank-production

# 4. Deploy FRANK API
helm install frank ./helm/frank \
  --namespace frank-production \
  --values values-production.yaml

# 5. Verify deployment
kubectl get pods -n frank-production
kubectl get services -n frank-production

# 6. Access application
kubectl port-forward -n frank-production service/frank-api 8000:8000
```

## Monitoring and Observability (Planned)

### Metrics

- **Request Rate**: Requests per second by endpoint
- **Latency**: p50, p95, p99 response times
- **Error Rate**: 4xx and 5xx error percentages
- **Database Performance**: Query latency, connection pool usage
- **Resource Usage**: CPU, memory, network per pod

### Dashboards

- **Application Dashboard**: API metrics, error rates, throughput
- **Infrastructure Dashboard**: Node health, pod status, resource usage
- **Database Dashboard**: Query performance, replication lag, storage usage

### Alerting

- High error rate (>5% for 5 minutes)
- Slow response times (p95 >500ms for 5 minutes)
- Database connection failures
- Pod crash loops
- Resource exhaustion

## Troubleshooting (Planned)

### Common Issues

**Issue**: Pods stuck in CrashLoopBackOff
```bash
# Check pod logs
kubectl logs -n frank-production <pod-name>

# Describe pod for events
kubectl describe pod -n frank-production <pod-name>
```

**Issue**: Database connection failures
```bash
# Verify database pods are running
kubectl get pods -n frank-production -l app=mongodb

# Check database logs
kubectl logs -n frank-production <db-pod-name>
```

**Issue**: High memory usage
```bash
# Check resource limits
kubectl describe pod -n frank-production <pod-name>

# Adjust resource limits in Helm values
# values-production.yaml:
# resources:
#   limits:
#     memory: 2Gi
```

## Next Steps from Stage 3

Transitioning from Stage 3 (AWS ECS) to Stage 4 (Kubernetes):

1. **Validate Kubernetes Deployment**: Run spikes testing K8s patterns
2. **Choose Database**: Decide between MongoDB and ScyllaDB
3. **Implement Supertokens**: Replace AWS Cognito
4. **Set Up Observability**: Deploy Prometheus, Grafana, Jaeger
5. **Test Multi-Cloud**: Verify deployment on AWS and GCP
6. **Load Testing**: Ensure performance at scale
7. **Gradual Migration**: Move non-critical workloads first

## Fallback to Stage 3

If Stage 4 encounters issues, fall back to Stage 3:

```bash
# 1. Keep data in DynamoDB (or export from MongoDB/ScyllaDB)
# 2. Deploy Stage 3 AWS ECS stack
cd stages/stage3
ansible-playbook ansible/playbook.yml --tags create

# 3. Migrate traffic back to ECS
# 4. Investigate and resolve Stage 4 issues
# 5. Retry Stage 4 deployment when ready
```

## Related Documentation

- [ADR-0001: Four-Stage Infrastructure Evolution](../../.openspec/architecture/decisions/0001-four-stage-infrastructure-evolution.md) - Stage 4 rationale
- [ADR-0010: Stages vs Environments](../../.openspec/architecture/decisions/0010-stages-vs-environments.md) - Understanding stages
- [Implementation Plan](../../docs/implementation_plan.md) - Stage 4 roadmap
- [DATABASE_CONNECTION_GUIDE.md](DATABASE_CONNECTION_GUIDE.md) - Database setup guide
- [stages/stage3/README.md](../stage3/README.md) - Previous stage documentation

---

*Last updated: 2026-02-01*
*Status: Planning phase - implementation pending Stage 3 production validation*
