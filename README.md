# DeepFellow Command Line Interface

## Installation

```bash
curl -fsSL https://deepfellow.com/install.sh | bash
```

## Development

Clone and then create the virtual environment

```bash
uv venv --python 3.10
```

Install locally to avoid using the `just df`

```bash
uv pip install -e .
```

The `deepfellow` command will install to the virtual environment (typically `./.venv/bin/deepfellow`). Ensure it's available in the `PATH`.
