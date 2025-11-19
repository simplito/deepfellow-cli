#!/bin/bash
set -e

REPO_URL="https://github.com/simplito/deepfellow-cli.git"
MIN_PYTHON_VERSION="3.10"


echo "Installing deepfellow..."

# Function to check Python version
check_python_version() {
    local python_cmd=$1
    if command -v "$python_cmd" &> /dev/null; then
        local version=$("$python_cmd" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if [ "$(printf '%s\n' "$MIN_PYTHON_VERSION" "$version" | sort -V | head -n1)" = "$MIN_PYTHON_VERSION" ]; then
            echo "$version"
            return 0
        fi
    fi
    return 1
}

# Check for Python 3.10+
PYTHON_VERSION=""
for cmd in python3 python; do
    if PYTHON_VERSION=$(check_python_version "$cmd"); then
        echo "✓ Found Python $PYTHON_VERSION"
        break
    fi
done

if [ -z "$PYTHON_VERSION" ]; then
    echo "Error: Python $MIN_PYTHON_VERSION or higher is required."
    echo "Please install Python from https://www.python.org/downloads/"
    exit 1
fi

if command -v uv &> /dev/null; then
    echo "Using uv tool install..."
    uv tool install "git+$REPO_URL"

elif command -v pipx &> /dev/null; then
    echo "Using pipx..."
    pipx install "git+$REPO_URL"

elif command -v pip3 &> /dev/null; then
    echo "Using pip3..."
    pip3 install "git+$REPO_URL"

elif command -v pip &> /dev/null; then
    echo "Using pip..."
    pip install "git+$REPO_URL"

else
    echo "Error: No package manager found. Please install Python first."
    exit 1
fi

echo "✅ Installed successfully!"
