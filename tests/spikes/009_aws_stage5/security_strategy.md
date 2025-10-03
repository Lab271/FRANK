# FRANK AWS Security Strategy
# Recommended IAM Role Structure

## 🎯 RECOMMENDED APPROACH: 5 IAM Roles (Not Accounts)

### **Why Roles > Accounts?**
- ✅ **Single password** to remember
- ✅ **Easier management** and auditing  
- ✅ **Cost effective** (no cross-account charges)
- ✅ **Simpler networking** (no VPC peering)
- ✅ **Better for small teams** (< 10 people)

---

## 🔑 **Proposed Role Structure**

### 1. **frank-infra-creator** (CloudFormation + Networking)
**Purpose**: Create AWS infrastructure (VPC, ALB, ECS Cluster, IAM roles)
**When to use**: Initial environment setup, infrastructure changes
**Time limit**: 2 hours
**MFA required**: Yes

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "ec2:*",
        "ecs:CreateCluster",
        "ecs:DescribeCluster*",
        "elasticloadbalancing:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PassRole",
        "logs:CreateLogGroup",
        "route53:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "aws:RequestedRegion": ["eu-central-1", "eu-west-1"]
        }
      }
    }
  ]
}
```

### 2. **frank-infra-destroyer** (Cleanup Only)
**Purpose**: Delete infrastructure and resources
**When to use**: Environment cleanup, cost control
**Time limit**: 30 minutes
**MFA required**: Yes (with confirmation)

```json
{
  "Version": "2012-10-17", 
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStack*",
        "ecs:DeleteCluster",
        "ecs:DeleteService", 
        "ec2:TerminateInstances",
        "ec2:DeleteVpc",
        "elasticloadbalancing:DeleteLoadBalancer",
        "dynamodb:DeleteTable"
      ],
      "Resource": "*",
      "Condition": {
        "Bool": {"aws:MultiFactorAuthPresent": "true"},
        "NumericLessThan": {"aws:MultiFactorAuthAge": "1800"},
        "StringLike": {
          "aws:userid": "*:${aws:username}"
        }
      }
    }
  ]
}
```

### 3. **frank-app-deployer** (Container Deployment)
**Purpose**: Deploy/update Docker containers and ECS services
**When to use**: Application updates, scaling changes
**Time limit**: 4 hours
**MFA required**: No (for CI/CD)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow", 
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:RegisterTaskDefinition", 
        "ecs:DescribeTaskDefinition",
        "ecs:ListTasks",
        "ecs:DescribeTasks",
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer", 
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "ecs:cluster": "arn:aws:ecs:*:*:cluster/frank-*"
        }
      }
    }
  ]
}
```

### 4. **frank-data-reader** (DynamoDB Read-Only)
**Purpose**: Read application data, debugging, monitoring
**When to use**: Data analysis, troubleshooting, monitoring
**Time limit**: 8 hours
**MFA required**: No

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:Query", 
        "dynamodb:Scan",
        "dynamodb:DescribeTable",
        "dynamodb:ListTables",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams", 
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/frank-*",
        "arn:aws:logs:*:*:log-group:/aws/ecs/frank-*",
        "*"
      ]
    }
  ]
}
```

### 5. **frank-emergency-admin** (Break Glass Access)
**Purpose**: Emergency access when everything is broken
**When to use**: Production incidents, critical issues
**Time limit**: 15 minutes
**MFA required**: Yes (fresh login)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*", 
      "Condition": {
        "Bool": {"aws:MultiFactorAuthPresent": "true"},
        "NumericLessThan": {"aws:MultiFactorAuthAge": "300"},
        "StringEquals": {
          "aws:PrincipalTag/EmergencyAccess": "true"
        }
      }
    }
  ]
}
```

---

## 🛠️ **Implementation Strategy**

