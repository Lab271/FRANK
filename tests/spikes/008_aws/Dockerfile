# ===================================
# Dockerfile for 008_aws_spike.py
# Simple FastAPI application for AWS ECS deployment
# ===================================

FROM python:3.11-slim AS builder

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

FROM python:3.11-slim AS production

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
COPY 008_aws_spike.py .

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
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "008_aws_spike.py"]