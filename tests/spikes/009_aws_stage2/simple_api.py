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

from fastapi import FastAPI
from datetime import datetime, timezone
import sys
import os

import frank

app = FastAPI(title="FRANK Application")

@app.get("/")
async def root():
    """Serve static JSON on root endpoint"""
    return {
        "application": "FRANK - Stage2",
        "version": frank.__version__,
        "status": "running",
        "message": "Welcome to FRANK application"
    }

@app.get("/v1/health")
async def health():
    """Health check endpoint for load balancer"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "FRANK"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)