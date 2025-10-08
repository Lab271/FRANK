# ===================================
# Dockerfile for 008_aws_spike.py
# Multi-architecture build for AWS ECS deployment
# Supports both ARM64 (M1/M2 Mac) and AMD64 (AWS Fargate)
# ===================================
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

# Create requirements.txt with minimal dependencies
RUN echo "fastapi===0.116.2" > requirements.txt && \
    echo "uvicorn[standard]==0.24.0" >> requirements.txt && \
    echo "boto3==1.40.18" >> requirements.txt && \
    echo "aioboto3==15.2.0" >> requirements.txt && \
    echo "pydantic==2.11.9" >> requirements.txt

    # Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# ===================================
# Production Stage
# ===================================

FROM base AS production

# Redeclare build context for this stage
ARG BUILD_CONTEXT=tests/spikes/009_aws_stage4
ARG PACKAGE_CONTEXT=.
ARG APP_NAME=simple_api.py

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
COPY ${BUILD_CONTEXT}/${APP_NAME} .
COPY ${BUILD_CONTEXT}/README.md .
COPY ${PACKAGE_CONTEXT}/setup.py .
COPY ${PACKAGE_CONTEXT}/src/ ./src/

RUN pip install -e .

# Set environment variables
ENV PATH=/home/frankuser/.local/bin:$PATH
# ENV PYTHONPATH=/app:$PYTHONPATH
ENV FRANK_ENVIRONMENT=aws
ENV HOST=0.0.0.0
ENV PORT=8000
ENV UVICORN_LOG_LEVEL=debug
ENV UVICORN_ACCESS_LOG=true

# Change ownership to frankuser
RUN chown -R frankuser:frankuser /app

# Switch to non-root user
USER frankuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

# Run the application
CMD ["python", "${APP_NAME}"]