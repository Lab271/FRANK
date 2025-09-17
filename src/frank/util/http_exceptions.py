
"""
FRANK Platform - HTTP Exception Utilities

Custom exception classes and error response utility for API error handling.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException

class BadRequestException(HTTPException):
	"""Exception for HTTP 400 Bad Request"""
	def __init__(self, detail: str = "Bad request"):
		super().__init__(status_code=400, detail=detail)

class NotFoundException(HTTPException):
	"""Exception for HTTP 404 Not Found"""
	def __init__(self, detail: str = "Resource not found"):
		super().__init__(status_code=404, detail=detail)

class UnauthenticatedException(HTTPException):
	"""Exception for HTTP 401 Unauthenticated"""
	def __init__(self, detail: str = "Authentication required"):
		super().__init__(status_code=401, detail=detail)

class UnauthorizedException(HTTPException):
	"""Exception for HTTP 403 Unauthorized/Forbidden"""
	def __init__(self, detail: str = "Forbidden: insufficient permissions"):
		super().__init__(status_code=403, detail=detail)
		
class TooManyRequestsException(HTTPException):
	"""Exception for HTTP 429 Too Many Requests (Rate Limit Exceeded)"""
	def __init__(self, detail: str = "Rate limit exceeded"):
		super().__init__(status_code=429, detail=detail)

def create_error_response(
		status_code: int,
		error_type: str,
		message: str,
		details: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
	"""Create a standardized error response dict for API errors."""
	return {
		"error": {
			"type": error_type,
			"status_code": status_code,
			"message": message,
			"details": details or {},
			"timestamp": datetime.now(timezone.utc).isoformat(),
			"request_id": f"req-{uuid.uuid4()}"
		}
	}
