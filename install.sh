#!/bin/bash
set -e

REPO_URL="https://github.com/simplito/deepfellow-cli.git"
DEV_REPO_URL="https://gitlab2.simplito.com/df/df-cli.git"
MIN_PYTHON_VERSION="3.10"

# Parse arguments
DEV=false
for arg in "$@"; do
    case "$arg" in
        --dev)
            DEV=true
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Usage: install.sh [--dev]"
            exit 1
            ;;
    esac
done

# Select install target: latest release from GitHub (default) or main from GitLab (--dev)
if [ "$DEV" = true ]; then
    INSTALL_TARGET="git+$DEV_REPO_URL@main"
    echo "Installing deepfellow (dev: GitLab main)..."
else
    INSTALL_TARGET="git+$REPO_URL"
    echo "Installing deepfellow..."
fi

# Allow overriding the install source (used by the CI smoke test to install the
# current checkout instead of a remote git URL). Not intended for end users.
INSTALL_TARGET="${DF_INSTALL_TARGET:-$INSTALL_TARGET}"

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

UNINSTALL_CMD=""

if command -v uv &> /dev/null; then
    echo "Using uv tool install..."
    uv tool install "$INSTALL_TARGET"
    UNINSTALL_CMD="uv tool uninstall deepfellow-cli"

elif command -v pipx &> /dev/null; then
    echo "Using pipx..."
    pipx install "$INSTALL_TARGET"
    UNINSTALL_CMD="pipx uninstall deepfellow-cli"

elif command -v pip3 &> /dev/null; then
    echo "Using pip3..."
    if ! pip3 install --user "$INSTALL_TARGET" 2>/dev/null; then
        echo ""
        echo "⚠ Your system uses PEP 668 protection (externally-managed-environment)."
        echo "This prevents pip from installing packages globally."
        echo ""
        read -p "Install with --break-system-packages? [y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            pip3 install --user --break-system-packages "$INSTALL_TARGET"
        else
            echo "Installation cancelled. Consider installing uv or pipx first."
            exit 1
        fi
    fi
    UNINSTALL_CMD="pip3 uninstall deepfellow-cli -y"

elif command -v pip &> /dev/null; then
    echo "Using pip..."
    if ! pip install --user "$INSTALL_TARGET" 2>/dev/null; then
        echo ""
        echo "⚠ Your system uses PEP 668 protection (externally-managed-environment)."
        echo "This prevents pip from installing packages globally."
        echo ""
        read -p "Install with --break-system-packages? [y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            pip install --user --break-system-packages "$INSTALL_TARGET"
        else
            echo "Installation cancelled. Consider installing uv or pipx first."
            exit 1
        fi
    fi
    UNINSTALL_CMD="pip uninstall deepfellow-cli -y"

else
    echo "Error: No package manager found. Please install Python package manager first (uv / pipx / pip3 / pip)."
    exit 1
fi

# Save the uninstall command so `deepfellow cli uninstall` can use it later.
DEEPFELLOW_DIR="$HOME/.deepfellow"
mkdir -p "$DEEPFELLOW_DIR"
CONFIG_FILE="$DEEPFELLOW_DIR/config"
if [ -f "$CONFIG_FILE" ]; then
    grep -v "^DF_UNINSTALL_COMMAND=" "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
fi
printf "DF_UNINSTALL_COMMAND=%s\n" "$UNINSTALL_CMD" >> "$CONFIG_FILE"

echo "✅ Installed successfully!"
