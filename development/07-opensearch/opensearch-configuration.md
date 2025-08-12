# Amazon OpenSearch Service Configuration

## Overview
OpenSearch provides search, analytics, and visualization capabilities for FRANK's security sightings data. It enables interactive dashboards, complex queries, and real-time monitoring of threat intelligence.

## Domain Architecture

### OpenSearch Domain Configuration
- **Name**: `frank-{env}`
- **Version**: OpenSearch 2.3 (latest stable)
- **Deployment**: VPC-based for security
- **Access**: Fine-grained access control (FGAC)

### Node Configuration

#### Development Environment
```yaml
NodeConfig:
  InstanceType: t3.small.search
  InstanceCount: 1
  DedicatedMasterEnabled: false
  Storage:
    VolumeType: gp3
    VolumeSize: 20
```

#### Production Environment
```yaml
NodeConfig:
  InstanceType: m6g.large.search
  InstanceCount: 3
  DedicatedMasterEnabled: true
  MasterInstanceType: m6g.medium.search
  MasterInstanceCount: 3
  Storage:
    VolumeType: gp3
    VolumeSize: 100
    IOPS: 3000
```

### Network Configuration

#### VPC Setup
```yaml
VPCOptions:
  SecurityGroupIds:
    - sg-opensearch-access
  SubnetIds:
    - subnet-private-1a
    - subnet-private-1b
    - subnet-private-1c
```

#### Security Group Rules
```yaml
SecurityGroupRules:
  Ingress:
    - Protocol: tcp
      Port: 443
      Source: sg-lambda-functions
      Description: "Lambda access to OpenSearch"
    - Protocol: tcp
      Port: 443
      Source: sg-vpc-endpoints
      Description: "VPC endpoint access"
```

## Index Strategy

### Index Templates

#### Sightings Index Template
```json
{
  "index_patterns": ["frank-sightings-*"],
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1,
      "refresh_interval": "30s",
      "index.lifecycle.name": "frank-sightings-policy",
      "index.lifecycle.rollover_alias": "frank-sightings"
    },
    "mappings": {
      "properties": {
        "ioc_value_hash": {
          "type": "keyword"
        },
        "ioc_type": {
          "type": "keyword"
        },
        "severity": {
          "type": "keyword"
        },
        "timestamp": {
          "type": "date",
          "format": "strict_date_optional_time"
        },
        "tenant_id_hash": {
          "type": "keyword"
        },
        "sector": {
          "type": "keyword"
        },
        "confidence": {
          "type": "byte"
        },
        "tags": {
          "type": "keyword"
        },
        "source": {
          "type": "keyword"
        },
        "context": {
          "type": "object",
          "enabled": false
        },
        "location": {
          "type": "geo_point"
        }
      }
    }
  }
}
```

#### SIGMA Rules Index Template
```json
{
  "index_patterns": ["frank-sigma-*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 1
    },
    "mappings": {
      "properties": {
        "rule_id": {
          "type": "keyword"
        },
        "title": {
          "type": "text",
          "analyzer": "standard"
        },
        "description": {
          "type": "text"
        },
        "tags": {
          "type": "keyword"
        },
        "level": {
          "type": "keyword"
        },
        "status": {
          "type": "keyword"
        },
        "author": {
          "type": "keyword"
        },
        "detection": {
          "type": "object",
          "enabled": false
        },
        "created": {
          "type": "date"
        },
        "modified": {
          "type": "date"
        },
        "version": {
          "type": "keyword"
        }
      }
    }
  }
}
```

### Index Lifecycle Management (ILM)

#### Sightings Data Lifecycle
```json
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "5GB",
            "max_age": "7d"
          },
          "set_priority": {
            "priority": 100
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "allocate": {
            "number_of_replicas": 0
          },
          "set_priority": {
            "priority": 50
          }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "allocate": {
            "number_of_replicas": 0
          },
          "set_priority": {
            "priority": 0
          }
        }
      },
      "delete": {
        "min_age": "365d"
      }
    }
  }
}
```

## Security Configuration

### Encryption
- **At Rest**: Customer-managed KMS key
- **In Transit**: TLS 1.2 for all communications
- **Node-to-Node**: Enabled within cluster

### Fine-Grained Access Control (FGAC)

#### Master User Configuration
```yaml
AdvancedSecurityOptions:
  Enabled: true
  InternalUserDatabaseEnabled: false
  MasterUserOptions:
    MasterUserARN: "arn:aws:iam::{account}:role/frank-opensearch-master-role"
```

#### Role-Based Access

**Tenant Reader Role**
```json
{
  "cluster_permissions": [],
  "index_permissions": [
    {
      "index_patterns": ["frank-sightings-{tenant_id}-*"],
      "allowed_actions": [
        "indices:data/read/*",
        "indices:admin/mappings/get*"
      ]
    }
  ]
}
```

