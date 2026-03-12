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

# Expose port 8000 for FastAPI backend
EXPOSE 8000

# Run only the backend API
CMD ["sh", "-c", "cd src && python -m uvicorn main:app --host 0.0.0.0 --port 8000"]
