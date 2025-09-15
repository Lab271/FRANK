#!/usr/bin/env python3
"""
FRANK Platform - FastAPI Spike Test Module

Standalone FastAPI test module with several endpoints and exception handling.
Demonstrates:
  1. Simple GET (no parameters, returns 200)
  2. Simple GET (with two parameters, returns 200)
  3. Simple POST (with Pydantic body, returns 200)
  4. Simple GET (raises Exception, returns 500)
  5. Simple GET (variable in URL, returns 400)

Includes testability and dedicated exception handlers.
Testable via test_spike_run method (pytest compatible, supports mocks).

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from fastapi.security import HTTPBearer

app = FastAPI(
    title="007 FastAPI Test spike",
    description="Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling",
    version="0.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)  # Don't auto-raise errors


class Item(BaseModel):
	name: str
	value: Optional[int] = None

@app.get("/call1")
def call1():
	"""Simple GET, no parameters, returns 200."""
	return {"result": "ok"}

@app.get("/call2")
def call2(param1: str, param2: int):
	"""Simple GET with two parameters, returns 200."""
	return {"param1": param1, "param2": param2}

@app.post("/call3")
def call3(item: Item):
	"""Simple POST with Pydantic body, returns 200."""
	return {"received": item.model_dump()}

@app.get("/call4")
def call4():
	"""Simple GET raising an Exception, returns 500."""
	raise Exception("Intentional error for test")

@app.get("/call5/{id}/test")
def call5(id: int):
	"""Simple GET with variable in URL, returns 400 if id < 0."""
	if id < 0:
		raise HTTPException(status_code=400, detail="ID must be non-negative")
	return {"id": id, "status": "ok"}

@app.get("/call6")
def call6(credentials: HTTPAuthorizationCredentials = Depends(security)):
	"""GET requiring HTTPAuthorizationCredentials, returns 401 if missing/invalid."""
	if not credentials or credentials.credentials != "validtoken":
		raise HTTPException(status_code=401, detail="Invalid or missing token")
	return {"auth": "success"}

@app.get("/call7")
def call7(q: str = Query(..., min_length=3, max_length=20, description="Search query string")):
	"""GET using FastAPI Query for parameter validation and docs."""
	return {"query": q, "length": len(q)}

@app.post("/call8")
def call8(data: dict = Body(..., description="Arbitrary JSON body")):
	"""POST using FastAPI Body for parameter validation and docs."""
	return {"received": data, "keys": list(data.keys())}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": f"req-{uuid.uuid4()}",
            }
        },
    )

@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
	"""Dedicated exception handler for generic exceptions."""
	return JSONResponse(status_code=500, content={"status_code": 500, "error": str(exc)})

# Testability: pytest compatible test function

def test_spike_run():
	"""Pytest-compatible test for FastAPI spike endpoints.
	
	# 1. Simple GET no parameters
	curl -s -X GET http://localhost:8000/call1 | jq
	# 2. Simple GET with two parameters
	curl -s -X GET 'http://localhost:8000/call2?param1=foo&param2=42' | jq
	# 3. Simple POST with Pydantic body
	curl -s -X POST http://localhost:8000/call3 -H 'Content-Type: application/json' -d '{"name": "bar", "value": 99}' | jq
	# 4. Simple GET raising Exception
	curl -s -i -X GET http://localhost:8000/call4
	# 5. Simple GET with variable in URL
	curl -s -X GET http://localhost:8000/call5/123/test | jq
	curl -s -X GET http://localhost:8000/call5/-1/test | jq
	# 6. Auth required (HTTPAuthorizationCredentials)
	curl -s -X GET http://localhost:8000/call6 | jq
	curl -s -X GET http://localhost:8000/call6 -H 'Authorization: Bearer badtoken' | jq
	curl -s -X GET http://localhost:8000/call6 -H 'Authorization: Bearer validtoken' | jq
	# 7. FastAPI Query
	curl -s -X GET 'http://localhost:8000/call7?q=searchterm' | jq
	curl -s -X GET 'http://localhost:8000/call7?q=ab' | jq
	# 8. FastAPI Body
	curl -s -X POST http://localhost:8000/call8 -H 'Content-Type: application/json' -d '{"foo": "bar", "baz": 123}' | jq



	"""
	from fastapi.testclient import TestClient
	client = TestClient(app)

	# 1. Simple GET no parameters
	print("curl -s -X GET http://localhost:8000/call1 | jq")
	resp1 = client.get("/call1")
	assert resp1.status_code == 200
	assert resp1.json()["result"] == "ok"

	# 2. Simple GET with two parameters
	print("curl -s -X GET 'http://localhost:8000/call2?param1=foo&param2=42' | jq")
	resp2 = client.get("/call2", params={"param1": "foo", "param2": 42})
	assert resp2.status_code == 200
	assert resp2.json()["param1"] == "foo"
	assert resp2.json()["param2"] == 42

	# 3. Simple POST with Pydantic body
	print("curl -s -X POST http://localhost:8000/call3 -H 'Content-Type: application/json' -d '{\"name\": \"bar\", \"value\": 99}' | jq")
	resp3 = client.post("/call3", json={"name": "bar", "value": 99})
	assert resp3.status_code == 200
	assert resp3.json()["received"]["name"] == "bar"
	assert resp3.json()["received"]["value"] == 99

	# # 4. Simple GET raising Exception
	# print("curl -s -i -X GET http://localhost:8000/call4")
	# resp4 = client.get("/call4")
	# assert resp4.status_code == 500
	# assert "Intentional error" in resp4.json()["error"]

	# # 5. Simple GET with variable in URL
	# print("curl -s -X GET http://localhost:8000/call5/123/test | jq")
	# print("curl -s -X GET http://localhost:8000/call5/-1/test | jq")
	# resp5_ok = client.get("/call5/123/test")
	# assert resp5_ok.status_code == 200
	# assert resp5_ok.json()["id"] == 123
	# resp5_bad = client.get("/call5/-1/test")
	# assert resp5_bad.status_code == 400
	# assert "ID must be non-negative" in resp5_bad.json()["detail"]

	# # 6. Auth required (HTTPAuthorizationCredentials)
	# print("curl -s -X GET http://localhost:8000/call6 | jq")
	# print("curl -s -X GET http://localhost:8000/call6 -H 'Authorization: Bearer badtoken' | jq")
	# print("curl -s -X GET http://localhost:8000/call6 -H 'Authorization: Bearer validtoken' | jq")
	# resp6_noauth = client.get("/call6")
	# assert resp6_noauth.status_code == 401
	# assert "Invalid or missing token" in resp6_noauth.json()["detail"]
	# resp6_bad = client.get("/call6", headers={"Authorization": "Bearer badtoken"})
	# assert resp6_bad.status_code == 401
	# assert "Invalid or missing token" in resp6_bad.json()["detail"]
	# resp6_ok = client.get("/call6", headers={"Authorization": "Bearer validtoken"})
	# assert resp6_ok.status_code == 200
	# assert resp6_ok.json()["auth"] == "success"

	# # 7. FastAPI Query
	# print("curl -s -X GET 'http://localhost:8000/call7?q=searchterm' | jq")
	# print("curl -s -X GET 'http://localhost:8000/call7?q=ab' | jq")
	# resp7 = client.get("/call7", params={"q": "searchterm"})
	# assert resp7.status_code == 200
	# assert resp7.json()["query"] == "searchterm"
	# assert resp7.json()["length"] == len("searchterm")
	# resp7_short = client.get("/call7", params={"q": "ab"})
	# assert resp7_short.status_code == 422  # min_length=3

	# # 8. FastAPI Body
	# print("curl -s -X POST http://localhost:8000/call8 -H 'Content-Type: application/json' -d '{\"foo\": \"bar\", \"baz\": 123}' | jq")
	# resp8 = client.post("/call8", json={"foo": "bar", "baz": 123})
	# assert resp8.status_code == 200
	# assert resp8.json()["received"]["foo"] == "bar"
	# assert "baz" in resp8.json()["keys"]
	


if __name__ == '__main__':
    # Run the server
    uvicorn.run(
        "007_fastapi_test:app",
        # app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )