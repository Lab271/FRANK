#! behave
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

Feature: Mock Cognito User and Organisation Management
  As a platform administrator
  I want to manage users and organisations in Cognito
  So that I can control access to the FRANK platform

  Background:
    Given Mock Cognito is running on port 8100

  @health @cognito
  Scenario: Mock Cognito health check
    When I query the Mock Cognito health endpoint
    Then the response status should be 200
    And the response should contain service name "mock-cognito"

  @seeding @cognito
  Scenario: Verify seeded fixture data
    When I list all users in Mock Cognito
    Then I should see 7 users in the system
    And user "admin" should exist with organisation "identity--schuberg-philis"
    And user "ijsbrand" should exist with organisation "identity--schuberg-philis"
    And user "s_unit_analyst" should exist with organisation "identity--s-unit"

  @seeding @cognito
  Scenario Outline: Verify seeded users have correct attributes
    When I get user details for "<username>"
    Then the user should have email "<email>"
    And the user should belong to organisation "<organisation_id>"
    And the user should have role "<role>"
    And the user should be in group "<group>"

    Examples:
      | username          | email                                 | organisation_id               | role   | group       |
      | admin             | admin@schubergphilis.com              | identity--schuberg-philis     | owner  | core_member |
      | ijsbrand          | ijsbrand.heitlager@schubergphilis.com | identity--schuberg-philis     | admin  | core_member |
      | s_unit_analyst    | analyst@s-unit.nl                     | identity--s-unit              | member | partner     |
      | rabobank_security | security@rabobank.nl                  | identity--rabobank            | member | contributor |
      | kpn_observer      | security@kpn.com                      | identity--kpn                 | member | observer    |

  @organisations @cognito
  Scenario Outline: List users by organisation
    When I filter users by organisation "<organisation_id>"
    Then I should see <user_count> users
    And the users should be "<expected_users>"

    Examples:
      | organisation_id            | user_count | expected_users          |
      | identity--schuberg-philis  | 2          | admin,ijsbrand          |
      | identity--s-unit           | 1          | s_unit_analyst          |
      | identity--rabobank         | 1          | rabobank_security       |
      | identity--ing              | 1          | ing_soc                 |

  @users @crud @cognito
  Scenario: Create a new user with organisation
    When I create a new user with the following details:
      | username          | newuser                  |
      | email             | newuser@example.com      |
      | password          | TempPass123!             |
      | organisation_id   | identity--rabobank       |
      | organisation_name | Rabobank                 |
      | role              | member                   |
      | groups            | contributor              |
    Then the user creation should be successful
    And the user "newuser" should exist in the system
    And user "newuser" should belong to organisation "identity--rabobank"

  @users @crud @cognito
  Scenario: Get user details shows custom attributes
    Given user "admin" exists in the system
    When I get user details for "admin"
    Then the response should include UserAttributes array
    And the UserAttributes should contain "custom:organisation_id" with value "identity--schuberg-philis"
    And the UserAttributes should contain "custom:organisation_name" with value "Schuberg Philis"
    And the UserAttributes should contain "custom:role" with value "owner"

  @users @crud @cognito
  Scenario: Update user's organisation
    Given I create a test user "testuser1" in organisation "identity--kpn"
    When I update user "testuser1" organisation to "identity--rabobank"
    And I update user "testuser1" role to "admin"
    Then user "testuser1" should belong to organisation "identity--rabobank"
    And user "testuser1" should have role "admin"

  @users @crud @cognito
  Scenario: Update user custom attributes using AWS Cognito format
    Given I create a test user "testuser2" in organisation "identity--ing"
    When I update user "testuser2" with UserAttributes:
      | Name                      | Value                      |
      | custom:organisation_id    | identity--s-unit           |
      | custom:organisation_name  | S-Unit                     |
      | custom:role               | owner                      |
    Then user "testuser2" should belong to organisation "identity--s-unit"
    And user "testuser2" should have role "owner"

  @users @crud @cognito
  Scenario: Delete user
    Given I create a test user "tempuser" in organisation "identity--kpn"
    When I delete user "tempuser"
    Then user "tempuser" should not exist in the system

  @users @groups @cognito
  Scenario: Add user to group changes access tier
    Given I create a test user "testuser3" in organisation "identity--rabobank"
    When I add user "testuser3" to group "partner"
    Then user "testuser3" should be in group "partner"

  @users @groups @cognito
  Scenario: Remove user from group
    Given user "admin" exists in the system
    And user "admin" is in group "core_member"
    When I remove user "admin" from group "core_member"
    Then user "admin" should not be in group "core_member"

  @authentication @cognito
  Scenario Outline: Authenticate users from different organisations
    Given user "<username>" exists in the system
    When I authenticate with username "<username>" and password "<password>"
    Then authentication should be successful
    And the access token should contain organisation "<organisation_id>"
    And the access token should contain groups "<group>"

    Examples:
      | username          | password     | organisation_id            | group       |
      | admin             | admin123     | identity--schuberg-philis  | core_member |
      | s_unit_analyst    | TempPass123! | identity--s-unit           | partner     |
      | kpn_observer      | TempPass123! | identity--kpn              | observer    |

  @authentication @cognito
  Scenario: Failed authentication with wrong password
    When I authenticate with username "admin" and password "wrongpassword"
    Then authentication should fail
    And I should receive an AWS "NotAuthorizedException" error

  @authentication @cognito
  Scenario: Failed authentication with non-existent user
    When I authenticate with username "nonexistent" and password "anypassword"
    Then authentication should fail
    And I should receive an AWS "UserNotFoundException" error

  @organisations @cognito
  Scenario: Query organisation members through user filtering
    When I filter users by organisation "identity--schuberg-philis"
    Then I should see 2 users
    And each user should have organisation "identity--schuberg-philis"
    And the users should have different roles

  @organisations @cognito
  Scenario Outline: Verify organisation structure matches seeded data
    When I filter users by organisation "<organisation_id>"
    Then the organisation should have <member_count> members
    And the organisation access tier should be "<access_tier>"

    Examples:
      | organisation_id            | member_count | access_tier |
      | identity--schuberg-philis  | 2            | core_member |
      | identity--s-unit           | 1            | partner     |
      | identity--rabobank         | 1            | contributor |
      | identity--gemeente-amsterdam | 1          | observer    |

  @edge-cases @cognito
  Scenario: Create user with duplicate username fails
    Given user "admin" exists in the system
    When I attempt to create a user with username "admin"
    Then the user creation should fail
    And I should receive a "409" status code

  @edge-cases @cognito
  Scenario: Get non-existent user returns 404
    When I attempt to get user details for "nonexistent"
    Then I should receive a "404" status code

  @edge-cases @cognito
  Scenario: Update non-existent user returns 404
    When I attempt to update user "nonexistent" with new email
    Then I should receive a "404" status code

  @aws-compatibility @cognito
  Scenario: AdminListUsers returns AWS Cognito compatible format
    When I list users with AWS SDK format
    Then the response should have a "Users" array
    And each user should have "Username" field
    And each user should have "Attributes" array
    And each user should have "UserStatus" field

  @aws-compatibility @cognito
  Scenario: AdminGetUser returns AWS Cognito compatible format
    When I get user "admin" with AWS SDK format
    Then the response should have "UserAttributes" array
    And the response should have "Username" field
    And the response should have "UserStatus" field
