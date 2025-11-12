# Multi-stage Docker build for production deployment
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN groupadd -r trader && useradd -r -g trader trader

# Production stage
FROM base as production

# Create application directories
RUN mkdir -p /app /var/log/condition_task_list_trader /app/data \
    && chown -R trader:trader /app /var/log/condition_task_list_trader /app/data

# Copy application code
COPY --chown=trader:trader . /app/

# Set user
USER trader

# Expose ports for health checks and metrics
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default entrypoint
ENTRYPOINT ["python", "/app/production_main.py"]
