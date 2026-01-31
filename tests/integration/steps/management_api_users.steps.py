#!/usr/bin/env python3
"""
FRANK Platform - Management API BDD Step Definitions

Step definitions for testing user and organisation management through the Management API.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import requests
import jwt
import logging
from hamcrest import assert_that, equal_to, greater_than, has_key, contains_string, is_in

logger = logging.getLogger(__name__)


class ManagementAPIClient:
    """Client for interacting with the Management API"""

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.last_response = None
        self.access_token = None
        self.refresh_token = None

    def set_auth_token(self, token):
        """Set the authorization token for requests"""
        self.access_token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def clear_auth(self):
        """Clear authentication"""
        self.access_token = None
        self.refresh_token = None
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]

    def login(self, username, password):
        """Authenticate and get access token"""
        url = f"{self.base_url}/v1/auth/login"
        data = {"username": username, "password": password}
        self.last_response = self.session.post(url, json=data)

        if self.last_response.status_code == 200:
            response_data = self.last_response.json()
            self.access_token = response_data.get("access_token")
            self.refresh_token = response_data.get("refresh_token")
            self.set_auth_token(self.access_token)

        return self.last_response

    def refresh_access_token(self):
        """Refresh the access token"""
        url = f"{self.base_url}/v1/auth/refresh"
        data = {"refresh_token": self.refresh_token}
        self.last_response = self.session.post(url, json=data)

        if self.last_response.status_code == 200:
            response_data = self.last_response.json()
            self.access_token = response_data.get("access_token")
            self.set_auth_token(self.access_token)

        return self.last_response

    def health_check(self):
        """Check Management API health"""
        url = f"{self.base_url}/health"
        self.last_response = self.session.get(url)
        return self.last_response

    def list_organisations(self, **params):
        """List organisations"""
        url = f"{self.base_url}/v1/organisations"
        self.last_response = self.session.get(url, params=params)
        return self.last_response

    def create_organisation(self, org_data):
        """Create a new organisation"""
        url = f"{self.base_url}/v1/organisations"
        self.last_response = self.session.post(url, json=org_data)
        return self.last_response

    def get_organisation(self, organisation_id):
        """Get organisation details"""
        url = f"{self.base_url}/v1/organisations/{organisation_id}"
        self.last_response = self.session.get(url)
        return self.last_response

    def create_user(self, organisation_id, user_data):
        """Create a new user in an organisation"""
        url = f"{self.base_url}/v1/organisations/{organisation_id}/users"
        self.last_response = self.session.post(url, json=user_data)
        return self.last_response

    def list_users_in_organisation(self, organisation_id):
        """List users in an organisation"""
        url = f"{self.base_url}/v1/organisations/{organisation_id}/users"
        self.last_response = self.session.get(url)
        return self.last_response

    def get_user(self, username):
        """Get user details"""
        url = f"{self.base_url}/v1/users/{username}"
        self.last_response = self.session.get(url)
        return self.last_response

    def update_user(self, username, update_data):
        """Update user"""
        url = f"{self.base_url}/v1/users/{username}"
        self.last_response = self.session.put(url, json=update_data)
        return self.last_response

    def delete_user(self, username):
        """Delete user"""
        url = f"{self.base_url}/v1/users/{username}"
        self.last_response = self.session.delete(url)
        return self.last_response

    def add_organisation_member(self, organisation_id, username, role="member"):
        """Add a member to an organisation"""
        url = f"{self.base_url}/v1/organisations/{organisation_id}/members"
        data = {"username": username, "role": role}
        self.last_response = self.session.post(url, json=data)
        return self.last_response

    def list_organisation_members(self, organisation_id):
        """List members of an organisation"""
        url = f"{self.base_url}/v1/organisations/{organisation_id}/members"
        self.last_response = self.session.get(url)
        return self.last_response

    def remove_organisation_member(self, organisation_id, username):
        """Remove a member from an organisation"""
        url = f"{self.base_url}/v1/organisations/{organisation_id}/members/{username}"
        self.last_response = self.session.delete(url)
        return self.last_response

    def decode_token(self, token, verify=False):
        """Decode JWT token"""
        return jwt.decode(token, options={"verify_signature": verify})


# ========== Background Steps ==========

@given('the Management API is running on port {port:d}')
def step_management_api_running(context, port):
    """Initialize Management API client"""
    management_host = context.config.userdata.get('management_host', 'localhost')
    base_url = context.management_url or f"http://{management_host}:{port}"
    context.management = ManagementAPIClient(base_url)

    # Verify it's accessible
    response = context.management.health_check()
    assert_that(response.status_code, equal_to(200), "Management API not accessible")


@given('Mock Cognito is running for Management API on port {port:d}')
def step_cognito_running_for_management(context, port):
    """Verify Mock Cognito is accessible (required by Management API)"""
    cognito_url = f"http://localhost:{port}/health"
    response = requests.get(cognito_url, timeout=5)
    assert_that(response.status_code, equal_to(200), "Mock Cognito not accessible")


# ========== Authentication Steps ==========

@given('I am authenticated as "{username}" with password "{password}"')
def step_authenticate_as_user(context, username, password):
    """Authenticate as a specific user"""
    response = context.management.login(username, password)
    assert_that(response.status_code, equal_to(200), f"Authentication failed for {username}")
    data = response.json()
    assert_that(data, has_key('access_token'))


@when('I login via Management API with username "{username}" and password "{password}"')
def step_login_management_api(context, username, password):
    """Login via Management API"""
    context.management.login(username, password)


@when('I refresh my access token via Management API')
def step_refresh_token(context):
    """Refresh access token"""
    context.management.refresh_access_token()


@then('the access token should be valid')
def step_verify_token_valid(context):
    """Verify access token is valid"""
    assert_that(context.management.access_token, "Access token should not be None")
    # Decode token to verify it's valid JWT
    decoded = context.management.decode_token(context.management.access_token)
    assert_that(decoded, has_key('sub'))  # Should have subject claim


@then('the new access token should be valid')
def step_verify_new_token_valid(context):
    """Verify new access token is valid"""
    step_verify_token_valid(context)


# ========== Health Check Steps ==========

@when('I query the Management API health endpoint')
def step_query_health(context):
    """Query health endpoint"""
    context.management.health_check()


# ========== Organisation Steps ==========

@when('I list all organisations via Management API')
def step_list_organisations(context):
    """List all organisations"""
    context.management.list_organisations()


@when('I list all organisations via Management API without authentication')
def step_list_organisations_no_auth(context):
    """List organisations without authentication"""
    context.management.clear_auth()
    context.management.list_organisations()


@then('I should see at least {count:d} organisation')
@then('I should see at least {count:d} organisations')
def step_verify_organisation_count(context, count):
    """Verify minimum organisation count"""
    data = context.management.last_response.json()
    organisations = data.get('organisations', [])
    assert_that(len(organisations), greater_than(count - 1),
                f"Expected at least {count} organisations, got {len(organisations)}")


# ========== User Management Steps ==========

@when('I create a user via Management API with details:')
@given('I create a user via Management API with details:')
def step_create_user_via_api(context):
    """Create user via Management API"""
    user_data = {}

    # Extract data from table
    if context.table.headings and len(context.table.headings) == 2:
        user_data[context.table.headings[0]] = context.table.headings[1]

    for row in context.table:
        if len(row.cells) == 2:
            user_data[row[0]] = row[1]

    # Convert groups to list if needed
    if 'groups' in user_data and isinstance(user_data['groups'], str):
        user_data['groups'] = [user_data['groups']]

    # Extract organisation_id (required for API)
    organisation_id = user_data.pop('organisation_id', 'identity--schuberg-philis')

    # Create user
    context.management.create_user(organisation_id, user_data)

    # Store created username for cleanup
    if 'username' in user_data:
        if not hasattr(context, 'created_test_users'):
            context.created_test_users = []
        context.created_test_users.append(user_data['username'])


@when('I attempt to create a user via Management API with details:')
def step_attempt_create_user(context):
    """Attempt to create user (may fail)"""
    step_create_user_via_api(context)


@when('I list users in organisation "{organisation_id}" via Management API')
def step_list_users_in_org(context, organisation_id):
    """List users in organisation"""
    context.management.list_users_in_organisation(organisation_id)


@when('I get user details for "{username}" via Management API')
def step_get_user_details(context, username):
    """Get user details"""
    context.management.get_user(username)


@when('I update user "{username}" via Management API with:')
def step_update_user(context, username):
    """Update user"""
    update_data = {}

    # Extract data from table
    if context.table.headings and len(context.table.headings) == 2:
        update_data[context.table.headings[0]] = context.table.headings[1]

    for row in context.table:
        if len(row.cells) == 2:
            key, value = row[0], row[1]
            # Convert groups to list if needed
            if key == 'groups':
                value = [value] if isinstance(value, str) else value
            update_data[key] = value

    context.management.update_user(username, update_data)


@when('I delete user "{username}" via Management API')
def step_delete_user(context, username):
    """Delete user"""
    context.management.delete_user(username)


@then('I should see at least {count:d} user in the response')
@then('I should see at least {count:d} users in the response')
def step_verify_user_count_in_response(context, count):
    """Verify minimum user count"""
    data = context.management.last_response.json()
    users = data.get('users', [])
    assert_that(len(users), greater_than(count - 1),
                f"Expected at least {count} users, got {len(users)}")


@then('the response should contain username "{username}"')
def step_verify_response_contains_username(context, username):
    """Verify response contains username"""
    data = context.management.last_response.json()
    actual_username = data.get('username') or data.get('Username')
    assert_that(actual_username, equal_to(username))


@then('the response should contain email "{email}"')
def step_verify_response_contains_email(context, email):
    """Verify response contains email"""
    data = context.management.last_response.json()
    actual_email = data.get('email')
    assert_that(actual_email, equal_to(email))


@then('the user should have organisation "{org_id}" in attributes')
def step_verify_user_has_org_in_attributes(context, org_id):
    """Verify user has organisation in custom attributes"""
    data = context.management.last_response.json()

    # Check in UserAttributes array (AWS format)
    user_attrs = data.get('UserAttributes', [])
    if user_attrs:
        org_attr = next((attr for attr in user_attrs
                        if attr['Name'] == 'custom:organisation_id'), None)
        if org_attr:
            assert_that(org_attr['Value'], equal_to(org_id))
            return

    # Check in direct attributes
    org = data.get('custom:organisation_id') or data.get('organisation_id')
    assert_that(org, equal_to(org_id))


# ========== Organisation Member Steps ==========

@when('I add user "{username}" as member to organisation "{organisation_id}" with role "{role}"')
@given('I add user "{username}" as member to organisation "{organisation_id}" with role "{role}"')
def step_add_organisation_member(context, username, organisation_id, role):
    """Add user as organisation member"""
    context.management.add_organisation_member(organisation_id, username, role)


@when('I list members of organisation "{organisation_id}" via Management API')
def step_list_organisation_members(context, organisation_id):
    """List organisation members"""
    context.management.list_organisation_members(organisation_id)


@when('I remove user "{username}" from organisation "{organisation_id}" via Management API')
def step_remove_organisation_member(context, username, organisation_id):
    """Remove user from organisation"""
    context.management.remove_organisation_member(organisation_id, username)


@then('I should see at least {count:d} member in the response')
@then('I should see at least {count:d} members in the response')
def step_verify_member_count(context, count):
    """Verify minimum member count"""
    data = context.management.last_response.json()
    members = data.get('members', [])
    assert_that(len(members), greater_than(count - 1),
                f"Expected at least {count} members, got {len(members)}")


# ========== General Response Verification Steps ==========

@then('the response status should be {status_code:d}')
@then('the Management API response status should be {status_code:d}')
def step_verify_status_code(context, status_code):
    """Verify HTTP status code"""
    assert_that(context.management.last_response.status_code, equal_to(status_code),
                f"Expected status {status_code}, got {context.management.last_response.status_code}")


@then('the response should contain "{field}"')
def step_verify_response_contains_field(context, field):
    """Verify response contains a field"""
    data = context.management.last_response.json()
    assert_that(data, has_key(field), f"Response missing field: {field}")


@then('the response should contain error details')
def step_verify_error_details(context):
    """Verify response contains error information"""
    data = context.management.last_response.json()
    # Should have either 'detail' or 'error' or 'message'
    has_error = ('detail' in data) or ('error' in data) or ('message' in data)
    assert_that(has_error, equal_to(True), "Response should contain error details")


# ========== Cleanup Hook ==========

def after_scenario(context, scenario):
    """Cleanup after each scenario"""
    # Clean up any test users created during the scenario
    if hasattr(context, 'created_test_users') and hasattr(context, 'management'):
        for username in context.created_test_users:
            try:
                context.management.delete_user(username)
                logger.debug(f"Cleaned up test user: {username}")
            except Exception as e:
                logger.warning(f"Could not clean up test user {username}: {e}")
        context.created_test_users = []
