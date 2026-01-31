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
    # Reset Mock Cognito database to initial fixtures
    if hasattr(context, 'cognito_url'):
        try:
            reset_url = f"{context.cognito_url}/admin/reset"
            response = requests.post(reset_url, timeout=5)
            if response.status_code == 200:
                logger.debug("Reset Mock Cognito database to initial fixtures")
        except Exception as e:
            logger.warning(f"Could not reset Mock Cognito: {e}")

    # Reset Management API database (reseed with initial data)
    if hasattr(context, 'management_url'):
        try:
            # Force reseed to reset database to known state
            seed_url = f"{context.management_url}/admin/seed?force=true"
            response = requests.post(seed_url, timeout=5)
            if response.status_code == 200:
                logger.debug("Reset Management API database to initial fixtures")
            elif response.status_code == 401:
                # Need authentication for seed endpoint - try with admin credentials
                logger.debug("Seed endpoint requires authentication, attempting with admin token")
                # This will be handled by the test setup if needed
            else:
                logger.warning(f"Could not seed Management API database: {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not seed Management API database: {e}")

    # Reset any scenario-specific state
    context.last_response = None
    context.last_submission_id = None


def after_scenario(context, scenario):
    """
    Cleanup after each scenario.
    """
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
