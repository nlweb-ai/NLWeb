# Stage 1: Build stage
FROM python:3.13-slim AS builder

WORKDIR /app

# Copy requirements file
COPY code/requirements.txt .

# Install build dependencies and Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Stage 2: Runtime stage
FROM python:3.13-slim

# Update system packages for security
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-root user and set permissions
RUN groupadd -r nlweb && \
    useradd -r -g nlweb -d /app -s /bin/bash nlweb && \
    chown -R nlweb:nlweb /app

USER nlweb

# Copy application code
COPY code/ /app/
COPY static/ /app/static/

# Remove local logs and .env file
RUN rm -r code/logs/* || true && \
    rm -r code/.env || true

    # Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000

# Command to run the application
CMD ["python", "app-file.py"]
