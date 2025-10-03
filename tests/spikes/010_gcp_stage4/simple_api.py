#!/usr/bin/env python3
"""
FRANK Platform - Simple API Test Application for GCP

A minimal FastAPI application for testing GCP deployment infrastructure.
Provides basic health check, root, and data endpoints for load balancer validation.

to run:
    >>> uvicorn simple_api:app --host 0.0.0.0 --port 8000

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone
import os
import frank
from google.cloud import firestore

app = FastAPI(title="FRANK Application on GCP")

# Initialize Firestore client
try:
    db = firestore.Client()
except Exception as e:
    # Handle exceptions during client initialization, e.g., credentials not found
    print(f"Error initializing Firestore client: {e}")
    db = None

@app.get("/")
async def root():
    """Serve static JSON on root endpoint"""
    return {
        "application": "FRANK",
        "version": frank.__version__,
        "status": "running",
        "message": "Welcome to FRANK application on GCP"
    }

@app.get("/v1/health")
async def health():
    """Health check endpoint for load balancer"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "FRANK on GCP"
    }

@app.post("/v1/data/{document_id}")
async def create_data(document_id: str, data: dict):
    """Create a document in Firestore"""
    if not db:
        raise HTTPException(status_code=500, detail="Firestore client not initialized")
    try:
        doc_ref = db.collection('frank_data').document(document_id)
        doc_ref.set(data)
        return {"status": "success", "document_id": document_id, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/data/{document_id}")
async def read_data(document_id: str):
    """Read a document from Firestore"""
    if not db:
        raise HTTPException(status_code=500, detail="Firestore client not initialized")
    try:
        doc_ref = db.collection('frank_data').document(document_id)
        doc = doc_ref.get()
        if doc.exists:
            return {"status": "success", "document_id": document_id, "data": doc.to_dict()}
        else:
            raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
