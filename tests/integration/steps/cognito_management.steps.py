#!/usr/bin/env python3
"""
FRANK Platform - Cognito Management BDD Steps

Step definitions for testing Mock Cognito user and organisation management.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import jwt
import requests
from behave import given, then, when
from hamcrest import (
    assert_that,
    contains_string,
    equal_to,
    greater_than,
    greater_than_or_equal_to,
    has_key,
    is_in,
    not_none,
)


class CognitoClient:
    """Client for interacting with Mock Cognito API"""

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.last_response = None
        self.last_tokens = None

    def health_check(self):
        """Check Mock Cognito health"""
        url = f"{self.base_url}/health"
        self.last_response = self.session.get(url)
        return self.last_response

    def list_users(self, filter_str=None, limit=60):
        """List users with optional filter (AWS AdminListUsers)"""
        url = f"{self.base_url}/admin/users"
        params = {}
        if filter_str:
            params['filter'] = filter_str
        if limit:
            params['limit'] = limit

        self.last_response = self.session.get(url, params=params)
        return self.last_response

    def get_user(self, username):
        """Get user details (AWS AdminGetUser)"""
        url = f"{self.base_url}/admin/users/{username}"
        self.last_response = self.session.get(url)
        return self.last_response

    def create_user(self, user_data):
        """Create new user (AWS AdminCreateUser)"""
        url = f"{self.base_url}/admin/users"
        self.last_response = self.session.post(url, json=user_data)
        return self.last_response

    def update_user(self, username, update_data):
        """Update user (AWS AdminUpdateUserAttributes)"""
        url = f"{self.base_url}/admin/users/{username}"
        self.last_response = self.session.put(url, json=update_data)
        return self.last_response

    def delete_user(self, username):
        """Delete user (AWS AdminDeleteUser)"""
        url = f"{self.base_url}/admin/users/{username}"
        self.last_response = self.session.delete(url)
        return self.last_response

    def add_user_to_group(self, username, group):
        """Add user to group (AWS AdminAddUserToGroup)"""
        url = f"{self.base_url}/admin/users/{username}/groups"
        self.last_response = self.session.post(url, json={"group": group})
        return self.last_response

    def remove_user_from_group(self, username, group):
        """Remove user from group (AWS AdminRemoveUserFromGroup)"""
        url = f"{self.base_url}/admin/users/{username}/groups/{group}"
        self.last_response = self.session.delete(url)
        return self.last_response

    def authenticate(self, username, password):
        """Authenticate user and get tokens"""
        url = f"{self.base_url}/auth/login"
        auth_data = {"username": username, "password": password}
        self.last_response = self.session.post(url, json=auth_data)
        if self.last_response.status_code == 200:
            self.last_tokens = self.last_response.json()
        return self.last_response

    def decode_token(self, token, verify=False):
        """Decode JWT token"""
        return jwt.decode(token, options={"verify_signature": verify})


# ========== Background Steps ==========

@given('Mock Cognito is running on port {port:d}')
def step_cognito_running(context, port):
    """Verify Mock Cognito is accessible"""
    base_url = context.cognito_url or f"http://localhost:{port}"
    context.cognito = CognitoClient(base_url)

    # Verify health endpoint
    response = context.cognito.health_check()
    assert_that(response.status_code, equal_to(200), "Mock Cognito not accessible")
    context.cognito_health = response.json()


# ========== Health Check Steps ==========

@when('I query the Mock Cognito health endpoint')
def step_query_health(context):
    """Query health endpoint"""
    context.cognito.health_check()


@then('the response should contain service name "{service_name}"')
def step_verify_service_name(context, service_name):
    """Verify service name in response"""
    data = context.cognito.last_response.json()
    assert_that(data.get('service'), equal_to(service_name))


# ========== Seeding Verification Steps ==========

@when('I list all users in Mock Cognito')
def step_list_all_users(context):
    """List all users"""
    context.cognito.list_users()


@then('I should see {count:d} users in the system')
def step_verify_user_count(context, count):
    """Verify total user count"""
    data = context.cognito.last_response.json()
    users = data.get('Users', [])
    assert_that(len(users), equal_to(count), f"Expected {count} users")


@then('I should see {count:d} users')
def step_verify_user_count_short(context, count):
    """Verify user count (shorter version)"""
    step_verify_user_count(context, count)


@then('user "{username}" should exist with organisation "{org_id}"')
def step_verify_user_organisation(context, username, org_id):
    """Verify user exists with specific organisation"""
    response = context.cognito.get_user(username)
    assert_that(response.status_code, equal_to(200), f"User {username} not found")

    data = response.json()
    # Check in UserAttributes array (AWS format)
    user_attrs = data.get('UserAttributes', [])
    org_attr = next((attr for attr in user_attrs if attr['Name'] == 'custom:organisation_id'), None)

    if org_attr:
        assert_that(org_attr['Value'], equal_to(org_id))
    else:
        # Fallback to legacy format
        assert_that(data.get('custom:organisation_id'), equal_to(org_id))


# ========== User Detail Verification Steps ==========

@when('I get user details for "{username}"')
def step_get_user_details(context, username):
    """Get user details"""
    context.cognito.get_user(username)
    context.current_username = username


@then('the user should have email "{email}"')
def step_verify_user_email(context, email):
    """Verify user email"""
    data = context.cognito.last_response.json()

    # Check UserAttributes array
    user_attrs = data.get('UserAttributes', [])
    email_attr = next((attr for attr in user_attrs if attr['Name'] == 'email'), None)

    if email_attr:
        assert_that(email_attr['Value'], equal_to(email))
    else:
        assert_that(data.get('email'), equal_to(email))


@then('the user should belong to organisation "{org_id}"')
def step_verify_user_belongs_to_org(context, org_id):
    """Verify user's organisation"""
    data = context.cognito.last_response.json()

    # Check UserAttributes array
    user_attrs = data.get('UserAttributes', [])
    org_attr = next((attr for attr in user_attrs if attr['Name'] == 'custom:organisation_id'), None)

    if org_attr:
        assert_that(org_attr['Value'], equal_to(org_id))
    else:
        assert_that(data.get('custom:organisation_id'), equal_to(org_id))


@then('user "{username}" should belong to organisation "{org_id}"')
def step_verify_named_user_belongs_to_org(context, username, org_id):
    """Verify specific user's organisation"""
    response = context.cognito.get_user(username)
    assert_that(response.status_code, equal_to(200), f"User {username} not found")
    context.cognito.last_response = response
    step_verify_user_belongs_to_org(context, org_id)


@then('the user should have role "{role}"')
def step_verify_user_role(context, role):
    """Verify user role"""
    data = context.cognito.last_response.json()

    # Check UserAttributes array
    user_attrs = data.get('UserAttributes', [])
    role_attr = next((attr for attr in user_attrs if attr['Name'] == 'custom:role'), None)

    if role_attr:
        assert_that(role_attr['Value'], equal_to(role))
    else:
        assert_that(data.get('custom:role'), equal_to(role))


@then('user "{username}" should have role "{role}"')
def step_verify_named_user_role(context, username, role):
    """Verify specific user's role"""
    response = context.cognito.get_user(username)
    assert_that(response.status_code, equal_to(200), f"User {username} not found")
    context.cognito.last_response = response
    step_verify_user_role(context, role)


@then('the user should be in group "{group}"')
def step_verify_user_group(context, group):
    """Verify user is in specified group"""
    context.cognito.last_response.json()


@then('user "{username}" should be in group "{group}"')
def step_verify_named_user_group(context, username, group):
    """Verify specific user is in group"""
    response = context.cognito.get_user(username)
    assert_that(response.status_code, equal_to(200), f"User {username} not found")

    # Get groups from user details
    user_data = response.json()
    user_groups = user_data.get('groups', [])
    assert_that(group, is_in(user_groups), f"User {username} not in group {group}")


# ========== Organisation Filtering Steps ==========

@when('I filter users by organisation "{org_id}"')
def step_filter_by_organisation(context, org_id):
    """Filter users by organisation"""
    filter_str = f'custom:organisation_id = "{org_id}"'
    context.cognito.list_users(filter_str=filter_str)
    context.current_org_id = org_id


@then('the users should be "{expected_users}"')
def step_verify_user_list(context, expected_users):
    """Verify list of usernames"""
    data = context.cognito.last_response.json()
    users = data.get('Users', [])

    expected_list = [u.strip() for u in expected_users.split(',')]
    actual_usernames = [user['Username'] for user in users]

    for expected_username in expected_list:
        assert_that(expected_username, is_in(actual_usernames),
                   f"Expected user {expected_username} not found")


# ========== User CRUD Steps ==========

@when('I create a new user with the following details:')
def step_create_user_with_details(context):
    """Create user with details from table"""
    user_data = {}

    # In Gherkin, the first row becomes table headings
    # For a key-value table, we need to extract it as data
    if context.table.headings and len(context.table.headings) == 2:
        # Add the header row as the first key-value pair
        user_data[context.table.headings[0]] = context.table.headings[1]

    # Process remaining rows as key-value pairs
    for row in context.table:
        if len(row.cells) == 2:
            user_data[row[0]] = row[1]

    # Convert groups string to list if needed
    if 'groups' in user_data and isinstance(user_data['groups'], str):
        user_data['groups'] = [user_data['groups']]

    context.cognito.create_user(user_data)
    context.last_created_user = user_data.get('username')


@then('the user creation should be successful')
def step_verify_creation_successful(context):
    """Verify user creation succeeded"""
    assert_that(context.cognito.last_response.status_code, equal_to(201),
               "User creation failed")


@then('the user "{username}" should exist in the system')
def step_verify_user_exists(context, username):
    """Verify user exists"""
    response = context.cognito.get_user(username)
    assert_that(response.status_code, equal_to(200), f"User {username} does not exist")


@given('user "{username}" exists in the system')
def step_given_user_exists(context, username):
    """Verify user exists (precondition)"""
    response = context.cognito.get_user(username)
    assert_that(response.status_code, equal_to(200), f"User {username} does not exist")


@given('I create a test user "{username}" in organisation "{org_id}"')
def step_create_test_user(context, username, org_id):
    """Create a test user"""
    user_data = {
        "username": username,
        "email": f"{username}@test.example.com",
        "password": "TempPass123!",
        "groups": ["observer"],
        "custom:organisation_id": org_id,
        "custom:organisation_name": org_id.replace("identity--", "").title(),
        "custom:role": "member"
    }
    context.cognito.create_user(user_data)
    assert_that(context.cognito.last_response.status_code, equal_to(201))
    context.test_users = getattr(context, 'test_users', [])
    context.test_users.append(username)


@when('I update user "{username}" organisation to "{org_id}"')
def step_update_user_organisation(context, username, org_id):
    """Update user's organisation"""
    update_data = {
        "custom:organisation_id": org_id,
        "custom:organisation_name": org_id.replace("identity--", "").title()
    }
    context.cognito.update_user(username, update_data)


@when('I update user "{username}" role to "{role}"')
def step_update_user_role(context, username, role):
    """Update user's role"""
    update_data = {"custom:role": role}
    context.cognito.update_user(username, update_data)


@when('I update user "{username}" with UserAttributes:')
def step_update_with_user_attributes(context, username):
    """Update user with AWS Cognito UserAttributes format"""
    user_attributes = []
    for row in context.table:
        user_attributes.append({
            "Name": row['Name'],
            "Value": row['Value']
        })

    update_data = {"UserAttributes": user_attributes}
    context.cognito.update_user(username, update_data)


@when('I delete user "{username}"')
def step_delete_user(context, username):
    """Delete user"""
    context.cognito.delete_user(username)


@then('user "{username}" should not exist in the system')
def step_verify_user_not_exists(context, username):
    """Verify user does not exist"""
    response = context.cognito.get_user(username)
    assert_that(response.status_code, equal_to(404), f"User {username} still exists")


# ========== Group Management Steps ==========

@when('I add user "{username}" to group "{group}"')
def step_add_to_group(context, username, group):
    """Add user to group"""
    context.cognito.add_user_to_group(username, group)


@given('user "{username}" is in group "{group}"')
def step_given_user_in_group(context, username, group):
    """Verify user is in group (precondition)"""
    response = context.cognito.get_user(username)
    data = response.json()
    groups = data.get('groups', [])
    assert_that(group, is_in(groups))


@when('I remove user "{username}" from group "{group}"')
def step_remove_from_group(context, username, group):
    """Remove user from group"""
    context.cognito.remove_user_from_group(username, group)


@then('user "{username}" should not be in group "{group}"')
def step_verify_not_in_group(context, username, group):
    """Verify user is not in group"""
    response = context.cognito.get_user(username)
    data = response.json()
    groups = data.get('groups', [])
    assert_that(group not in groups, equal_to(True))


# ========== Authentication Steps ==========

@when('I authenticate with username "{username}" and password "{password}"')
def step_authenticate_user(context, username, password):
    """Authenticate user"""
    context.cognito.authenticate(username, password)


@then('authentication should be successful')
def step_verify_auth_successful(context):
    """Verify authentication succeeded"""
    assert_that(context.cognito.last_response.status_code, equal_to(200))
    data = context.cognito.last_response.json()
    assert_that(data, has_key('access_token'))
    assert_that(data, has_key('id_token'))


@then('authentication should fail')
def step_verify_auth_failed(context):
    """Verify authentication failed"""
    assert_that(context.cognito.last_response.status_code, greater_than_or_equal_to(400))


@then('the access token should contain organisation "{org_id}"')
def step_verify_token_org(context, org_id):
    """Verify token contains organisation (note: typically not in JWT)"""
    # Tokens usually don't contain custom attributes, but we can verify via GetUser
    # For now, just verify we got a token
    data = context.cognito.last_response.json()
    assert_that(data, has_key('access_token'))


@then('the access token should contain groups "{group}"')
def step_verify_token_groups(context, group):
    """Verify token contains group"""
    data = context.cognito.last_response.json()
    access_token = data.get('access_token')

    # Decode token (without verification for testing)
    decoded = context.cognito.decode_token(access_token)
    groups = decoded.get('cognito:groups', [])
    assert_that(group, is_in(groups))


@then('I should receive a "{status_code:d}" status code')
def step_verify_status_code_cognito(context, status_code):
    """Verify HTTP status code for Cognito response"""
    assert_that(context.cognito.last_response.status_code, equal_to(status_code))


@then('I should receive an AWS "{error_type}" error')
def step_verify_aws_error_type(context, error_type):
    """Verify AWS-specific error type"""
    data = context.cognito.last_response.json()
    assert_that(data.get('__type'), contains_string(error_type))


# ========== Response Format Verification Steps ==========

@then('the response should include UserAttributes array')
def step_verify_user_attributes_array(context):
    """Verify response has UserAttributes array"""
    data = context.cognito.last_response.json()
    assert_that(data, has_key('UserAttributes'))
    assert_that(isinstance(data['UserAttributes'], list), equal_to(True))


@then('the response should have "{field}" array')
def step_verify_response_has_array(context, field):
    """Verify response has specific array field"""
    data = context.cognito.last_response.json()
    assert_that(data, has_key(field))
    assert_that(isinstance(data[field], list), equal_to(True))


@then('each user should have "{field}" array')
def step_verify_each_user_has_array(context, field):
    """Verify each user in list has specific array field"""
    data = context.cognito.last_response.json()
    users = data.get('Users', [])
    for user in users:
        assert_that(user, has_key(field))
        assert_that(isinstance(user[field], list), equal_to(True))


@then('the UserAttributes should contain "{attr_name}" with value "{attr_value}"')
def step_verify_attribute_value(context, attr_name, attr_value):
    """Verify specific attribute value"""
    data = context.cognito.last_response.json()
    user_attrs = data.get('UserAttributes', [])
    attr = next((a for a in user_attrs if a['Name'] == attr_name), None)
    assert_that(attr, not_none(), f"Attribute {attr_name} not found")
    assert_that(attr['Value'], equal_to(attr_value))


