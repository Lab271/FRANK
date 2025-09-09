# # ================================
# # test_stage2.py - Basic API Tests
# # ================================
# import pytest
# import httpx
# import asyncio
# from frank_stage2 import app, config

# # Test configuration
# BASE_URL = "http://localhost:8000"
# TEST_ORG_ID = "test-org-pytest"

# @pytest.fixture
# def client():
#     return httpx.AsyncClient(app=app, base_url=BASE_URL)

# @pytest.mark.asyncio
# async def test_health_endpoint(client):
#     """Test health check endpoint"""
#     response = await client.get("/v1/health")
#     assert response.status_code == 200
#     data = response.json()
#     assert "status" in data
#     assert "databases" in data

# @pytest.mark.asyncio
# async def test_root_endpoint(client):
#     """Test root endpoint"""
#     response = await client.get("/")
#     assert response.status_code == 200
#     data = response.json()
#     assert data["service"] == "FRANK Platform"
#     assert "stage" in data

# @pytest.mark.asyncio
# async def test_submit_minimal_submission(client):
#     """Test submitting a minimal threat intelligence submission"""
#     submission_data = {
#         "submitter_org_id": TEST_ORG_ID,
#         "observables": [
#             {
#                 "type": "ipv4",
#                 "value": "192.168.1.200",
#                 "confidence": 85
#             },
#             {
#                 "type": "domain", 
#                 "value": "test.malicious.com",
#                 "confidence": 90
#             }
#         ],
#         "confidence": 87
#     }
    
#     response = await client.post("/v1/submissions", json=submission_data)
#     assert response.status_code == 200
#     data = response.json()
#     assert data["status"] == "success"
#     assert "submission_id" in data
#     assert "performance_ms" in data

# @pytest.mark.asyncio
# async def test_get_submission(client):
#     """Test retrieving a submission"""
#     # First create a submission
#     submission_data = {
#         "submitter_org_id": TEST_ORG_ID,
#         "observables": [
#             {
#                 "type": "file_hash",
#                 "value": "abcdef123456",
#                 "confidence": 95
#             }
#         ],
#         "confidence": 95
#     }
    
#     create_response = await client.post("/v1/submissions", json=submission_data)
#     assert create_response.status_code == 200
#     submission_id = create_response.json()["submission_id"]
    
#     # Now retrieve it
#     get_response = await client.get(f"/v1/submissions/{submission_id}")
#     assert get_response.status_code == 200
#     data = get_response.json()
#     assert data["submission"]["submission_id"] == submission_id

# @pytest.mark.asyncio 
# async def test_list_organization_submissions(client):
#     """Test listing submissions for an organization"""
#     response = await client.get(f"/v1/organizations/{TEST_ORG_ID}/submissions")
#     assert response.status_code == 200
#     data = response.json()
#     assert "organization_id" in data
#     assert "submissions" in data
#     assert data["organization_id"] == TEST_ORG_ID

# @pytest.mark.asyncio
# async def test_performance_endpoint(client):
#     """Test performance monitoring endpoint"""
#     response = await client.get("/v1/performance")
#     assert response.status_code == 200
#     data = response.json()
#     assert "performance_summary" in data

# @pytest.mark.asyncio
# async def test_dual_database_submission(client):
#     """Test submission to dual databases"""
#     submission_data = {
#         "submitter_org_id": TEST_ORG_ID,
#         "observables": [
#             {
#                 "type": "url",
#                 "value": "http://evil.example.com/test",
#                 "confidence": 80
#             }
#         ],
#         "confidence": 80
#     }
    
#     # Test dual database submission
#     response = await client.post("/v1/submissions?database=dual", json=submission_data)
#     assert response.status_code == 200
#     data = response.json()
#     assert data["database_used"] == "dual"

# if __name__ == "__main__":
#     pytest.main([__file__, "-v"])