#!/usr/bin/env python3
"""
008_aws_spike.py - Simple FastAPI Application for AWS Deployment Spike

A minimal FastAPI application demonstrating:
- HTML endpoint on /
- JSON API endpoint on /v1/hello
- Health check endpoint on /health

This app is designed for AWS ECS deployment testing without dependencies
on complex FRANK models or database integrations.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Application metadata
APP_VERSION = "1.0.0"
APP_NAME = "FRANK AWS Spike"
ENVIRONMENT = os.getenv("FRANK_ENVIRONMENT", "aws")

# Create FastAPI app
app = FastAPI(
    title=APP_NAME,
    description="Simple FastAPI application for AWS ECS deployment testing",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root endpoint serving HTML "Hello World" response.
    """
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{APP_NAME}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #2c3e50;
                text-align: center;
            }}
            .info {{
                background-color: #ecf0f1;
                padding: 20px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .status {{
                color: #27ae60;
                font-weight: bold;
            }}
            .links {{
                text-align: center;
                margin-top: 30px;
            }}
            .links a {{
                margin: 0 15px;
                color: #3498db;
                text-decoration: none;
            }}
            .links a:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Hello World from {APP_NAME}!</h1>
            
            <div class="info">
                <p><strong>Status:</strong> <span class="status">✅ Running Successfully</span></p>
                <p><strong>Version:</strong> {APP_VERSION}</p>
                <p><strong>Environment:</strong> {ENVIRONMENT}</p>
                <p><strong>Current Time:</strong> {current_time}</p>
                <p><strong>Description:</strong> This is a simple FastAPI application designed for AWS ECS deployment testing.</p>
            </div>
            
            <h2>Available Endpoints:</h2>
            <ul>
                <li><strong>GET /</strong> - This HTML page</li>
                <li><strong>GET /v1/hello</strong> - JSON API endpoint</li>
                <li><strong>GET /health</strong> - Health check endpoint</li>
                <li><strong>GET /docs</strong> - Interactive API documentation</li>
            </ul>
            
            <div class="links">
                <a href="/v1/hello">JSON API</a>
                <a href="/health">Health Check</a>
                <a href="/docs">API Docs</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    logger.info("Root endpoint accessed")
    return html_content

@app.get("/v1/hello")
async def json_hello() -> Dict[str, Any]:
    """
    JSON API endpoint returning hello world response.
    """
    current_time = datetime.now(timezone.utc).isoformat()
    
    response = {
        "message": "Hello World from FRANK AWS Spike!",
        "service": APP_NAME,
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "timestamp": current_time,
        "status": "success",
        "data": {
            "greeting": "Hello World",
            "description": "Simple JSON API endpoint for AWS deployment testing",
            "endpoints": [
                {"method": "GET", "path": "/", "description": "HTML hello world page"},
                {"method": "GET", "path": "/v1/hello", "description": "JSON API endpoint"},
                {"method": "GET", "path": "/health", "description": "Health check endpoint"},
                {"method": "GET", "path": "/docs", "description": "Interactive API documentation"}
            ]
        }
    }
    
    logger.info("JSON API endpoint accessed")
    return response

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for load balancer monitoring.
    
    Returns HTTP 200 with service status information.
    This endpoint is used by AWS Application Load Balancer for health checks.
    """
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Basic health checks
    health_status = {
        "status": "healthy",
        "service": APP_NAME,
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "timestamp": current_time,
        "uptime": "unknown",  # Could be enhanced with actual uptime tracking
        "checks": {
            "api": "ok",
            "memory": "ok",
            "disk": "ok"
        }
    }
    
    logger.info("Health check endpoint accessed")
    return health_status

@app.get("/info")
async def app_info() -> Dict[str, Any]:
    """
    Application information endpoint.
    
    Returns detailed information about the application and environment.
    """
    return {
        "application": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "description": "Simple FastAPI application for AWS ECS deployment testing"
        },
        "environment": {
            "frank_environment": ENVIRONMENT,
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            "platform": os.name,
        },
        "configuration": {
            "cors_enabled": True,
            "docs_enabled": True,
            "logging_level": "INFO"
        },
        "endpoints": {
            "root": {"path": "/", "method": "GET", "type": "HTML"},
            "json_api": {"path": "/v1/hello", "method": "GET", "type": "JSON"},
            "health": {"path": "/health", "method": "GET", "type": "JSON"},
            "info": {"path": "/info", "method": "GET", "type": "JSON"},
            "docs": {"path": "/docs", "method": "GET", "type": "HTML"},
        }
    }

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler"""
    return {
        "error": "Not Found",
        "message": f"Endpoint not found: {request.url.path}",
        "service": APP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "available_endpoints": ["/", "/v1/hello", "/health", "/info", "/docs"]
    }

@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    """Custom 500 handler"""
    logger.error(f"Internal server error: {exc}")
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "service": APP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    """
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info("Application startup complete")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.
    """
    logger.info(f"Shutting down {APP_NAME}")

# Main entry point
if __name__ == "__main__":
    # Configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    logger.info(f"Starting {APP_NAME} on {host}:{port}")
    
    # Run the application
    uvicorn.run(
        "008_aws_spike:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        reload=False  # Set to True for development
    )