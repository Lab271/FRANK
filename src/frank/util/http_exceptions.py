
"""
FRANK Platform - HTTP Exception Utilities

Custom exception classes and error response utility for API error handling.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from frank.core import gen_stix_id

#########################
# Exceptions
#########################

class BadRequestException(HTTPException):
    """Exception for HTTP 400 Bad Request"""

    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UnauthenticatedException(HTTPException):
    """Exception for HTTP 401 Unauthenticated"""

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
        )


class UnauthorizedException(HTTPException):
    """Exception for HTTP 403 Unauthorized/Forbidden"""

    def __init__(self, detail: str = "Forbidden: insufficient permissions"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail, headers={"WWW-Authenticate": "Bearer"})


class NotFoundException(HTTPException):
    """Exception for HTTP 404 Not Found"""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class TooManyRequestsException(HTTPException):
    """Exception for HTTP 429 Too Many Requests (Rate Limit Exceeded)"""

    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


class InternalError(HTTPException):
    """Custom HTTPException extension for internal server errors"""

    def __init__(self, detail: str = "Custom internal server error"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class ServiceUnavailableException(HTTPException):
    """Exception for HTTP 503 Service Unavailable"""

    def __init__(self, detail: str = "Service temporarily unavailable"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class GatewayTimeoutException(HTTPException):
    """Exception for HTTP 504 Gateway Timeout"""

    def __init__(self, detail: str = "Gateway timeout"):
        super().__init__(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
#######################
# Helper functions
#######################
def create_error_response(
		status_code: int,
		error_type: str,
		message: str,
		request_id: Optional[str] = None,
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
			"request_id": request_id or gen_stix_id("req")
		}
	}
