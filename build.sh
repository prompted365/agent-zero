#!/usr/bin/env bash
set -e

# Install main and dev dependencies
pip install -r requirements.txt
if [ -f requirements-dev.txt ]; then
    pip install -r requirements-dev.txt
fi

# Run test suite
pytest tests

# Build Docker image for agent runtime
BRANCH=${BRANCH:-development}
CACHE_DATE=$(date +%Y-%m-%d:%H:%M:%S)

docker build -f docker/run/Dockerfile -t agent-zero-run:local \
  --build-arg BRANCH=$BRANCH \
  --build-arg CACHE_DATE=$CACHE_DATE .

echo "Build complete"