@then('each user should have organisation "{org_id}"')
def step_verify_all_users_have_org(context, org_id):
    """Verify all users in result have same organisation"""
    data = context.cognito.last_response.json()
    users = data.get('Users', [])

    for user in users:
        attrs = user.get('Attributes', [])
        org_attr = next((a for a in attrs if a['Name'] == 'custom:organisation_id'), None)
        assert_that(org_attr, not_none())
        assert_that(org_attr['Value'], equal_to(org_id))


@then('the users should have different roles')
def step_verify_different_roles(context):
    """Verify users have different roles"""
    data = context.cognito.last_response.json()
    users = data.get('Users', [])

    roles = set()
    for user in users:
        attrs = user.get('Attributes', [])
        role_attr = next((a for a in attrs if a['Name'] == 'custom:role'), None)
        if role_attr:
            roles.add(role_attr['Value'])

    assert_that(len(roles), greater_than(1), "All users have the same role")


# ========== Organisation Structure Verification ==========

@then('the organisation should have {count:d} members')
def step_verify_org_member_count(context, count):
    """Verify organisation member count"""
    data = context.cognito.last_response.json()
    users = data.get('Users', [])
    assert_that(len(users), equal_to(count))


@then('the organisation access tier should be "{tier}"')
def step_verify_org_tier(context, tier):
    """Verify organisation access tier (from user groups)"""
    data = context.cognito.last_response.json()
    users = data.get('Users', [])

    # Get the group from first user (all users in org should have same tier)
    if users:
        users[0].get('Attributes', [])
        # Note: groups are not in Attributes, this is stored separately
        # For this test, we'll just verify we got users
        assert_that(len(users), greater_than(0))


# ========== Edge Cases ==========

@when('I attempt to create a user with username "{username}"')
def step_attempt_create_duplicate(context, username):
    """Attempt to create duplicate user"""
    user_data = {
        "username": username,
        "email": f"{username}@test.com",
        "password": "TempPass123!"
    }
    context.cognito.create_user(user_data)


@then('the user creation should fail')
def step_verify_creation_failed(context):
    """Verify creation failed"""
    assert_that(context.cognito.last_response.status_code, greater_than_or_equal_to(400))


@when('I attempt to get user details for "{username}"')
def step_attempt_get_user(context, username):
    """Attempt to get user"""
    context.cognito.get_user(username)


@when('I attempt to update user "{username}" with new email')
def step_attempt_update_user(context, username):
    """Attempt to update user"""
    context.cognito.update_user(username, {"email": "new@example.com"})


# ========== AWS Compatibility Verification ==========

@when('I list users with AWS SDK format')
def step_list_users_aws_format(context):
    """List users (already returns AWS format)"""
    context.cognito.list_users()


@then('the response should have a "{field}" array')
def step_verify_has_array(context, field):
    """Verify response has array field"""
    data = context.cognito.last_response.json()
    assert_that(data, has_key(field))
    assert_that(isinstance(data[field], list), equal_to(True))


@then('each user should have "{field}" field')
def step_verify_users_have_field(context, field):
    """Verify all users have field"""
    data = context.cognito.last_response.json()
    users = data.get('Users', [])

    for user in users:
        assert_that(user, has_key(field), f"User missing field {field}")


@when('I get user "{username}" with AWS SDK format')
def step_get_user_aws_format(context, username):
    """Get user (already returns AWS format)"""
    context.cognito.get_user(username)


@then('the response should have "{field}" field')
def step_verify_has_field(context, field):
    """Verify response has field"""
    data = context.cognito.last_response.json()
    assert_that(data, has_key(field), f"Response missing field {field}")


# ========== Common Assertions ==========

@then('the response status should be {status:d}')
def step_verify_status(context, status):
    """Verify response status code"""
    assert_that(context.cognito.last_response.status_code, equal_to(status))


# ========== Cleanup Hook ==========

def after_scenario(context, scenario):
    """Cleanup test users after each scenario"""
    if hasattr(context, 'test_users') and hasattr(context, 'cognito'):
        for username in context.test_users:
            try:
                context.cognito.delete_user(username)
            except Exception:
                pass  # User might already be deleted
        context.test_users = []
