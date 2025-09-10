#! behave
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

Feature: FRANK Platform Threat Intelligence API
  As a cybersecurity professional
  I want to submit and query threat intelligence
  So that I can contribute to and benefit from collective defense

  Background:
    Given the FRANK API is running
    And the database is initialized with demo data

  Scenario Outline: Submit threat intelligence with different access levels
    Given I am authenticated as a <user_type> user
    When I submit a threat intelligence sighting with confidence <confidence>
    Then the submission should be <result>
    And my contribution score should increase by <score_increase>

    Examples:
      | user_type   | confidence | result   | score_increase |
      | partner     | 85         | accepted | 10-25          |
      | contributor | 70         | accepted | 10-25          |
      | core_member | 95         | accepted | 10-25          |

  Scenario: Observer cannot submit threat intelligence
    Given I am authenticated as an observer user
    When I attempt to submit a threat intelligence sighting
    Then the submission should be rejected
    And I should receive a "403" error
    And the error message should contain "Insufficient access level"

  Scenario: Unauthenticated access is denied
    Given I am not authenticated
    When I attempt to submit a threat intelligence sighting
    Then the submission should be rejected
    And I should receive a "401" error

  Scenario Outline: Query threat intelligence with access level filtering
    Given I am authenticated as a <user_type> user
    And there are threat sightings in the database
    When I query for sightings with IP address "185.220.102.45"
    Then I should receive <data_level> data
    And the response should contain <field_count> fields per sighting

    Examples:
      | user_type   | data_level | field_count |
      | observer    | masked     | 6           |
      | contributor | partial    | 6           |
      | partner     | detailed   | 9           |
      | core_member | complete   | 9           |

  Scenario: Search with confidence filtering
    Given I am authenticated as a contributor user
    And there are sightings with various confidence levels
    When I query for sightings with minimum confidence 80
    Then all returned sightings should have confidence >= 80
    And the results should be properly paginated

  Scenario: Invalid query parameters are rejected
    Given I am authenticated as a partner user
    When I query with start_date "2025-01-20" and end_date "2025-01-15"
    Then I should receive a "400" error
    And the error should indicate "Invalid date range"

  # Scenario: Rate limiting enforcement
  #   Given I am authenticated as an observer user
  #   When I make more than 500 requests in a day
  #   Then subsequent requests should be rejected with "429" error
  #   And the error message should contain "Rate limit exceeded"

  Scenario: Health check endpoint
    When I check the API health status
    Then the health endpoint should return "healthy"
    And include database status information

  Scenario: Platform statistics access
    Given I am authenticated as a contributor user
    When I request platform statistics
    Then I should receive aggregated usage data
    And sensitive details should be filtered based on my access level

  Scenario: Complex search with multiple filters
    Given I am authenticated as a partner user
    And there are sightings from different sectors and dates
    When I search for sightings in "financial" sector from last 7 days with confidence > 75
    Then the results should match all filter criteria
    And include threat context information
    And provide aggregation statistics

  Scenario: Submit comprehensive threat intelligence
    Given I am authenticated as a core_member user
    When I submit a comprehensive sighting with:
      | field              | value                    |
      | observable_type    | ipv4                     |
      | observable_value   | 192.168.1.100            |
      | confidence         | 95                       |
      | severity           | high                     |
      | sigma_rule         | banking_trojan_detection |
      | campaign           | operation_banking_theft  |
      | impact_systems     | 15                       |
    Then the submission should be accepted
    And all context data should be stored
    And the contribution score should reflect the comprehensive nature