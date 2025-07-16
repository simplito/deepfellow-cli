# Installation

## Quick Start

### One-time use (recommended)

```bash
uvx deepfellow-cli --help
```

### Permanent installation

```bash
uv tool install deepfellow-cli
deepfellow --help
```

### Alternative: pipx

```bash
pipx install deepfellow-cli
deepfellow --help
```

### Universal installer (works anywhere)

```bash
curl -sSL https://install.deepfellow.com | bash
deepfellow --help
```

## Installation Methods

### 🚀 uv (Fastest)

**For one-time use:**

```bash
uvx deepfellow-cli [command]
```

This runs your tool directly without installing it permanently.

**For permanent installation:**

```bash
uv tool install deepfellow-cli
```

**Install from source:**

```bash
uv tool install git+https://github.com/seemplito/deepfellow-cli.git
```

### 📦 pipx (Python-focused)

```bash
pipx install deepfellow-cli
```

**Install from source:**

```bash
pipx install git+https://github.com/seemplito/deepfellow-cli.git
```

### 🌐 Universal Installer

For systems without uv or pipx, use our universal installer:

```bash
curl -sSL https://install.deepfellow.com | bash
```

**Review before installing:**

```bash
curl -sSL https://install.deepfellow.com | less
```

**Custom installation directory:**

```bash
curl -sSL https://install.deepfellow.com | bash -s -- --prefix ~/.local
```

### 🐍 pip (Traditional)

```bash
pip install --user deepfellow
```

**Note:** This method doesn't provide automatic isolation. Consider using uv or pipx instead.

## System Requirements

* Python 3.8 or higher
* Linux, macOS, or Windows (WSL)
* Internet connection for installation

## Verification

After installation, verify it works:

```bash
deepfellow --version
deepfellow --help
```

## Upgrading

### uv

```bash
uv tool upgrade deepfellow-cli
```

### pipx

```bash
pipx upgrade deepfellow-cli
```

### Universal installer

```bash
curl -sSL https://install.deepfellow.com | bash -s -- --upgrade
```

## Uninstalling

### uv

```bash
uv tool uninstall deepfellow-cli
```

### pipx

```bash
pipx uninstall deepfellow-cli
```

### Universal installer

```bash
deepfellow --uninstall
```

## Troubleshooting

### Command not found

If you get "command not found" after installation:

1. **Check your PATH:** Ensure the installation directory is in your PATH

   ```bash
   echo $PATH
   ```

2. **Reload your shell:**

   ```bash
   source ~/.bashrc  # or ~/.zshrc
   ```

3. **Find installation location:**

   ```bash
   # For uv
   uv tool list

   # For pipx
   pipx list
   ```

### Permission errors

If you encounter permission errors:

* **Don't use sudo** - use user-level installations
* Use `uv tool install` or `pipx install` instead of system pip
* Check your user's bin directory is writable

### Network issues

If downloads fail:

* Check your internet connection
* Try installing from PyPI directly: `pip install deepfellow-cli`
* Use a different mirror or wait and retry

### Python version issues

If you get Python version errors:

* Check your Python version: `python --version`
* Ensure Python 3.12+ is installed
* Consider using pyenv to manage Python versions

## Advanced Installation

### Development Version

```bash
# Latest from main branch
uv tool install git+git+https://github.com/seemplito/deepfellow-cli.git

# Specific branch
uv tool install git+git+https://github.com/seemplito/deepfellow-cli.git@develop
```

### Editable Installation (for development)

```bash
git clone git+https://github.com/seemplito/deepfellow-cli.git
cd deepfellow-cli
uv tool install --editable .
```

### Offline Installation

```bash
# Download wheel
pip download deepfellow-cli

# Install from wheel
uv tool install ./deepfellow-*.whl
```

## Getting Help

* 📖 [Full Documentation](https://docs.deepfellow.com)
* 🐛 [Report Issues](https://github.com/simplito/deepfellow/issues)
* 💬 [Discussions](https://github.com/simplito/deepfellow/discussions)
* 📧 [Email Support](mailto:support@deepfellow.com)
