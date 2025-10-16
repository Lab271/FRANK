#!/usr/bin/env python3
"""
FRANK Platform - Simple API Test Application
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

A minimal FastAPI application for testing AWS deployment infrastructure.
Provides basic health check and root endpoints for load balancer validation.

to run:
    >>> uvicorn main:app --host 0.0.0.0 --port 8000

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timezone
from functools import lru_cache
import logging
import sys
import os
import socket
import platform
import time

import boto3
import aioboto3
from fastapi import FastAPI, Request
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import frank
from frank.util import create_error_response


# ===================================
# Logging Setup
# ===================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uvicorn.error")


# ===================================
# Container Metadata
# ===================================
def get_container_info():
    """Get container and runtime information for autoscaling identification"""
    try:
        # Get basic system info
        hostname = socket.gethostname()
        platform_info = platform.platform()
        
        # Try to get ECS task metadata (if running in Fargate)
        ecs_metadata = {}
        metadata_uri = os.environ.get('ECS_CONTAINER_METADATA_URI_V4')
        if metadata_uri:
            try:
                # In a real implementation, you'd make an HTTP request to metadata_uri
                # For now, we'll just note that it's available
                ecs_metadata = {
                    "metadata_uri_available": True,
                    "metadata_uri": metadata_uri
                }
            except Exception:
                ecs_metadata = {"metadata_uri_available": False}
        
        # Get process ID for uniqueness
        pid = os.getpid()
        
        # Calculate container uptime (approximate)
        try:
            import psutil
            process = psutil.Process(pid)
            create_time = process.create_time()
            uptime_seconds = time.time() - create_time
            uptime = f"{uptime_seconds:.1f}s"
        except Exception:
            uptime = "unknown"
        
        return {
            "hostname": hostname,
            "process_id": pid,
            "platform": platform_info,
            "ecs_metadata": ecs_metadata,
            "container_id": hostname,  # In Fargate, hostname is often the container ID
            "instance_type": "fargate" if metadata_uri else "local",
            "uptime": uptime
        }
    except Exception as e:
        return {
            "hostname": "unknown",
            "process_id": os.getpid(),
            "error": str(e),
            "container_id": "unknown",
            "instance_type": "unknown",
            "uptime": "unknown"
        }


# ===================================
# Database Setup
# ===================================
@lru_cache()
def get_client():
    """Initialize DynamoDB connection"""
    # Get configuration from environment
    table_name = os.environ.get("DYNAMODB_TABLE", "frank-stage3-data")
    audit_table_name = os.environ.get("DYNAMODB_AUDIT_TABLE", "frank-audit")
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
    endpoint = os.environ.get("ENDPOINT", None)  # None for AWS, set for LocalStack
    environment = os.environ.get("FRANK_ENVIRONMENT", "aws")    

    res = {
        "table_name": table_name,
        "audit_table_name": audit_table_name,
        "region": region,
        "endpoint": endpoint,
        "environment": environment
    }
    return res

async def get_async_dynamodb_client():
    """Get async DynamoDB client using aioboto3"""
    config = get_client()  # Get cached configuration
    session = aioboto3.Session()
    
    # Use configuration from db_config
    if config["environment"] == "aws":
        # AWS environment - use Task Role (no credentials needed)
        client = session.client(
            'dynamodb',
            region_name=config["region"]
        )
        resource = session.resource(
            'dynamodb',
            region_name=config["region"]
        )
    else:
        # LocalStack environment - use explicit credentials
        client = session.client(
            'dynamodb',
            endpoint_url=config["endpoint"],
            region_name=config["region"],
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
        )
        resource = session.resource(
            'dynamodb',
            endpoint_url=config["endpoint"],
            region_name=config["region"],
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
        )
    return (client, resource)

# ================================
# CONFIGURATION MANAGEMENT
# ================================
security = HTTPBearer(auto_error=False)  # Don't auto-raise errors

app = FastAPI(
    title="FRANK Application - Stage 3",
    description="A minimal FastAPI application for testing AWS deployment infrastructure.",
    version=frank.__version__,
    docs_url="/docs",
    redoc_url="/redoc"
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Serve static JSON on root endpoint"""
    container_info = get_container_info()
    
    return {
        "application": "FRANK",
        "version": frank.__version__,
        "status": "running",
        "message": "Welcome to FRANK application",
        "served_by": {
            "container_id": container_info["container_id"],
            "hostname": container_info["hostname"],
            "instance_type": container_info["instance_type"]
        }
    }

