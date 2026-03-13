# Multi-stage Dockerfile for Expense AI Assistant

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/

# Create logs directory
RUN mkdir -p logs

# Expose a default port (metadata only); runtime will use $PORT if provided
EXPOSE 8000

# Run only the backend API. Use the environment-provided $PORT (Railway sets $PORT).
# Fall back to 8000 when $PORT is not provided to keep local behavior unchanged.
CMD ["sh", "-c", "cd src && python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
