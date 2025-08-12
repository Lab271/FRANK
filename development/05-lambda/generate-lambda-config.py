#!/usr/bin/env python3
"""
FRANK Lambda Functions Template Generator
Generates SAM templates for Lambda functions with proper configuration
"""

import yaml
import json
from pathlib import Path

def generate_lambda_template(environment='dev'):
    """Generate SAM template for FRANK Lambda functions"""
    
    template = {
        'AWSTemplateFormatVersion': '2010-09-09',
        'Transform': 'AWS::Serverless-2016-10-31',
        'Description': f'FRANK Lambda Functions for {environment}',
        
        'Parameters': {
            'Environment': {
                'Type': 'String',
                'Default': environment,
                'AllowedValues': ['dev', 'test', 'prod']
            },
            'ProjectName': {
                'Type': 'String',
                'Default': 'frank'
            }
        },
        
        'Globals': {
            'Function': {
                'Runtime': 'python3.11',
                'MemorySize': 512,
                'Timeout': 30,
                'Tracing': 'Active',
                'Environment': {
                    'Variables': {
                        'POWERTOOLS_SERVICE_NAME': 'frank',
                        'POWERTOOLS_LOG_LEVEL': 'INFO',
                        'POWERTOOLS_METRICS_NAMESPACE': 'FRANK',
                        'AWS_DEFAULT_REGION': 'eu-west-1'
                    }
                },
                'Tags': {
                    'Project': 'frank',
                    'Environment': '!Ref Environment'
                }
            }
        },
        
        'Resources': {
            # Lambda Layer for dependencies
            'DependenciesLayer': {
                'Type': 'AWS::Serverless::LayerVersion',
                'Properties': {
                    'LayerName': '!Sub frank-dependencies-${Environment}',
                    'Description': 'FRANK Lambda dependencies',
                    'ContentUri': 'layers/dependencies/',
                    'CompatibleRuntimes': ['python3.11'],
                    'RetentionPolicy': 'Delete'
                }
            },
            
            # Ingest Sightings Function
            'IngestSightingsFunction': {
                'Type': 'AWS::Serverless::Function',
                'Properties': {
                    'FunctionName': '!Sub frank-ingest-sightings-${Environment}',
                    'CodeUri': 'src/ingest_sightings/',
                    'Handler': 'lambda_function.lambda_handler',
                    'MemorySize': 512,
                    'Timeout': 30,
                    'Layers': [
                        'arn:aws:lambda:eu-west-1:017000801446:layer:AWSLambdaPowertoolsPythonV2:59',
                        '!Ref DependenciesLayer'
                    ],
                    'Environment': {
                        'Variables': {
                            'FRANK_TENANTS_TABLE': '!Sub frank-tenants-${Environment}',
                            'FRANK_IDEMPOTENCY_TABLE': '!Sub frank-idempotency-${Environment}',
                            'PROCESSING_QUEUE_URL': '!Ref ProcessingQueue'
                        }
                    },
                    'Policies': [
                        {
                            'Version': '2012-10-17',
                            'Statement': [
                                {
                                    'Effect': 'Allow',
                                    'Action': [
                                        'dynamodb:GetItem',
                                        'dynamodb:PutItem',
                                        'dynamodb:Query'
                                    ],
                                    'Resource': [
                                        '!Sub arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/frank-tenants-${Environment}',
                                        '!Sub arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/frank-idempotency-${Environment}'
                                    ]
                                },
                                {
                                    'Effect': 'Allow',
                                    'Action': [
                                        'kms:Decrypt',
                                        'kms:GenerateDataKey'
                                    ],
                                    'Resource': '*',
                                    'Condition': {
                                        'StringEquals': {
                                            'kms:EncryptionContext:Project': 'frank'
                                        }
                                    }
                                },
                                {
                                    'Effect': 'Allow',
                                    'Action': ['sqs:SendMessage'],
                                    'Resource': '!GetAtt ProcessingQueue.Arn'
                                }
                            ]
                        }
                    ]
                }
            },
            
            # Write Persistence Function
            'WritePersistenceFunction': {
                'Type': 'AWS::Serverless::Function',
                'Properties': {
                    'FunctionName': '!Sub frank-write-persistence-${Environment}',
                    'CodeUri': 'src/write_persistence/',
                    'Handler': 'lambda_function.lambda_handler',
                    'MemorySize': 1024,
                    'Timeout': 300,
                    'Layers': [
                        'arn:aws:lambda:eu-west-1:017000801446:layer:AWSLambdaPowertoolsPythonV2:59',
                        '!Ref DependenciesLayer'
                    ],
                    'Environment': {
                        'Variables': {
                            'FRANK_RAW_BUCKET': '!Sub frank-raw-${AWS::AccountId}-${Environment}',
                            'FRANK_AGGREGATES_TABLE': '!Sub frank-aggregates-${Environment}',
                            'OPENSEARCH_ENDPOINT': '!GetAtt OpenSearchDomain.DomainEndpoint'
                        }
                    },
                    'Events': {
                        'SQSEvent': {
                            'Type': 'SQS',
                            'Properties': {
                                'Queue': '!GetAtt ProcessingQueue.Arn',
                                'BatchSize': 10
                            }
                        }
                    },
                    'Policies': [
                        {
                            'S3WritePolicy': {
                                'BucketName': '!Sub frank-raw-${AWS::AccountId}-${Environment}'
                            }
                        },
                        {
                            'DynamoDBWritePolicy': {
                                'TableName': '!Sub frank-aggregates-${Environment}'
                            }
                        }
                    ]
                }
            },
            
            # Query Stats Function
            'QueryStatsFunction': {
                'Type': 'AWS::Serverless::Function',
                'Properties': {
                    'FunctionName': '!Sub frank-query-stats-${Environment}',
                    'CodeUri': 'src/query_stats/',
                    'Handler': 'lambda_function.lambda_handler',
                    'MemorySize': 256,
                    'Timeout': 30,
                    'Layers': [
                        'arn:aws:lambda:eu-west-1:017000801446:layer:AWSLambdaPowertoolsPythonV2:59',
                        '!Ref DependenciesLayer'
                    ],
                    'Environment': {
                        'Variables': {
                            'FRANK_AGGREGATES_TABLE': '!Sub frank-aggregates-${Environment}',
                            'OPENSEARCH_ENDPOINT': '!GetAtt OpenSearchDomain.DomainEndpoint'
                        }
                    },
                    'Policies': [
                        {
                            'DynamoDBReadPolicy': {
                                'TableName': '!Sub frank-aggregates-${Environment}'
                            }
                        }
                    ]
                }
            },
            
            # SIGMA Update Function
            'SigmaUpdateFunction': {
                'Type': 'AWS::Serverless::Function',
                'Properties': {
                    'FunctionName': '!Sub frank-sigma-update-${Environment}',
                    'CodeUri': 'src/sigma_update/',
                    'Handler': 'lambda_function.lambda_handler',
                    'MemorySize': 512,
                    'Timeout': 120,
                    'Layers': [
                        'arn:aws:lambda:eu-west-1:017000801446:layer:AWSLambdaPowertoolsPythonV2:59',
                        '!Ref DependenciesLayer'
                    ],
                    'Environment': {
                        'Variables': {
                            'SIGMA_WORKFLOW_ARN': '!Ref SigmaTranslateStateMachine'
                        }
                    },
                    'Events': {
                        'S3Event': {
                            'Type': 'S3',
                            'Properties': {
                                'Bucket': '!Sub frank-artifacts-${AWS::AccountId}-${Environment}',
                                'Events': 's3:ObjectCreated:*',
                                'Filter': {
                                    'S3Key': {
                                        'Rules': [
                                            {
                                                'Name': 'prefix',
                                                'Value': 'sigma-rules/'
                                            },
                                            {
                                                'Name': 'suffix',
                                                'Value': '.yml'
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    },
                    'Policies': [
                        {
                            'S3ReadPolicy': {
                                'BucketName': '!Sub frank-artifacts-${AWS::AccountId}-${Environment}'
                            }
                        },
                        {
                            'Version': '2012-10-17',
                            'Statement': [
                                {
                                    'Effect': 'Allow',
                                    'Action': ['states:StartExecution'],
                                    'Resource': '!Ref SigmaTranslateStateMachine'
                                }
                            ]
                        }
                    ]
                }
            },
            
            # SQS Queue for processing
            'ProcessingQueue': {
                'Type': 'AWS::SQS::Queue',
                'Properties': {
                    'QueueName': '!Sub frank-processing-${Environment}',
                    'VisibilityTimeoutSeconds': 360,
                    'MessageRetentionPeriod': 1209600,
                    'KmsMasterKeyId': 'alias/aws/sqs',
                    'RedrivePolicy': {
                        'deadLetterTargetArn': '!GetAtt ProcessingDLQ.Arn',
                        'maxReceiveCount': 3
                    }
                }
            },
            
            # Dead Letter Queue
            'ProcessingDLQ': {
                'Type': 'AWS::SQS::Queue',
                'Properties': {
                    'QueueName': '!Sub frank-processing-dlq-${Environment}',
                    'MessageRetentionPeriod': 1209600,
                    'KmsMasterKeyId': 'alias/aws/sqs'
                }
            }
        },
        
        'Outputs': {
            'IngestSightingsFunctionArn': {
                'Description': 'Ingest Sightings Function ARN',
                'Value': '!GetAtt IngestSightingsFunction.Arn',
                'Export': {
                    'Name': '!Sub ${ProjectName}-${Environment}-ingest-function-arn'
                }
            },
            'WritePersistenceFunctionArn': {
                'Description': 'Write Persistence Function ARN',
                'Value': '!GetAtt WritePersistenceFunction.Arn',
                'Export': {
                    'Name': '!Sub ${ProjectName}-${Environment}-persistence-function-arn'
                }
            },
            'QueryStatsFunctionArn': {
                'Description': 'Query Stats Function ARN',
                'Value': '!GetAtt QueryStatsFunction.Arn',
                'Export': {
                    'Name': '!Sub ${ProjectName}-${Environment}-query-function-arn'
                }
            }
        }
    }
    
    return template

def generate_requirements_txt():
    """Generate requirements.txt for Lambda layer"""
    requirements = [
        "pydantic==2.4.2",
        "sigma-cli==1.0.3", 
        "requests==2.31.0",
        "jsonschema==4.19.1",
        "cryptography==41.0.7",
        "opensearch-py==2.3.1",
        "boto3-stubs[dynamodb,s3,sqs,opensearch]==1.28.85"
    ]
    return "\n".join(requirements)

def generate_layer_build_script():
    """Generate script to build Lambda layer"""
    script = """#!/bin/bash
# Build Lambda layer for FRANK dependencies

set -e

LAYER_DIR="layers/dependencies"
BUILD_DIR="$LAYER_DIR/python"

# Clean up previous build
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR

# Install dependencies
pip install -r requirements.txt -t $BUILD_DIR --no-deps

# Remove unnecessary files to reduce size
find $BUILD_DIR -type d -name "__pycache__" -exec rm -rf {} +
find $BUILD_DIR -name "*.pyc" -delete
find $BUILD_DIR -name "*.pyo" -delete
find $BUILD_DIR -name "*.dist-info" -exec rm -rf {} +

echo "Lambda layer built successfully in $LAYER_DIR"
"""
    return script

if __name__ == "__main__":
    import sys
    
    env = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    
    # Generate SAM template
    template = generate_lambda_template(env)
    
    # Write template file
    with open(f'lambda-template-{env}.yaml', 'w') as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)
    
    # Write requirements.txt
    with open('requirements.txt', 'w') as f:
        f.write(generate_requirements_txt())
    
    # Write build script
    with open('build-layer.sh', 'w') as f:
        f.write(generate_layer_build_script())
    
    # Make build script executable
    Path('build-layer.sh').chmod(0o755)
    
    print(f"Generated Lambda configuration for environment: {env}")
    print("Files created:")
    print(f"  - lambda-template-{env}.yaml")
    print("  - requirements.txt")
    print("  - build-layer.sh")
