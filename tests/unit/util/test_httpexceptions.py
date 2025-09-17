"""
FRANK Platform - Unit Tests for HTTP Exception Utilities

Unit tests for custom exception classes and error response utility.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from datetime import datetime, timezone
from uuid import UUID
from frank.util.http_exceptions import (
    BadRequestException,
    UnauthenticatedException,
    UnauthorizedException,
    create_error_response
)

class TestHttpExceptions(unittest.TestCase):
    """Test custom HTTP exception classes."""
    def test_bad_request_exception(self):
        """BadRequestException sets status_code and detail."""
        exc = BadRequestException("bad req")
        self.assertEqual(exc.status_code, 400)
        self.assertEqual(exc.detail, "bad req")

    def test_unauthenticated_exception(self):
        """UnauthenticatedException sets status_code and detail."""
        exc = UnauthenticatedException("no auth")
        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.detail, "no auth")

    def test_unauthorized_exception(self):
        """UnauthorizedException sets status_code and detail."""
        exc = UnauthorizedException("forbidden")
        self.assertEqual(exc.status_code, 403)
        self.assertEqual(exc.detail, "forbidden")

class TestCreateErrorResponse(unittest.TestCase):
    """Test create_error_response utility function."""
    def test_error_response_structure(self):
        """create_error_response returns correct dict structure."""
        result = create_error_response(400, "BAD_REQUEST", "fail", details={"foo": "bar"})
        self.assertIn("error", result)
        err = result["error"]
        self.assertEqual(err["type"], "BAD_REQUEST")
        self.assertEqual(err["status_code"], 400)
        self.assertEqual(err["message"], "fail")
        self.assertEqual(err["details"], {"foo": "bar"})
        self.assertIsInstance(err["timestamp"], str)
        self.assertTrue(err["timestamp"].endswith("Z") or "T" in err["timestamp"])  # ISO8601
        self.assertTrue(err["request_id"].startswith("req-"))
        # Validate UUID part
        uuid_part = err["request_id"][4:]
        try:
            UUID(uuid_part)
        except Exception as e:
            self.fail(f"request_id UUID part is invalid: {e}")

    def test_error_response_defaults(self):
        """create_error_response fills details with empty dict if None."""
        result = create_error_response(500, "INTERNAL_ERROR", "fail")
        self.assertEqual(result["error"]["details"], {})

if __name__ == "__main__":
    """Run all unit tests for HTTP exception utilities."""
    unittest.main()
