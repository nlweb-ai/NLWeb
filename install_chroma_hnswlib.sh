#!/bin/bash

# Force install chroma-hnswlib with specific wheel for Azure Web App
echo "Installing chroma-hnswlib with prebuilt wheel..."

# Detect Python version
PYTHON_VERSION=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo "Detected Python version: $PYTHON_VERSION"

# Set wheel URL based on Python version
if [[ "$PYTHON_VERSION" == "3.11" ]]; then
    WHEEL_URL="https://files.pythonhosted.org/packages/c7/2d/d5663e134436e5933bc63516a20b5edc08b4c1b1588b9680908a5f1afd04/chroma_hnswlib-0.7.6-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
elif [[ "$PYTHON_VERSION" == "3.12" ]]; then
    WHEEL_URL="https://files.pythonhosted.org/packages/20/41/1a0c96de5e4f7d091c3b68ad31c4797c60c97e6b12e1e96f228c24fa88e0/chroma_hnswlib-0.7.6-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
elif [[ "$PYTHON_VERSION" == "3.10" ]]; then
    WHEEL_URL="https://files.pythonhosted.org/packages/85/cd/23e8f4b2070074d38a2e6c9c1bb3c5a1a27630a67c563e4e35cc31f029e8/chroma_hnswlib-0.7.6-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
else
    echo "Unsupported Python version: $PYTHON_VERSION"
    echo "Falling back to standard pip install"
    pip install chroma-hnswlib
    exit $?
fi

echo "Installing from wheel: $WHEEL_URL"

# First install numpy (dependency)
pip install numpy

# Install directly from wheel URL
pip install --force-reinstall --no-deps "$WHEEL_URL"

# Verify installation
python -c "import hnswlib; print('chroma-hnswlib installed successfully')" || {
    echo "Installation verification failed"
    exit 1
}

echo "chroma-hnswlib installation complete!"