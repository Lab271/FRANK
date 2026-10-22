#!/bin/bash

# put this in a function and get HOST_URL from outside as parameter to script
HOST_URL=${1:-http://localhost:8000}

echo "🔍 Testing all FastAPI endpoints..."
echo "==================================="
echo "Using HOST_URL: $HOST_URL"
echo
printf "📌 Testing public endpoint: "
curl -s $HOST_URL/ | grep -q "Public endpoint accessed successfully" && echo "✅ PASS" || echo "❌ FAIL"

printf "🔐 Testing protected endpoint (valid token): "
curl -s -H "Authorization: Bearer valid-token" $HOST_URL/protected | grep -q "Protected endpoint accessed successfully" && echo "✅ PASS" || echo "❌ FAIL"
printf "🚫 Testing protected endpoint (invalid token): "
curl -s -H "Authorization: Bearer invalid-token" $HOST_URL/protected | grep -q "Invalid authentication token" && echo "✅ PASS" || echo "❌ FAIL"

printf "💥 Testing exception endpoint (500 error): "
curl -s $HOST_URL/error | grep -q "This is a controlled exception for testing purposes" && echo "✅ PASS" || echo "❌ FAIL"
printf "🐍 Testing Python exception endpoint (500 error): "
curl -s $HOST_URL/python-error | grep -q "This is a Python exception converted to HTTP 500" && echo "✅ PASS" || echo "❌ FAIL"
printf "⚠️  Testing custom error endpoint (401 error): "
curl -s $HOST_URL/unauthorized | grep -q "Custom unauthorized error from endpoint" && echo "✅ PASS" || echo "❌ FAIL"

printf "❤️  Testing health check endpoint: "
curl -s $HOST_URL/health | grep -q "healthy" && echo "✅ PASS" || echo "❌ FAIL"
