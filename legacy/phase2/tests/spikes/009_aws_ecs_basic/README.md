FRANK Application - Stage 1: Absolute Minimal Setup
==================================================

## Status
INTEGRATED

## Integrated Into
- `stages/stage3/` - AWS cloud deployment
- `ansible/` - Deployment automation

---

HYPOTHESIS:
-----------
A single containerized FastAPI application can be deployed to AWS ECS Fargate with minimal 
infrastructure components to validate basic cloud deployment patterns and establish a 
foundation for incremental complexity addition.

OBJECTIVE:
----------
Deploy the simplest possible cloud-native setup that demonstrates:
1. Container orchestration in the cloud
2. Public internet accessibility
3. Basic security group configuration
4. Container registry integration

ARCHITECTURE HYPOTHESIS:
-----------------------
By using ECS Fargate in a public subnet with direct internet access, we can achieve:
- Zero infrastructure management overhead
- Immediate public accessibility without load balancers
- Minimal AWS service dependencies
- Cost-effective proof of concept deployment

COMPONENT RATIONALE:
-------------------

1. **ECS Fargate Task (Single Instance)**
   - Hypothesis: Serverless container execution eliminates EC2 management complexity
   - Expected outcome: Application runs without server provisioning
   - Risk: Single point of failure, IP address changes on restart

2. **Public Subnet Deployment**
   - Hypothesis: Direct internet access simplifies initial networking
   - Expected outcome: Container receives public IP automatically
   - Risk: Increased attack surface, no network isolation

3. **ECR (Elastic Container Registry)**
   - Hypothesis: Native AWS registry provides seamless ECS integration
   - Expected outcome: Secure, authenticated container image storage
   - Risk: Additional cost for image storage

4. **Security Group (0.0.0.0/0:80)**
   - Hypothesis: Open HTTP access validates basic connectivity
   - Expected outcome: Application accessible from any internet location
   - Risk: Security vulnerability in production scenarios

5. **No Load Balancer**
   - Hypothesis: Direct task access reduces complexity and cost
   - Expected outcome: Immediate accessibility via public IP
   - Risk: IP address instability, no health checking

VALIDATION CRITERIA:
-------------------
1. Application accessible via public IP over HTTP
2. Container starts successfully in ECS Fargate
3. FastAPI endpoints respond correctly
4. Container can be updated with new image versions
5. Logs available in CloudWatch

EXPECTED LIMITATIONS:
--------------------
1. **IP Address Volatility**: Public IP changes on task restart
2. **No Health Monitoring**: Manual verification of application status required
3. **Single Point of Failure**: No redundancy or failover capability
4. **Security Exposure**: Application directly exposed to internet
5. **No SSL/TLS**: Only HTTP communication supported
6. **No Persistence**: Stateless container with no data storage

SUCCESS METRICS:
---------------
- Application responds to HTTP requests within 5 seconds
- Container startup time under 2 minutes
- 99% uptime during testing period (excluding planned restarts)
- Successful image updates without manual intervention

RISK MITIGATION:
---------------
- Document public IP for testing before task restarts
- Monitor CloudWatch logs for application errors
- Use security group rules to restrict access if needed
- Plan migration path to Stage 2 (Load Balancer) for stability

LEARNING OUTCOMES:
-----------------
1. ECS Fargate task definition configuration
2. ECR image lifecycle management
3. VPC and subnet networking basics
4. Security group rule implementation
5. CloudWatch logging integration
6. AWS CLI/Console container management

TRANSITION TO STAGE 2:
---------------------
This stage establishes the foundation for adding an Application Load Balancer,
which will address the IP volatility and health monitoring limitations while
introducing stable DNS endpoints and improved security through private subnets.

COST IMPLICATIONS:
-----------------
- ECS Fargate: Pay per vCPU/memory usage (~$0.04/hour for 0.25 vCPU, 0.5GB)
- ECR: $0.10/GB/month for storage
- Data transfer: $0.09/GB for outbound internet traffic
- Estimated monthly cost: $5-15 for development workloads

DEPLOYMENT VERIFICATION:
-----------------------
```bash
# Test application accessibility
curl http://<public-ip>
curl http://<public-ip>/v1/health

# Expected responses
{"application": "FRANK", "status": "running"}
{"status": "healthy", "service": "FRANK"}
```

This stage validates the fundamental hypothesis that cloud-native applications
can be deployed with minimal complexity while maintaining observability and
update capabilities essential for production evolution.
