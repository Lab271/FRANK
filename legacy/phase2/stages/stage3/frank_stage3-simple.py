#!/usr/bin/env python3
"""
FRANK Platform - Simple API Test Application

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
    return {
        "application": "FRANK",
        "version": frank.__version__,
        "status": "running",
        "message": "Welcome to FRANK application"
    }

@app.get("/env")
async def env():
    """Environment variables endpoint"""
    config = get_client()  # Get cached configuration
    return {
        "AWS_PROFILE": os.environ.get("AWS_PROFILE", "<NOT SET>"),
        "AWS_ACCESS_KEY_ID": "<NOT SET>" if not os.environ.get("AWS_ACCESS_KEY_ID") else "<SET>",
        "AWS_SECRET_ACCESS_KEY": "<NOT SET>" if not os.environ.get("AWS_SECRET_ACCESS_KEY") else "<SET>",
        "ENDPOINT": config.get("endpoint", "<NOT SET>"),
        "DYNAMODB_TABLE": config.get("table_name"),
        "DYNAMODB_AUDIT_TABLE": config.get("audit_table_name"),
        "AWS_DEFAULT_REGION": config.get("region"),
        "FRANK_ENVIRONMENT": config.get("environment"),
        "using_task_role": config.get("environment") == "aws"
    }



@app.get("/database")
async def database():
    """Database connection endpoint - uses async aioboto3"""
    config = get_client()  # Get cached configuration
    
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
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "FRANK"
    }


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

    parser = argparse.ArgumentParser(description="FRANK Platform 009 - AWS - Stage 4 Server")
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

    logger.info(f"🚀 Starting FRANK 009 - Stage 3 on {args.host}:{args.port} | Environment: {args.environment} | Profile: {args.profile or '<NOT SET>'}")

    uvicorn.run("frank_stage3:app", host=args.host, port=args.port, reload=args.reload, log_level=log_level)
