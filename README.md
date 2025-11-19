# DeepFellow Command Line Interface

## Installation

```bash
curl -fsSL https://deepfellow.ai/install.sh | bash
```

## Development

### Local installtion

Clone and then create the virtual environment

```bash
uv venv --python 3.10
```

Install locally to avoid using the `just df`

```bash
uv pip install -e .
```

The `deepfellow` command will install to the virtual environment (typically `./.venv/bin/deepfellow`). Ensure it's available in the `PATH`.

### Chaning image to development

To set latest development images for DeepFellow Server and DeepFellow Infra, export enviromental variables.

Pattern for Linux based OS:
```bash
export DF_INFRA_IMAGE={infra_image}:dev
export DF_SERVER_IMAGE={server_img}:dev
```

Actual existing images you can find in `deepfellow/common/defaults.py`

Example for Linux based OS:
```bash
export DF_INFRA_IMAGE=hub.simplito.com/deepfellow/deepfellow-infra:latest
export DF_SERVER_IMAGE=hub.simplito.com/deepfellow/deepfellow-server:latest
```

To remember it in every new terminal. Save it into `~/.zshrc` or `~/.bashrc` and source to work in existing terminal.
