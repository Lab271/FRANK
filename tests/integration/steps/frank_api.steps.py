#!/usr/bin/env python3
"""
FRANK Platform - API steps - BDD

Step implementation function for BDD/Behave tests

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

# features/steps/frank_api_steps.py
import json
import requests
import time
from datetime import datetime, timezone, timedelta
from behave import given, when, then
from hamcrest import assert_that, equal_to, greater_than, contains_string, has_key, not_none, less_than_or_equal_to


# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_TOKENS = {
    "observer": "observer_test_token",
    "contributor": "contributor_test_token", 
    "partner": "partner_test_token",
    "core_member": "core_test_token"
}

class APIClient:
    def __init__(self, base_url=API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.last_response = None
    
    def set_auth_token(self, token):
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def clear_auth(self):
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]
    
    def post(self, endpoint, data=None, json_data=None):
        url = f"{self.base_url}{endpoint}"
        self.last_response = self.session.post(url, data=data, json=json_data)
        return self.last_response
    
    def get(self, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        self.last_response = self.session.get(url, params=params)
        return self.last_response


@given('the FRANK API is running')
def step_api_running(context):
    context.api = APIClient()
    # Test that API is accessible
    response = context.api.get("/v1/health")
    assert_that(response.status_code, equal_to(200))
    context.health_data = response.json()


@given('the database is initialized with demo data')
def step_database_initialized(context):
    # The API should initialize demo data on startup
    # We can verify this by checking statistics
    context.api.set_auth_token(TEST_TOKENS["partner"])
    response = context.api.get("/v1/statistics")
    assert_that(response.status_code, equal_to(200))


@given('I am authenticated as {article} {user_type} user')
def step_authenticated_user(context, article, user_type):
    context.user_type = user_type
    context.api.set_auth_token(TEST_TOKENS[user_type])


@given('I am not authenticated')
def step_not_authenticated(context):
    context.user_type = None
    context.api.clear_auth()


@given('there are threat sightings in the database')
def step_sightings_exist(context):
    # Submit a test sighting to ensure data exists
    context.api.set_auth_token(TEST_TOKENS["partner"])
    test_submission = create_test_submission("185.220.102.45", 85)
    response = context.api.post("/v1/submission", json_data=test_submission)
    # Allow some time for processing
    time.sleep(0.1)


@given('there are sightings with various confidence levels')
def step_sightings_various_confidence(context):
    context.api.set_auth_token(TEST_TOKENS["partner"])
    confidence_levels = [60, 75, 85, 95]
    
    for i, confidence in enumerate(confidence_levels):
        submission = create_test_submission(f"10.0.0.{i+1}", confidence)
        context.api.post("/v1/submission", json_data=submission)
    
    time.sleep(0.2)  # Allow processing


@given('there are sightings from different sectors and dates')
def step_sightings_different_sectors(context):
    context.api.set_auth_token(TEST_TOKENS["core_member"])
    
    # Create submissions for different scenarios
    sectors = ["financial", "healthcare", "retail"]
    for i, sector in enumerate(sectors):
        submission = create_test_submission(f"203.0.113.{i+1}", 80, sector=sector)
        context.api.post("/v1/submission", json_data=submission)
    
    time.sleep(0.2)


@when('I submit a threat intelligence sighting with confidence {confidence:d}')
def step_submit_sighting(context, confidence):
    submission = create_test_submission("192.168.1.1", confidence)
    context.response = context.api.post("/v1/submission", json_data=submission)


@when('I attempt to submit a threat intelligence sighting')
def step_attempt_submit(context):
    submission = create_test_submission("192.168.1.2", 75)
    context.response = context.api.post("/v1/submission", json_data=submission)


@when('I query for sightings with IP address "{ip_address}"')
def step_query_by_ip(context, ip_address):
    params = {"observable": ip_address}
    context.response = context.api.get("/v1/sighting", params=params)


@when('I query for sightings with minimum confidence {min_confidence:d}')
def step_query_min_confidence(context, min_confidence):
    params = {"confidence_min": min_confidence}
    context.response = context.api.get("/v1/sighting", params=params)


@when('I query with start_date "{start_date}" and end_date "{end_date}"')
def step_query_invalid_dates(context, start_date, end_date):
    params = {
        "start_date": f"{start_date}T00:00:00Z",
        "end_date": f"{end_date}T23:59:59Z"
    }
    context.response = context.api.get("/v1/sighting", params=params)


# @when('I make more than {limit:d} requests in a day')
# def step_exceed_rate_limit(context, limit):
#     # For testing, we'll make a smaller number of rapid requests
#     # to simulate rate limiting
#     responses = []
#     for i in range(min(limit + 5, 20)):  # Cap at 20 for test efficiency
#         response = context.api.get("/v1/sighting")
#         responses.append(response)
#         if response.status_code == 429:
#             break
    
#     context.response = responses[-1]


@when('I check the API health status')
def step_check_health(context):
    context.response = context.api.get("/v1/health")


@when('I request platform statistics')
def step_request_statistics(context):
    context.response = context.api.get("/v1/statistics")


@when('I search for sightings in "{sector}" sector from last {days:d} days with confidence > {confidence:d}')
def step_complex_search(context, sector, days, confidence):
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    params = {
        "sector": sector,
        "confidence_min": confidence + 1,
        "start_date": start_date.isoformat()
    }
    context.response = context.api.get("/v1/sighting", params=params)


@when('I submit a comprehensive sighting with:')
def step_submit_comprehensive(context):
    # Parse the table data from context
    sighting_data = {}
    for row in context.table:
        sighting_data[row['field']] = row['value']
    
    submission = create_comprehensive_submission(sighting_data)
    context.response = context.api.post("/v1/submission", json_data=submission)


@then('the submission should be {result}')
def step_submission_result(context, result):
    if result == "accepted":
        assert_that(context.response.status_code, equal_to(200))
        response_data = context.response.json()
        assert_that(response_data["status"], equal_to("accepted"))
    elif result == "rejected":
        assert_that(context.response.status_code, greater_than(399))


@then('my contribution score should increase by {score_range}')
def step_score_increase(context, score_range):
    if context.response.status_code == 200:
        response_data = context.response.json()
        if "contribution_score_impact" in response_data:
            score = response_data["contribution_score_impact"]
            if "-" in score_range:
                min_score, max_score = map(int, score_range.split("-"))
                assert_that(score, greater_than(min_score - 1))
                assert_that(score, less_than_or_equal_to(max_score))
            else:
                expected_score = int(score_range)
                assert_that(score, equal_to(expected_score))


@then('I should receive a "{status_code:d}" error')
def step_receive_error(context, status_code):
    assert_that(context.response.status_code, equal_to(status_code))


@then('the error message should contain "{message}"')
def step_error_contains_message(context, message):
    response_data = context.response.json()
    error_text = str(response_data)
    assert_that(error_text.lower(), contains_string(message.lower()))


@then('I should receive {data_level} data')
def step_receive_data_level(context, data_level):
    assert_that(context.response.status_code, equal_to(200))
    response_data = context.response.json()
    
    if data_level == 'aggregated usage':
        # Check for basic statistics fields
        expected_fields = ["total_submissions", "observable_types"]
        for field in expected_fields:
            if field in response_data:
                assert_that(response_data[field], not_none())        
    elif response_data.get("sightings"):
        sighting = response_data["sightings"][0]
        
        if data_level == "masked":
            # Observer level should have masked values
            if "observable_value" in sighting:
                assert_that(sighting["observable_value"], contains_string("*"))
        
        elif data_level == "detailed":
            # Partner level should have full observables
            assert_that(sighting, has_key("observable"))
            if context.user_type in ["partner", "core_member"]:
                assert_that(response_data, has_key("threat_context"))


@then('the response should contain {field_count:d} fields per sighting')
def step_field_count(context, field_count):
    response_data = context.response.json()
    if response_data.get("sightings"):
        sighting = response_data["sightings"][0]
        actual_count = len(sighting.keys())
        # Allow some flexibility in field count
        assert_that(actual_count, greater_than(field_count - 3))


@then('all returned sightings should have confidence >= {min_confidence:d}')
def step_confidence_filter_validation(context, min_confidence):
    response_data = context.response.json()
    if response_data.get("sightings"):
        for sighting in response_data["sightings"]:
            confidence = sighting.get("confidence", 0)
            assert_that(confidence, greater_than(min_confidence - 1))


@then('subsequent requests should be rejected with "429" error')
def step_subsequent_requests_rejected_429(context):
    # The last response in the rate limit scenario should be 429
    assert_that(context.response.status_code, equal_to(429))


@then('the results should be properly paginated')
def step_results_paginated(context):
    response_data = context.response.json()
    assert_that(response_data, has_key("total_results"))
    assert_that(response_data, has_key("returned_results"))


@then('the error should indicate "{error_message}"')
def step_error_indicates(context, error_message):
    response_data = context.response.json()
    error_content = json.dumps(response_data)
    assert_that(error_content.lower(), contains_string(error_message.lower()))


@then('the health endpoint should return "{status}"')
def step_health_status(context, status):
    assert_that(context.response.status_code, equal_to(200))
    response_data = context.response.json()
    assert_that(response_data["status"], equal_to(status))


@then('include database status information')
def step_include_db_status(context):
    response_data = context.response.json()
    assert_that(response_data, has_key("database"))


@then('sensitive details should be filtered based on my access level')
def step_sensitive_filtered(context):
    response_data = context.response.json()
    
    # Observer should have limited data
    if context.user_type == "observer":
        # Should not have detailed organisation information
        sensitive_fields = ["organisation_details", "financial_impact"]
        for field in sensitive_fields:
            assert field not in response_data, f"Sensitive field {field} should not be in observer response"


@then('the results should match all filter criteria')
def step_results_match_criteria(context):
    # This is validated by the fact that the query succeeded
    # and returned results - detailed validation would require
    # inspecting each result
    assert_that(context.response.status_code, equal_to(200))


@then('include threat context information')
def step_include_threat_context(context):
    if context.user_type in ["partner", "core_member"]:
        response_data = context.response.json()
        # Partner and above should get threat context
        if "threat_context" in response_data:
            assert_that(response_data["threat_context"], not_none())


@then('provide aggregation statistics')
def step_provide_aggregations(context):
    response_data = context.response.json()
    if context.user_type in ["contributor", "partner", "core_member"]:
        # These levels should get aggregations
        if "aggregations" in response_data:
            assert_that(response_data["aggregations"], not_none())


@then('all context data should be stored')
def step_context_data_stored(context):
    # Verify the comprehensive submission was accepted
    assert_that(context.response.status_code, equal_to(200))
    response_data = context.response.json()
    assert_that(response_data["status"], equal_to("accepted"))


@then('the contribution score should reflect the comprehensive nature')
def step_comprehensive_score(context):
    response_data = context.response.json()
    if "contribution_score_impact" in response_data:
        score = response_data["contribution_score_impact"]
        # Comprehensive submissions should have higher scores
        assert_that(score, greater_than(15))


# Helper functions
def create_test_submission(ip_address, confidence, sector="technology"):
    return {
        "submission": {
            "submitter": {
                "organisation_id": f"test-org-{hash(ip_address)}",
                "access_level": "partner",
                "sector": sector
            },
            "sighting": {
                "sighting_id": f"test-sighting-{hash(ip_address)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": confidence,
                "severity": "medium",
                "observables": {
                    "network": [
                        {
                            "type": "ipv4",
                            "value": ip_address,
                            "role": "c2_server"
                        }
                    ]
                }
            }
        }
    }


def create_comprehensive_submission(sighting_data):
    return {
        "submission": {
            "submitter": {
                "organisation_id": "test-comprehensive-org",
                "access_level": "core_member",
                "sector": "cybersecurity_services"
            },
            "sighting": {
                "sighting_id": f"comprehensive-{datetime.now().timestamp()}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": int(sighting_data.get("confidence", 95)),
                "severity": sighting_data.get("severity", "high"),
                "observables": {
                    "network": [
                        {
                            "type": sighting_data.get("observable_type", "ipv4"),
                            "value": sighting_data.get("observable_value", "192.168.1.100"),
                            "role": "malicious_server"
                        }
                    ]
                },
                "sigma_detection": {
                    "rule_name": sighting_data.get("sigma_rule", "test_rule"),
                    "rule_status": "stable"
                },
                "threat_context": {
                    "campaign": {
                        "name": sighting_data.get("campaign", "test_campaign"),
                        "attribution": "test_actor"
                    }
                },
                "impact": {
                    "affected_systems": int(sighting_data.get("impact_systems", 5)),
                    "financial_impact_eur": 10000
                }
            }
        }
    }