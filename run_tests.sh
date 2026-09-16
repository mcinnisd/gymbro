#!/bin/bash

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install test dependencies if needed (optional check)
# pip install pytest pytest-mock

# Run tests
echo "Running tests..."
MOCK_DB=true PYTHONPATH=. ./venv/bin/python -m pytest tests/ -v "$@"
