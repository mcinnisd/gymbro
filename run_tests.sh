#!/bin/bash

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install test dependencies if needed (optional check)
# pip install pytest pytest-mock

# Run tests
echo "Running tests..."
python -m pytest tests/ -v