**Analytics Role**
```json
{
  "cluster_permissions": [
    "cluster:monitor/*"
  ],
  "index_permissions": [
    {
      "index_patterns": ["frank-sightings-*"],
      "allowed_actions": [
        "indices:data/read/*",
        "indices:admin/mappings/get*"
      ],
      "field_level_security": {
        "grant": ["*"],
        "except": ["tenant_id_hash", "source_ip"]
      }
    }
  ]
}
```

**Lambda Writer Role**
```json
{
  "cluster_permissions": [
    "cluster:admin/ingest/pipeline/put",
    "cluster:admin/ingest/pipeline/get"
  ],
  "index_permissions": [
    {
      "index_patterns": ["frank-sightings-*", "frank-sigma-*"],
      "allowed_actions": [
        "indices:data/write/*",
        "indices:admin/create",
        "indices:admin/mapping/put"
      ]
    }
  ]
}
```

## Data Ingestion Pipeline

### Ingest Pipeline for Sightings
```json
{
  "description": "Process sighting data for indexing",
  "processors": [
    {
      "set": {
        "field": "ingestion_timestamp",
        "value": "{{_ingest.timestamp}}"
      }
    },
    {
      "script": {
        "lang": "painless",
        "source": "ctx.day_of_week = ZonedDateTime.parse(ctx.timestamp).getDayOfWeek().getValue()"
      }
    },
    {
      "geoip": {
        "field": "source_ip",
        "target_field": "location",
        "ignore_missing": true
      }
    },
    {
      "remove": {
        "field": ["source_ip"],
        "ignore_missing": true
      }
    }
  ]
}
```

### Lambda Integration
```python
from opensearchpy import OpenSearch, RequestsHttpConnection
from aws_requests_auth.aws_auth import AWSRequestsAuth
import json
import os

def get_opensearch_client():
    """Create authenticated OpenSearch client"""
    host = os.environ['OPENSEARCH_ENDPOINT'].replace('https://', '')
    region = os.environ['AWS_REGION']
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWSRequestsAuth(credentials, region, service)
    
    client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client

def index_sighting(sighting_data, tenant_id):
    """Index a sighting document"""
    client = get_opensearch_client()
    
    # Create index name with date rollover
    index_name = f"frank-sightings-{tenant_id}-{datetime.now().strftime('%Y-%m')}"
    
    # Index document
    response = client.index(
        index=index_name,
        body=sighting_data,
        pipeline="frank-sightings-pipeline"
    )
    
    return response
```

## Dashboard Configuration

### OpenSearch Dashboards

#### Sightings Overview Dashboard
```json
{
  "objects": [
    {
      "type": "visualization",
      "id": "sightings-timeline",
      "attributes": {
        "title": "Sightings Timeline",
        "type": "line",
        "params": {
          "grid": {"categoryLines": false, "style": {"color": "#eee"}},
          "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "bottom"}],
          "valueAxes": [{"id": "ValueAxis-1", "type": "value", "position": "left"}]
        }
      }
    },
    {
      "type": "visualization", 
      "id": "severity-distribution",
      "attributes": {
        "title": "Severity Distribution",
        "type": "pie",
        "params": {
          "addTooltip": true,
          "addLegend": true,
          "legendPosition": "right"
        }
      }
    }
  ]
}
```

#### Threat Intelligence Dashboard
```json
{
  "objects": [
    {
      "type": "visualization",
      "id": "ioc-types-breakdown",
      "attributes": {
        "title": "IoC Types Breakdown",
        "type": "histogram",
        "params": {
          "grid": {"categoryLines": false},
          "categoryAxes": [{"id": "CategoryAxis-1", "type": "category"}],
          "valueAxes": [{"id": "ValueAxis-1", "type": "value"}]
        }
      }
    },
    {
      "type": "visualization",
      "id": "geographic-distribution", 
      "attributes": {
        "title": "Geographic Distribution",
        "type": "tile_map",
        "params": {
          "mapType": "Scaled Circle Markers",
          "addTooltip": true
        }
      }
    }
  ]
}
```

## Performance Optimization

### Query Optimization

#### Common Query Patterns
```python
# Time-range queries with aggregations
query = {
    "size": 0,
    "query": {
        "bool": {
            "filter": [
                {"range": {"timestamp": {"gte": "now-24h"}}},
                {"term": {"sector": "finance"}}
            ]
        }
    },
    "aggs": {
        "severity_breakdown": {
            "terms": {"field": "severity"}
        },
        "hourly_trends": {
            "date_histogram": {
                "field": "timestamp",
                "calendar_interval": "hour"
            }
        }
    }
}

# Search for similar IoCs
similarity_query = {
    "query": {
        "more_like_this": {
            "fields": ["ioc_value_hash", "tags"],
            "like": [{"_index": "frank-sightings-*", "_id": "doc_id"}],
            "min_term_freq": 1,
            "max_query_terms": 12
        }
    }
}
```

