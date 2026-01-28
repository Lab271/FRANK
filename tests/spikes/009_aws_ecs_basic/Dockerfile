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
RUN echo "fastapi==0.104.1" > requirements.txt && \
    echo "uvicorn[standard]==0.24.0" >> requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# ===================================
# Production Stage
# ===================================

FROM base AS production

# Create non-root user
RUN groupadd -r frankuser && useradd -r -g frankuser frankuser

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/frankuser/.local

# Copy application code
COPY simple_api.py .

# Set environment variables
ENV PATH=/home/frankuser/.local/bin:$PATH
# ENV PYTHONPATH=/app:$PYTHONPATH
ENV FRANK_ENVIRONMENT=aws
ENV HOST=0.0.0.0
ENV PORT=8000

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
CMD ["python", "simple_api.py"]