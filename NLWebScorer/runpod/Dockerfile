FROM pytorch/pytorch:2.4.1-cuda12.4-cudnn9-devel

WORKDIR /workspace

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl vim && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /workspace/NLWebScorer

WORKDIR /workspace/NLWebScorer

CMD ["bash"]
