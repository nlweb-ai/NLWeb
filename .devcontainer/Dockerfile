# .devcontainer/Dockerfile
FROM python:3.11-slim

# Install Rust (for building packages like cryptography, orjson, etc.)
RUN apt-get update && \
    apt-get install -y curl build-essential && \
    curl https://sh.rustup.rs -sSf | sh -s -- -y && \
    . "$HOME/.cargo/env"

# Add Rust to PATH for login shells
ENV PATH="/root/.cargo/bin:$PATH"

# Install project dependencies
COPY code/requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

# Set working directory
WORKDIR /workspace

RUN apt-get update && apt-get install -y git