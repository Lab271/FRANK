# Amazon API Gateway Configuration

## Overview
API Gateway provides the REST API interface for FRANK, handling authentication, request validation, throttling, and routing to Lambda functions.

## API Architecture

### REST API Configuration
- **API Name**: `frank-api-{env}`
- **Protocol**: HTTPS only
- **Endpoint Type**: Regional
- **Compression**: Enabled for responses > 1KB

### Stage Configuration
- **Stages**: dev, test, prod
- **Stage Variables**: Environment-specific Lambda function aliases
- **Deployment**: Automated via CloudFormation/SAM

## Endpoint Design

### 1. Sightings Endpoint
```
POST /v1/sightings
```

#### Request Configuration
- **Authorization**: Cognito User Pool authorizer
- **Required Scopes**: `sightings:write`
- **Content-Type**: `application/json`
- **Max Request Size**: 1MB

#### Request Model
```json
{
  "$schema": "http://json-schema.org/draft-04/schema#",
  "type": "object",
  "title": "Sighting Request Schema",
  "required": ["ioc_type", "ioc_value", "severity", "timestamp"],
  "properties": {
    "ioc_type": {
      "type": "string",
      "enum": ["ip", "domain", "url", "hash", "email"]
    },
    "ioc_value": {
      "type": "string",
      "minLength": 1,
      "maxLength": 2048
    },
    "severity": {
      "type": "string",
      "enum": ["low", "medium", "high", "critical"]
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "context": {
      "type": "object",
      "properties": {
        "source": {"type": "string"},
        "campaign": {"type": "string"},
        "tags": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    }
  },
  "additionalProperties": false
}
```

#### Response Models
```json
// Success Response (201)
{
  "type": "object",
  "properties": {
    "message": {"type": "string"},
    "id": {"type": "string"},
    "timestamp": {"type": "string"}
  }
}

// Error Response (400/403/500)
{
  "type": "object",
  "properties": {
    "error": {"type": "string"},
    "message": {"type": "string"},
    "timestamp": {"type": "string"}
  }
}
```

### 2. Statistics Endpoint
```
GET /v1/stats
```

#### Query Parameters
- `ioc_type` (optional): Filter by IoC type
- `sector` (optional): Filter by sector (if authorized)
- `time_range` (optional): Time range (1h, 24h, 7d, 30d)
- `granularity` (optional): Data granularity (hour, day, week)

#### Authorization
- **Required Scopes**: `stats:read`
- **Tenant Isolation**: Based on JWT claims

#### Response Model
```json
{
  "type": "object",
  "properties": {
    "statistics": {
      "type": "object",
      "properties": {
        "total_sightings": {"type": "integer"},
        "unique_iocs": {"type": "integer"},
        "time_range": {"type": "string"},
        "breakdown": {
          "type": "object",
          "properties": {
            "by_type": {"type": "object"},
            "by_severity": {"type": "object"},
            "by_time": {"type": "array"}
          }
        }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "query_time": {"type": "string"},
        "anonymized": {"type": "boolean"}
      }
    }
  }
}
```

## Authentication and Authorization

### Cognito Authorizer Configuration
```json
{
  "Type": "COGNITO_USER_POOLS",
  "Name": "FrankCognitoAuthorizer",
  "IdentitySource": "method.request.header.Authorization",
  "UserPoolArn": "arn:aws:cognito-idp:eu-west-1:{account}:userpool/{pool-id}",
  "ResultTtlInSeconds": 300
}
```

### JWT Claims Validation
```javascript
// Lambda authorizer context enhancement
{
  "tenant_id": "org-123",
  "sector": "finance", 
  "scopes": ["sightings:write", "stats:read"],
  "user_id": "user-456"
}
```

## Request/Response Transformation

