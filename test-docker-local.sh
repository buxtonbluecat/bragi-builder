#!/bin/bash
# Test Docker build and run locally

set -e

echo "🐳 Testing Docker Build Locally"
echo "================================"
echo ""

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running."
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "✓ Docker is running"
echo ""

# Build the image
echo "🔨 Building Docker image..."
docker build -t bragi-builder:test .
echo ""

# Check if build was successful
if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully!"
    echo ""
    
    # Stop any existing container
    docker stop bragi-test 2>/dev/null || true
    docker rm bragi-test 2>/dev/null || true
    
    # Run the container
    echo "🚀 Starting container..."
    echo "App will be available at: http://localhost:8000"
    echo ""
    echo "Press Ctrl+C to stop the container"
    echo ""
    
    docker run -it --rm \
        --name bragi-test \
        -p 8000:8000 \
        -e PORT=8000 \
        -e SECRET_KEY="test-secret-key-for-local-testing" \
        bragi-builder:test
else
    echo "❌ Docker build failed"
    exit 1
fi