### Caching Strategy
```yaml
IndexSettings:
  "index.queries.cache.enabled": true
  "index.requests.cache.enable": true
  "index.refresh_interval": "30s"
```

## Monitoring and Alerting

### CloudWatch Metrics
- **Cluster Health**: Red/Yellow/Green status
- **Search Latency**: Query response times
- **Indexing Rate**: Documents per second
- **Storage Usage**: Disk utilization per node

### Custom Metrics
```python
# Custom metric for data freshness
def publish_data_freshness_metric():
    latest_doc = client.search(
        index="frank-sightings-*",
        body={
            "size": 1,
            "sort": [{"timestamp": {"order": "desc"}}]
        }
    )
    
    if latest_doc['hits']['hits']:
        latest_timestamp = latest_doc['hits']['hits'][0]['_source']['timestamp']
        freshness_minutes = (datetime.now() - datetime.fromisoformat(latest_timestamp)).total_seconds() / 60
        
        cloudwatch.put_metric_data(
            Namespace='FRANK/OpenSearch',
            MetricData=[{
                'MetricName': 'DataFreshnessMinutes',
                'Value': freshness_minutes,
                'Unit': 'Count'
            }]
        )
```

### Alerts
```yaml
Alerts:
  - Name: OpenSearchClusterRed
    Condition: ClusterStatus.red >= 1
    Action: SNS notification + auto-recovery
    
  - Name: HighSearchLatency
    Condition: SearchLatency > 5000ms
    Action: Scale up cluster
    
  - Name: LowDiskSpace
    Condition: StorageUtilization > 85%
    Action: Add storage or scale out
```

## Backup and Recovery

### Snapshot Configuration
```json
{
  "snapshot_repository": {
    "type": "s3",
    "settings": {
      "bucket": "frank-opensearch-snapshots-{env}",
      "region": "eu-west-1",
      "role_arn": "arn:aws:iam::{account}:role/frank-opensearch-snapshot-role",
      "server_side_encryption": true
    }
  }
}
```

### Snapshot Schedule
```python
# Automated snapshot creation
def create_snapshot():
    snapshot_name = f"frank-snapshot-{datetime.now().strftime('%Y-%m-%d-%H-%M')}"
    
    client.snapshot.create(
        repository='frank-snapshots',
        snapshot=snapshot_name,
        body={
            "indices": "frank-sightings-*,frank-sigma-*",
            "ignore_unavailable": True,
            "include_global_state": False,
            "metadata": {
                "taken_by": "automated-backup",
                "taken_because": "scheduled"
            }
        }
    )
```

## Cost Optimization

### Storage Optimization
- **Index Lifecycle Management**: Automatic data tiering
- **Compression**: Enable best_compression codec
- **Rollover**: Size and age-based index rollover

### Compute Optimization
- **Reserved Instances**: For predictable workloads
- **Right-sizing**: Monitor CPU and memory usage
- **Auto-scaling**: Based on search latency and queue depth

## Environment Variables
```bash
# OpenSearch Configuration
OPENSEARCH_ENDPOINT=https://frank-dev.eu-west-1.es.amazonaws.com
OPENSEARCH_INDEX_PREFIX=frank-sightings
OPENSEARCH_PIPELINE_NAME=frank-sightings-pipeline

# Security
OPENSEARCH_MASTER_ROLE_ARN=arn:aws:iam::{account}:role/frank-opensearch-master-role
OPENSEARCH_KMS_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{key-id}

# Networking
OPENSEARCH_VPC_ID=vpc-12345678
OPENSEARCH_SUBNET_IDS=subnet-12345,subnet-67890,subnet-abcde
OPENSEARCH_SECURITY_GROUP_ID=sg-opensearch-access
```

## Implementation Checklist
- [ ] Create VPC and subnets for OpenSearch
- [ ] Set up security groups with proper rules
- [ ] Create KMS key for encryption
- [ ] Deploy OpenSearch domain via CloudFormation
- [ ] Configure fine-grained access control
- [ ] Create index templates and lifecycle policies
- [ ] Set up ingest pipelines
- [ ] Configure Lambda integration
- [ ] Create OpenSearch Dashboards
- [ ] Set up monitoring and alerting
- [ ] Configure automated snapshots
- [ ] Test search and analytics functionality
- [ ] Optimize performance and costs
- [ ] Document operational procedures