### Request Mapping Templates
```vtl
## Add request context
{
  "body": $input.json('$'),
  "headers": {
    #foreach($header in $input.params().header.keySet())
    "$header": "$util.escapeJavaScript($input.params().header.get($header))"
    #if($foreach.hasNext),#end
    #end
  },
  "requestContext": {
    "requestId": "$context.requestId",
    "authorizer": {
      "claims": {
        "tenant_id": "$context.authorizer.claims.custom:tenant_id",
        "sector": "$context.authorizer.claims.custom:sector"
      }
    }
  }
}
```

### Response Mapping Templates
```vtl
## Error response mapping
#set($inputRoot = $input.path('$'))
{
  "error": "$inputRoot.errorType",
  "message": "$inputRoot.errorMessage",
  "timestamp": "$util.formatDate($context.requestTime, 'yyyy-MM-dd HH:mm:ss')",
  "requestId": "$context.requestId"
}
```

## Throttling and Usage Plans

### API-Level Throttling
- **Burst Limit**: 2000 requests
- **Rate Limit**: 1000 requests per second
- **Method-Level**: Configurable per endpoint

### Usage Plans
```json
{
  "UsagePlans": [
    {
      "PlanName": "BasicPlan",
      "Description": "Basic tier for small organizations",
      "Throttle": {
        "BurstLimit": 100,
        "RateLimit": 50
      },
      "Quota": {
        "Limit": 10000,
        "Period": "DAY"
      }
    },
    {
      "PlanName": "PremiumPlan", 
      "Description": "Premium tier for large organizations",
      "Throttle": {
        "BurstLimit": 500,
        "RateLimit": 200
      },
      "Quota": {
        "Limit": 100000,
        "Period": "DAY"
      }
    }
  ]
}
```

### API Keys
- **Generation**: Automatic per tenant
- **Rotation**: 90-day lifecycle
- **Usage Tracking**: CloudWatch metrics

## CORS Configuration

### CORS Settings
```json
{
  "CorsConfiguration": {
    "AllowOrigins": [
      "https://frank-dashboard.example.com",
      "https://frank-portal.example.com"
    ],
    "AllowMethods": ["GET", "POST", "OPTIONS"],
    "AllowHeaders": [
      "Content-Type",
      "Authorization",
      "X-Amz-Date",
      "X-Api-Key"
    ],
    "ExposeHeaders": ["X-Request-ID"],
    "MaxAge": 3600,
    "AllowCredentials": true
  }
}
```

## Request Validation

### Schema Validation
- **Enable**: Request body validation for POST endpoints
- **Schema**: JSON Schema v4
- **Error Response**: 400 Bad Request with validation details

### Custom Validators
```python
# Lambda validator for complex business rules
def validate_sighting_business_rules(sighting_data, tenant_context):
    """Custom validation beyond schema"""
    
    # Check IoC format based on type
    if sighting_data['ioc_type'] == 'ip':
        if not is_valid_ip(sighting_data['ioc_value']):
            raise ValidationError("Invalid IP address format")
    
    # Check tenant quotas
    if exceeds_daily_quota(tenant_context['tenant_id']):
        raise QuotaExceeded("Daily sighting quota exceeded")
    
    # Validate timestamp is not too old/future
    if not is_valid_timestamp(sighting_data['timestamp']):
        raise ValidationError("Timestamp out of acceptable range")
    
    return True
```

## Logging and Monitoring

### Access Logging
```json
{
  "AccessLogSettings": {
    "DestinationArn": "arn:aws:logs:eu-west-1:{account}:log-group:frank-api-access",
    "Format": "$requestId $ip $caller $user [$requestTime] \"$httpMethod $resourcePath $protocol\" $status $error.message $error.messageString $responseLength $requestTime $xrayTraceId"
  }
}
```

### Execution Logging
- **Level**: INFO for production, DEBUG for development
- **Include**: Execution details, request/response data
- **CloudWatch**: Structured logs for analysis