@app.get("/env")
async def env():
    """Environment variables endpoint"""
    config = get_client()  # Get cached configuration
    container_info = get_container_info()  # Get container metadata
    
    return {
        "container": {
            "id": container_info["container_id"],
            "hostname": container_info["hostname"],
            "process_id": container_info["process_id"],
            "instance_type": container_info["instance_type"],
            "platform": container_info["platform"]
        },
        "aws_environment": {
            "AWS_PROFILE": os.environ.get("AWS_PROFILE", "<NOT SET>"),
            "AWS_ACCESS_KEY_ID": "<NOT SET>" if not os.environ.get("AWS_ACCESS_KEY_ID") else "<SET>",
            "AWS_SECRET_ACCESS_KEY": "<NOT SET>" if not os.environ.get("AWS_SECRET_ACCESS_KEY") else "<SET>",
            "ENDPOINT": config.get("endpoint", "<NOT SET>"),
            "DYNAMODB_TABLE": config.get("table_name"),
            "DYNAMODB_AUDIT_TABLE": config.get("audit_table_name"),
            "AWS_DEFAULT_REGION": config.get("region"),
            "FRANK_ENVIRONMENT": config.get("environment"),
            "using_task_role": config.get("environment") == "aws"
        },
        "ecs_metadata": container_info["ecs_metadata"] if container_info.get("ecs_metadata") else None
    }



@app.get("/database")
async def database():
    """Database connection endpoint - uses async aioboto3"""
    config = get_client()  # Get cached configuration
    container_info = get_container_info()  # Get container metadata
    
    # Get async DynamoDB client and resource
    dynamodb_client, dynamodb_resource = await get_async_dynamodb_client()

    # Use async context managers properly
    async with dynamodb_client as client:
        # List all tables
        response = await client.list_tables()
        table_names = response.get('TableNames', [])
        
    async with dynamodb_resource as dynamodb:
        # Get table references
        main_table = await dynamodb.Table(config["table_name"])
        audit_table = await dynamodb.Table(config["audit_table_name"])
        
        # Get item counts from both tables
        main_response = await main_table.scan(Select='COUNT', Limit=1)
        main_count = main_response.get('Count', 0)
        main_status = "accessible"
        
        audit_response = await audit_table.scan(Select='COUNT', Limit=1)
        audit_count = audit_response.get('Count', 0)
        audit_status = "accessible"
    
    return {
        "status": "connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "async_implementation": "aioboto3",
        "served_by": {
            "container_id": container_info["container_id"],
            "hostname": container_info["hostname"],
            "instance_type": container_info["instance_type"]
        },
        "environment": {
            "DYNAMODB_TABLE": config["table_name"],
            "AUDIT_TABLE": config["audit_table_name"],
            "AWS_DEFAULT_REGION": config["region"],
            "ENDPOINT": config["endpoint"] or "AWS (no custom endpoint)",
            "FRANK_ENVIRONMENT": config.get("environment", "default")
        },
        "tables": {
            "available_tables": table_names,
            "main": {
                "name": config["table_name"],
                "status": main_status,
                "item_count": main_count
            },
            "audit": {
                "name": config["audit_table_name"],
                "status": audit_status,
                "item_count": audit_count
            }
        },
        "aws_credentials": {
            "using_task_role": config["environment"] == "aws",
            "using_profile": False,
            "access_key_set": bool(os.environ.get("AWS_ACCESS_KEY_ID")),
            "secret_key_set": bool(os.environ.get("AWS_SECRET_ACCESS_KEY"))
        }
    }
        
      

