# FRANK Platform - Cognito Authentication Spike - Mock Cognito Service Container
# 
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim

WORKDIR /app

# Install dependencies inline
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    pyjwt==2.8.0 \
    python-multipart==0.0.6 \
    cryptography==41.0.7

# Copy application code
COPY mock_cognito.py .

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "mock_cognito:app", "--host", "0.0.0.0", "--port", "8080"]