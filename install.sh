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
PYTHON_CMD=""
for cmd in python3 python; do
    if PYTHON_VERSION=$(check_python_version "$cmd"); then
        PYTHON_CMD="$cmd"
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
UPDATE_CMD=""

DEEPFELLOW_DIR="$HOME/.deepfellow"
VENV_DIR="$DEEPFELLOW_DIR/cli-venv"
BIN_DIR="$HOME/.local/bin"

# Install into a dedicated venv and link the entry point into $BIN_DIR. Used when pip
# refuses a --user install on an externally managed Python (PEP 668, e.g. Homebrew).
install_in_venv() {
    echo "Your Python is externally managed (PEP 668), installing into a dedicated venv at $VENV_DIR..."
    # Only clean up a venv created by this run, never a working one from a previous install.
    local venv_existed=false
    [ -d "$VENV_DIR" ] && venv_existed=true
    if ! "$PYTHON_CMD" -m venv "$VENV_DIR"; then
        [ "$venv_existed" = false ] && rm -rf "$VENV_DIR"
        echo "Error: Failed to create a virtual environment with $PYTHON_CMD."
        echo "Install the venv module (e.g. python3-venv) or install uv or pipx first, then re-run the installer."
        exit 1
    fi
    if ! "$VENV_DIR/bin/pip" install --upgrade "$INSTALL_TARGET"; then
        [ "$venv_existed" = false ] && rm -rf "$VENV_DIR"
        echo "Error: Failed to install deepfellow-cli into $VENV_DIR."
        exit 1
    fi
    mkdir -p "$BIN_DIR"
    ln -sf "$VENV_DIR/bin/deepfellow" "$BIN_DIR/deepfellow"

    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            echo ""
            echo "⚠ $BIN_DIR is not on your PATH. Add it to your shell profile:"
            echo "    export PATH=\"$BIN_DIR:\$PATH\""
            echo ""
            ;;
    esac

    UNINSTALL_CMD="rm -rf $(printf '%q' "$VENV_DIR") $(printf '%q' "$BIN_DIR/deepfellow")"
    UPDATE_CMD="$(printf '%q' "$VENV_DIR/bin/pip") install --upgrade $(printf '%q' "$INSTALL_TARGET")"
}

# Install with `<pip> install --user`, falling back to a dedicated venv on PEP 668.
# pip's stderr is held back so its PEP 668 advice (--break-system-packages) is not shown
# when the venv fallback takes over; any other stderr output is printed after pip exits.
pip_install_user() {
    local pip_cmd=$1
    local stderr_log
    stderr_log=$(mktemp)
    if "$pip_cmd" install --user "$INSTALL_TARGET" 2>"$stderr_log"; then
        cat "$stderr_log" >&2
        rm -f "$stderr_log"
        UNINSTALL_CMD="$pip_cmd uninstall deepfellow-cli -y"
        UPDATE_CMD="$pip_cmd install --user --upgrade deepfellow-cli"
        return 0
    fi
    if grep -q "externally-managed-environment" "$stderr_log"; then
        rm -f "$stderr_log"
        install_in_venv
        return 0
    fi
    cat "$stderr_log" >&2
    rm -f "$stderr_log"
    echo "Error: $pip_cmd failed to install deepfellow-cli."
    exit 1
}

if command -v uv &> /dev/null; then
    echo "Using uv tool install..."
    uv tool install "$INSTALL_TARGET"
    UNINSTALL_CMD="uv tool uninstall deepfellow-cli"
    UPDATE_CMD="uv tool upgrade deepfellow-cli"

elif command -v pipx &> /dev/null; then
    echo "Using pipx..."
    pipx install "$INSTALL_TARGET"
    UNINSTALL_CMD="pipx uninstall deepfellow-cli"
    UPDATE_CMD="pipx upgrade deepfellow-cli"

elif command -v pip3 &> /dev/null; then
    echo "Using pip3..."
    pip_install_user pip3

elif command -v pip &> /dev/null; then
    echo "Using pip..."
    pip_install_user pip

else
    echo "Error: No package manager found. Please install Python package manager first (uv / pipx / pip3 / pip)."
    exit 1
fi

# Save the uninstall and update commands so `deepfellow cli uninstall`/`update` can use them later.
mkdir -p "$DEEPFELLOW_DIR"
CONFIG_FILE="$DEEPFELLOW_DIR/config"
if [ -f "$CONFIG_FILE" ]; then
    grep -vE "^(DF_UNINSTALL_COMMAND|DF_UPDATE_COMMAND)=" "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
fi
printf "DF_UNINSTALL_COMMAND=%s\n" "$UNINSTALL_CMD" >> "$CONFIG_FILE"
printf "DF_UPDATE_COMMAND=%s\n" "$UPDATE_CMD" >> "$CONFIG_FILE"

echo "✅ Installed successfully!"