@app.get("/v1/health")
async def health():
    """Health check endpoint for load balancer"""
    container_info = get_container_info()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "FRANK",
        "version": frank.__version__,
        "container_id": container_info["container_id"],
        "hostname": container_info["hostname"],
        "instance_type": container_info["instance_type"]
    }


@app.get("/v1/health/deep")
async def deep_health_check():
    """Comprehensive health check for monitoring systems - NOT for load balancers"""
    container_info = get_container_info()
    config = get_client()
    start_time = datetime.now(timezone.utc)
    
    health = {
        "status": "healthy",
        "timestamp": start_time.isoformat(),
        "version": frank.__version__,
        "service": "FRANK",
        "container_id": container_info["container_id"],
        "checks": {},
        "performance": {}
    }
    
    # Check 1: Database Connectivity
    try:
        check_start = datetime.now(timezone.utc)
        
        # Check main table
        main_client, _ = await get_async_dynamodb_client()
        async with main_client as client:
            main_response = await client.describe_table(TableName=config["table_name"])
            
        # Check audit table with separate client
        audit_client, _ = await get_async_dynamodb_client()
        async with audit_client as client:
            audit_response = await client.describe_table(TableName=config["audit_table_name"])
            
        health["checks"]["dynamodb"] = {
            "status": "healthy",
            "main_table": {"name": config["table_name"], "status": main_response['Table']['TableStatus']},
            "audit_table": {"name": config["audit_table_name"], "status": audit_response['Table']['TableStatus']}
        }
        health["performance"]["dynamodb_check_duration"] = f"{(datetime.now(timezone.utc) - check_start).total_seconds():.3f}s"
        
    except Exception as e:
        health["checks"]["dynamodb"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"
    
    # Check 2: Application Components & Environment
    try:
        required_env_vars = ["DYNAMODB_TABLE", "DYNAMODB_AUDIT_TABLE", "AWS_DEFAULT_REGION"]
        missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
        
        health["checks"]["application"] = {
            "status": "healthy" if not missing_vars else "unhealthy",
            "frank_version": frank.__version__,
            "missing_env_vars": missing_vars,
            "environment": config["environment"]
        }
        
        if missing_vars:
            health["status"] = "unhealthy"
            
    except Exception as e:
        health["checks"]["application"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "unhealthy"
    
    # Performance summary
    health["performance"]["total_duration"] = f"{(datetime.now(timezone.utc) - start_time).total_seconds():.3f}s"
    health["performance"]["container_uptime"] = container_info.get("uptime", "unknown")
    
    # Set overall status based on checks
    if any(check.get("status") == "unhealthy" for check in health["checks"].values()):
        health["status"] = "unhealthy"
    elif any(check.get("status") == "degraded" for check in health["checks"].values()):
        health["status"] = "degraded"
    
    return health


@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    """Dedicated exception handler for generic exceptions."""
    return JSONResponse(
        status_code=500,
        content=create_error_response(
            500,
            "INTERNAL_ERROR",
            str(exc),
            details={"type": type(exc).__name__}
        ),
    )

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="FRANK Platform - AWS - Stage 3 Server")
    parser.add_argument(
        "--environment", choices=["localstack", "aws"], default=os.environ.get("FRANK_ENVIRONMENT", "aws"), help="Environment to run in"
    )    
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Host to bind to")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")), help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE", None), help="AWS profile to use")
    args = parser.parse_args()

    # Set environment variables before database setup
    os.environ["FRANK_ENVIRONMENT"] = args.environment
    if args.profile:
        os.environ["AWS_PROFILE"] = args.profile

    if args.debug:
        log_level = "debug"
    else:
        log_level = os.environ.get("UVICORN_LOG_LEVEL", "info")

    logger.info(f"🚀 Starting FRANK - Stage 3 on {args.host}:{args.port} | Environment: {args.environment} | Profile: {args.profile or '<NOT SET>'}")

    uvicorn.run("frank_stage3:app", host=args.host, port=args.port, reload=args.reload, log_level=log_level)