### **Phase 1: Setup (1 hour)**
```bash
# 1. Create IAM roles
aws iam create-role --role-name frank-infra-creator --assume-role-policy-document file://trust-policy.json
aws iam create-role --role-name frank-infra-destroyer --assume-role-policy-document file://trust-policy.json  
aws iam create-role --role-name frank-app-deployer --assume-role-policy-document file://trust-policy.json
aws iam create-role --role-name frank-data-reader --assume-role-policy-document file://trust-policy.json
aws iam create-role --role-name frank-emergency-admin --assume-role-policy-document file://trust-policy.json

# 2. Attach policies to roles
aws iam put-role-policy --role-name frank-infra-creator --policy-name InfraCreatorPolicy --policy-document file://infra-creator-policy.json
# ... repeat for other roles
```

### **Phase 2: Configure AWS CLI (15 minutes)**
```ini
# ~/.aws/config
[profile frank-infra]
role_arn = arn:aws:iam::350012230634:role/frank-infra-creator
source_profile = spike-account
external_id = frank-deployment-access
mfa_serial = arn:aws:iam::350012230634:mfa/iheitlager
duration_seconds = 7200

[profile frank-deploy] 
role_arn = arn:aws:iam::350012230634:role/frank-app-deployer
source_profile = spike-account
external_id = frank-deployment-access
duration_seconds = 14400

[profile frank-data]
role_arn = arn:aws:iam::350012230634:role/frank-data-reader
source_profile = spike-account
external_id = frank-deployment-access
duration_seconds = 28800

[profile frank-destroy]
role_arn = arn:aws:iam::350012230634:role/frank-infra-destroyer  
source_profile = spike-account
external_id = frank-deployment-access
mfa_serial = arn:aws:iam::350012230634:mfa/iheitlager
duration_seconds = 1800

[profile frank-emergency]
role_arn = arn:aws:iam::350012230634:role/frank-emergency-admin
source_profile = spike-account
external_id = frank-deployment-access
mfa_serial = arn:aws:iam::350012230634:mfa/iheitlager
duration_seconds = 900
```

### **Phase 3: Daily Workflow**
```bash
# Create infrastructure
aws --profile frank-infra cloudformation deploy --stack-name frank-dev

# Deploy application  
aws --profile frank-deploy ecs update-service --service frank-service

# Check data
aws --profile frank-data dynamodb scan --table-name frank-data

# Emergency access (requires fresh MFA)
aws --profile frank-emergency sts get-caller-identity

# Destroy environment
aws --profile frank-destroy cloudformation delete-stack --stack-name frank-dev
```

---

## 🎯 **Answers to Your Questions**

### **Q: Do I need super admin?**  
**A: YES** - but only for emergencies (frank-emergency-admin role)
- Time-limited to 15 minutes
- Requires fresh MFA
- Heavily audited
- Used only when other roles can't fix the issue

### **Q: Should I separate infra creation/destruction?**
**A: YES** - excellent idea!
- Prevents accidental deletions
- Destruction requires explicit role switch + MFA
- Creation doesn't need destruction permissions
- Clear audit trail of who deleted what

### **Q: Separate app deployment?**
**A: YES** - perfect for CI/CD
- No MFA required (for automation)
- Cannot create/destroy infrastructure  
- Only updates existing applications
- Ideal for GitHub Actions/Jenkins

### **Q: Separate data reading?**
**A: YES** - great for debugging
- Read-only access to databases
- Can access logs for troubleshooting
- Long session duration (8 hours)
- No ability to modify/delete data

---

## 📊 **Comparison: Your Idea vs. Best Practice**

| Your Proposal | Best Practice | Recommendation |
|--------------|---------------|----------------|
| Super admin | Emergency admin (15min) | ✅ Keep but time-limit |
| Infra creation | Infra creator (2hr) | ✅ Perfect |
| Infra destruction | Infra destroyer (30min + MFA) | ✅ Excellent separation |
| Docker deployment | App deployer (4hr) | ✅ Great for CI/CD |
| Data reading | Data reader (8hr) | ✅ Perfect for debugging |

## 🏆 **Final Recommendation**

**Use your proposed structure as IAM roles, not separate accounts:**

1. ✅ **1 password** for your main user
2. ✅ **5 IAM roles** with specific permissions  
3. ✅ **MFA required** for destructive operations
4. ✅ **Time limits** on all sessions
5. ✅ **Clear separation** of duties

This gives you the security benefits you want without the complexity of managing multiple accounts!