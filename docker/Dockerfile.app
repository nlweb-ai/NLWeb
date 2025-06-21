# Application-specific Dockerfile for NLWeb
# This extends the base image and adds application-specific configurations

# Use the base image we created in Dockerfile.base
FROM nlweb-base:latest

# Switch to the non-root user created in the base image
USER nlweb

# Copy application code
COPY code/ /app/
COPY static/ /app/static/

# Expose the port the app runs on
EXPOSE 8000

# Set application-specific environment variables
ENV NLWEB_OUTPUT_DIR=/app

# Command to run the application
CMD ["python", "app-file.py"]