### Custom Metrics
```python
# Custom CloudWatch metrics
cloudwatch.put_metric_data(
    Namespace='FRANK/API',
    MetricData=[
        {
            'MetricName': 'SightingsPerTenant',
            'Dimensions': [
                {'Name': 'TenantId', 'Value': tenant_id},
                {'Name': 'Environment', 'Value': environment}
            ],
            'Value': 1,
            'Unit': 'Count'
        }
    ]
)
```

## Security Configuration

### WAF Integration
```json
{
  "WebAclArn": "arn:aws:wafv2:eu-west-1:{account}:regional/webacl/frank-api-protection/{id}"
}
```

### Security Headers
```vtl
## Response template with security headers
#set($context.responseOverride.header.X-Content-Type-Options = "nosniff")
#set($context.responseOverride.header.X-Frame-Options = "DENY")
#set($context.responseOverride.header.X-XSS-Protection = "1; mode=block")
#set($context.responseOverride.header.Strict-Transport-Security = "max-age=31536000; includeSubDomains")
```

### Resource Policies
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": "execute-api:Invoke",
      "Resource": "arn:aws:execute-api:eu-west-1:{account}:{api-id}/*",
      "Condition": {
        "StringEquals": {
          "aws:SourceVpce": "vpce-1234567890abcdef0"
        }
      }
    }
  ]
}
```

## Caching Strategy

### Response Caching
- **TTL**: 300 seconds for statistics endpoints
- **Cache Key**: Include tenant_id, query parameters
- **Invalidation**: On data updates

### CloudFront Integration
```yaml
CloudFrontDistribution:
  Properties:
    DistributionConfig:
      Origins:
        - DomainName: !Sub "${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com"
          Id: api-gateway-origin
          OriginPath: /prod
          CustomOriginConfig:
            HTTPPort: 443
            OriginProtocolPolicy: https-only
      DefaultCacheBehavior:
        TargetOriginId: api-gateway-origin
        ViewerProtocolPolicy: redirect-to-https
        CachePolicyId: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad  # Managed-CachingDisabled
        OriginRequestPolicyId: 88a5eaf4-2fd4-4709-b370-b4c650ea3fcf  # Managed-CORS-S3Origin
```

## Error Handling

### Gateway Responses
```json
{
  "GatewayResponses": {
    "UNAUTHORIZED": {
      "StatusCode": "401",
      "ResponseTemplates": {
        "application/json": "{\"error\":\"Unauthorized\",\"message\":\"Authentication required\"}"
      }
    },
    "ACCESS_DENIED": {
      "StatusCode": "403", 
      "ResponseTemplates": {
        "application/json": "{\"error\":\"Forbidden\",\"message\":\"Insufficient permissions\"}"
      }
    },
    "THROTTLED": {
      "StatusCode": "429",
      "ResponseTemplates": {
        "application/json": "{\"error\":\"Too Many Requests\",\"message\":\"Rate limit exceeded\"}"
      }
    }
  }
}
```

## Environment Configuration

### Stage Variables
```json
{
  "StageVariables": {
    "lambda_alias": "${Environment}",
    "log_level": "INFO",
    "cache_ttl": "300"
  }
}
```

### Environment-Specific Settings
- **dev**: Debug logging, no caching, relaxed throttling
- **test**: Production-like settings with test data
- **prod**: Full security, caching, strict throttling

## Implementation Checklist
- [ ] Create REST API with proper naming
- [ ] Configure Cognito authorizer
- [ ] Define request/response models and validation
- [ ] Set up method configurations for each endpoint
- [ ] Configure CORS for web applications
- [ ] Set up throttling and usage plans
- [ ] Create API keys for tenants
- [ ] Configure logging (access and execution)
- [ ] Set up CloudWatch alarms for monitoring
- [ ] Deploy to stages (dev, test, prod)
- [ ] Test authentication and authorization
- [ ] Validate request/response transformations
- [ ] Set up WAF protection
- [ ] Configure custom domain names
- [ ] Test error handling scenarios
