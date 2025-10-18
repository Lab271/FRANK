#
# FRANK Platform - Main container Dockerfile
# Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling
#
# Multi-architecture build for AWS ECS deployment
# Supports both ARM64 (M1/M2 Mac) and AMD64 (AWS Fargate)
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0


# Accept platform arguments from buildx
ARG TARGETPLATFORM
ARG BUILDPLATFORM

FROM python:3.13-slim AS base

# Platform-specific optimizations
RUN case "${TARGETPLATFORM}" in \
    "linux/amd64") \
        echo "Building for AMD64 (AWS Fargate compatible)" \
        ;; \
    "linux/arm64") \
        echo "Building for ARM64 (M1/M2 Mac and AWS Graviton compatible)" \
        ;; \
    *) \
        echo "Building for platform: ${TARGETPLATFORM}" \
        ;; \
    esac

# ===================================
# Builder Stage
# ===================================
FROM base AS builder

# Set working directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --user \
    fastapi==0.118.3 \
    uvicorn==0.37.0 \
    boto3==1.40.18 \
    requests==2.32.5 \
    pydantic==2.11.9 \
    PyJWT==2.10.1 \
    httpx==0.28.1 \
    python-multipart==0.0.20 \
    cryptography==46.0.2

# ===================================
# Production Stage
# ===================================

FROM base AS production

# Redeclare build context for this stage
ARG BUILD_CONTEXT=stages/stage3
ARG PACKAGE_CONTEXT=.

# Create non-root user
RUN groupadd -r frankuser && useradd -r -g frankuser frankuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN pip install --upgrade pip

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/frankuser/.local

# Set working directory
WORKDIR /app

# Copy application code
COPY ${BUILD_CONTEXT}/README.md .
COPY ${PACKAGE_CONTEXT}/setup.py .
COPY ${PACKAGE_CONTEXT}/src/ ./src/
RUN pip install --no-cache-dir .

COPY ${BUILD_CONTEXT}/frank_stage3.py frank_api.py



# Change ownership to frankuser
RUN chown -R frankuser:frankuser /app

# Switch to non-root user
USER frankuser

# Expose port
EXPOSE 8000
# Set environment variables
ENV PORT=8000
ENV PATH=/home/frankuser/.local/bin:$PATH
ENV FRANK_ENVIRONMENT=aws
ENV RELOAD=false
ENV HOST=0.0.0.0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

# Run the application
CMD ["python", "frank_api.py"]