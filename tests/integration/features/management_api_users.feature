#! behave
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

Feature: Management API User and Organisation Management
  As a platform administrator
  I want to manage users and organisations through the Management API
  So that I can control access to the FRANK platform via the proper API layer

  Background:
    Given the Management API is running on port 8001
    And Mock Cognito is running for Management API on port 8100

  @health @management
  Scenario: Management API health check
    When I query the Management API health endpoint
    Then the Management API response status should be 200
    And the response should contain "database"

  @organisations @management
  Scenario: List organisations via Management API
    Given I am authenticated as "admin" with password "admin123"
    When I list all organisations via Management API
    Then the Management API response status should be 200
    And I should see at least 1 organisation

  @users @management
  Scenario: Create user via Management API
    Given I am authenticated as "admin" with password "admin123"
    When I create a user via Management API with details:
      | username          | apiuser                  |
      | email             | apiuser@example.com      |
      | password          | TempPass123!             |
      | organisation_id   | identity--schuberg-philis |
      | groups            | observer                 |
    Then the Management API response status should be 201
    And the response should contain username "apiuser"
    And the response should contain email "apiuser@example.com"

  @users @management
  Scenario: List users in organisation via Management API
    Given I am authenticated as "admin" with password "admin123"
    When I list users in organisation "identity--schuberg-philis" via Management API
    Then the Management API response status should be 200
    And I should see at least 2 users in the response

  @users @management
  Scenario: Get user details via Management API
    Given I am authenticated as "admin" with password "admin123"
    When I get user details for "admin" via Management API
    Then the Management API response status should be 200
    And the response should contain username "admin"
    And the response should contain email "admin@schubergphilis.com"
    And the user should have organisation "identity--schuberg-philis" in attributes

  @users @management
  Scenario: Update user via Management API
    Given I am authenticated as "admin" with password "admin123"
    And I create a user via Management API with details:
      | username          | updateuser               |
      | email             | update@example.com       |
      | password          | TempPass123!             |
      | organisation_id   | identity--schuberg-philis |
      | groups            | observer                 |
    When I update user "updateuser" via Management API with:
      | email   | updated@example.com |
      | groups  | contributor         |
    Then the Management API response status should be 200
    And the response should contain email "updated@example.com"

  @users @management
  Scenario: Delete user via Management API
    Given I am authenticated as "admin" with password "admin123"
    And I create a user via Management API with details:
      | username          | deleteuser               |
      | email             | delete@example.com       |
      | password          | TempPass123!             |
      | organisation_id   | identity--schuberg-philis |
      | groups            | observer                 |
    When I delete user "deleteuser" via Management API
    Then the Management API response status should be 204
    When I get user details for "deleteuser" via Management API
    Then the Management API response status should be 404

  @auth @management
  Scenario: Login via Management API
    When I login via Management API with username "admin" and password "admin123"
    Then the Management API response status should be 200
    And the response should contain "access_token"
    And the response should contain "refresh_token"
    And the access token should be valid

  @auth @management
  Scenario: Failed login with wrong password
    When I login via Management API with username "admin" and password "wrongpassword"
    Then the Management API response status should be 401
    And the response should contain error details

  @auth @management
  Scenario: Refresh token via Management API
    Given I am authenticated as "admin" with password "admin123"
    When I refresh my access token via Management API
    Then the Management API response status should be 200
    And the response should contain "access_token"
    And the new access token should be valid

  @members @management
  Scenario: Add organisation member via Management API
    Given I am authenticated as "admin" with password "admin123"
    And I create a user via Management API with details:
      | username          | memberuser               |
      | email             | member@example.com       |
      | password          | TempPass123!             |
      | organisation_id   | identity--s-unit         |
      | groups            | partner                  |
    When I add user "memberuser" as member to organisation "identity--rabobank" with role "member"
    Then the Management API response status should be 201
    And the response should contain username "memberuser"

  @members @management
  Scenario: List organisation members via Management API
    Given I am authenticated as "admin" with password "admin123"
    When I list members of organisation "identity--schuberg-philis" via Management API
    Then the Management API response status should be 200
    And I should see at least 2 members in the response

  @members @management
  Scenario: Remove organisation member via Management API
    Given I am authenticated as "admin" with password "admin123"
    And I add user "admin" as member to organisation "identity--rabobank" with role "admin"
    When I remove user "admin" from organisation "identity--rabobank" via Management API
    Then the Management API response status should be 204

  @access-control @management
  Scenario: Observer cannot create users
    Given I am authenticated as "kpn_observer" with password "TempPass123!"
    When I attempt to create a user via Management API with details:
      | username | unauthorized |
      | email    | unauth@test.com |
    Then the Management API response status should be 403

  @access-control @management
  Scenario: Observer can view organisations
    Given I am authenticated as "kpn_observer" with password "TempPass123!"
    When I list all organisations via Management API
    Then the Management API response status should be 200

  @edge-cases @management
  Scenario: Create user with duplicate username fails
    Given I am authenticated as "admin" with password "admin123"
    When I attempt to create a user via Management API with details:
      | username | admin |
      | email    | duplicate@test.com |
    Then the Management API response status should be 409
    And the response should contain error details

  @edge-cases @management
  Scenario: Get non-existent user returns 404
    Given I am authenticated as "admin" with password "admin123"
    When I get user details for "nonexistent" via Management API
    Then the Management API response status should be 404

  @edge-cases @management
  Scenario: Unauthorized request without token fails
    When I list all organisations via Management API without authentication
    Then the Management API response status should be 401
