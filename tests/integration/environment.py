#!/usr/bin/env python3
"""
FRANK Platform - Behave Environment Configuration

Handles test setup, teardown, and command-line parameter configuration.

Usage:
    # Run with default settings (port 8000)
    behave

    # Run with custom server port
    behave -D server_port=8080

    # Run with custom server URL
    behave -D server_url=http://localhost:8080

    # Run with mock cognito
    behave -D server_port=8080 -D cognito_port=8100

    # Run specific tags
    behave --tags=@health -D server_port=8080

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import logging
import requests
from urllib.parse import urlparse

# Configure logging for behave
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def before_all(context):
    """
    Setup test environment before all features.

    Reads command-line parameters and environment variables to configure test settings.
    """
    # Get server configuration from command-line (-D flag) or environment variables
    server_url = context.config.userdata.get('server_url')
    server_port = context.config.userdata.get('server_port')
    server_host = context.config.userdata.get('server_host', 'localhost')

    # Build server URL
    if server_url:
        # Full URL provided
        context.api_base_url = server_url
    elif server_port:
        # Port provided, build URL
        context.api_base_url = f"http://{server_host}:{server_port}"
    else:
        # Use environment variable or default
        context.api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000')

    # Cognito configuration (for authentication tests)
    cognito_url = context.config.userdata.get('cognito_url')
    cognito_port = context.config.userdata.get('cognito_port')

    if cognito_url:
        context.cognito_url = cognito_url
    elif cognito_port:
        context.cognito_url = f"http://{server_host}:{cognito_port}"
    else:
        context.cognito_url = os.environ.get('COGNITO_URL', 'http://localhost:8100')

    # Management API configuration
    management_url = context.config.userdata.get('management_url')
    management_port = context.config.userdata.get('management_port')

    if management_url:
        context.management_url = management_url
    elif management_port:
        context.management_url = f"http://{server_host}:{management_port}"
    else:
        context.management_url = os.environ.get('MANAGEMENT_URL', 'http://localhost:8200')

    # Test tokens (for authentication)
    context.test_tokens = {
        "observer": context.config.userdata.get('observer_token', 'observer_test_token'),
        "contributor": context.config.userdata.get('contributor_token', 'contributor_test_token'),
        "partner": context.config.userdata.get('partner_token', 'partner_test_token'),
        "core_member": context.config.userdata.get('core_member_token', 'core_test_token')
    }

    # Additional configuration
    context.timeout = int(context.config.userdata.get('timeout', '30'))
    context.verify_ssl = context.config.userdata.get('verify_ssl', 'false').lower() == 'true'

    # Log configuration
    logger.info("=" * 60)
    logger.info("FRANK BDD Test Configuration")
    logger.info("=" * 60)
    logger.info(f"API Base URL: {context.api_base_url}")
    logger.info(f"Cognito URL: {context.cognito_url}")
    logger.info(f"Management URL: {context.management_url}")
    logger.info(f"Timeout: {context.timeout}s")
    logger.info(f"Verify SSL: {context.verify_ssl}")
    logger.info("=" * 60)


def before_feature(context, feature):
    """
    Setup before each feature.
    """
    logger.info(f"Starting feature: {feature.name}")


def after_feature(context, feature):
    """
    Cleanup after each feature.
    """
    if feature.status == "failed":
        logger.error(f"Feature failed: {feature.name}")
    else:
        logger.info(f"Feature completed: {feature.name} ({feature.status})")


def before_scenario(context, scenario):
    """
    Setup before each scenario.
    """
    # Debug: Log scenario tags
    logger.debug(f"Scenario: {scenario.name}, Tags: {scenario.effective_tags}")

    # Only seed Mock Cognito if running cognito-related tests
    if 'cognito' in scenario.effective_tags and hasattr(context, 'cognito_url'):
        try:
            reset_url = f"{context.cognito_url}/admin/reset"
            response = requests.post(reset_url, timeout=5)
            if response.status_code == 200:
                logger.debug("Reset Mock Cognito database to initial fixtures")
        except Exception as e:
            logger.debug(f"Could not reset Mock Cognito: {e}")

    # Only seed Management API if running management-related tests
    if 'management' in scenario.effective_tags and hasattr(context, 'management_url'):
        # First check if Management API is available
        try:
            health_check = requests.get(f"{context.management_url}/health", timeout=2)
            if health_check.status_code != 200:
                logger.debug(f"Management API not available, skipping database seed")
                return
        except Exception:
            logger.debug(f"Management API not available, skipping database seed")
            return

        # Management API is available, proceed with seeding
        try:
            # Get admin token for authenticated seed endpoint
            auth_response = requests.post(
                f"{context.management_url}/v1/auth/login",
                json={"username": "admin", "password": "admin123"},
                timeout=5
            )

            if auth_response.status_code == 200:
                token = auth_response.json().get("access_token")

                # Force reseed to reset database to known state
                seed_url = f"{context.management_url}/admin/seed?force=true"
                response = requests.post(
                    seed_url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5
                )

                if response.status_code == 200:
                    logger.debug("Reset Management API database to initial fixtures")
                else:
                    logger.debug(f"Could not seed Management API database: {response.status_code}")
            else:
                logger.debug("Could not authenticate for database seed")
        except Exception as e:
            logger.debug(f"Could not seed Management API database: {e}")

    # Reset any scenario-specific state
    context.last_response = None
    context.last_submission_id = None


def after_scenario(context, scenario):
    """
    Cleanup after each scenario.
    """
    # Clean up test users created during the scenario
    if hasattr(context, 'created_test_users') and hasattr(context, 'management'):
        for username in context.created_test_users:
            try:
                context.management.delete_user(username)
                logger.debug(f"Cleaned up test user: {username}")
            except Exception as e:
                logger.warning(f"Could not clean up test user {username}: {e}")
        context.created_test_users = []

    if scenario.status == "failed":
        logger.error(f"Scenario failed: {scenario.name}")
        # Log last response for debugging
        if hasattr(context, 'last_response') and context.last_response:
            logger.error(f"Last response status: {context.last_response.status_code}")
            logger.error(f"Last response body: {context.last_response.text[:500]}")


def after_step(context, step):
    """
    Hook after each step (useful for debugging).
    """
    if step.status == "failed":
        logger.error(f"Step failed: {step.name}")
        logger.error(f"Step location: {step.location}")


def after_all(context):
    """
    Cleanup after all features.
    """
    logger.info("=" * 60)
    logger.info("BDD Test Run Complete")
    logger.info("=" * 60)
