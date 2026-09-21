# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""MCP server management core logic for the infra module."""

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InfraInstallSkippedError
from deepfellow.common.rest import make_request
from deepfellow.common.state import state
from deepfellow.common.validation import validate_port
from deepfellow.infra.utils.connection import call_infra, is_installed, resolve_infra_connection
from deepfellow.infra.utils.fields import build_spec_from_fields, format_field, parse_set_args, parse_spec_json
from deepfellow.infra.utils.models import get_service_models
from deepfellow.infra.utils.progress import install_with_progress

MCP_SERVICE_ID = "mcp"

# Spec fields that may carry credentials (env vars, HTTP headers, OAuth secrets) and must never be
# printed in plaintext.
_SENSITIVE_SPEC_FIELDS = {"envs", "headers", "oauth"}

# Matches a credential-looking "key=value"/"key: value" token embedded in a free-form string (e.g.
# a `docker run -e GITHUB_TOKEN=ghp_xxx` argument, or a `?token=...` query string), so those fields
# still get their secret masked even though they aren't in `_SENSITIVE_SPEC_FIELDS`.
_EMBEDDED_SECRET_PATTERN = re.compile(
    r"(?i)\b([\w.-]*(?:key|token|secret|password|credential|auth)[\w.-]*)\s*[:=]\s*(\S+)"
)

# Matches an `Authorization: Bearer <token>`-style header value embedded in a free-form string
# (e.g. a `--header` argument). Applied before `_EMBEDDED_SECRET_PATTERN`, which would otherwise
# only mask the word "Bearer" itself and leave the actual token that follows it untouched.
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)\bBearer\s+(\S+)")

# Matches a CLI-flag-looking string whose name suggests it carries a credential (e.g. `--api-key`,
# `-token`), so the *next* element of an `args`-style list can be masked too - a config's args are
# stored as separate `["--api-key", "sk-..."]` list elements, not a single "key=value" string.
_SECRET_FLAG_PATTERN = re.compile(r"(?i)^-{1,2}[\w-]*(?:key|token|secret|password|credential|auth)[\w-]*$")


def _mask(value: Any) -> Any:
    """Mask a credential-bearing field's value, preserving dict keys for readability."""
    if isinstance(value, dict):
        return dict.fromkeys(value, "*****")
    return "*****"


def _mask_embedded_secrets(text: str) -> str:
    """Mask credential-looking key=value tokens and Bearer tokens embedded inside a free-form string."""
    text = _BEARER_TOKEN_PATTERN.sub("Bearer *****", text)
    return _EMBEDDED_SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=*****", text)


def _redact_list(items: list[Any]) -> list[Any]:
    """Redact a spec list, masking dicts/strings and the value following a secret-looking flag.

    Handles the canonical MCP `args` shape (e.g. `["--api-key", "sk-..."]`), where a flag and its
    value are separate list elements rather than a single "key=value" string.
    """
    redacted: list[Any] = []
    mask_next = False
    for item in items:
        if mask_next:
            redacted.append("*****" if isinstance(item, str) else item)
            mask_next = False
            continue
        if isinstance(item, dict):
            redacted.append(_redact_sensitive_fields(item))
        elif isinstance(item, str):
            redacted.append(_mask_embedded_secrets(item))
            mask_next = bool(_SECRET_FLAG_PATTERN.match(item))
        else:
            redacted.append(item)
    return redacted


def _redact_sensitive_fields(spec: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a spec/status dict with credential-bearing fields masked for display.

    Recurses into nested dicts and lists of dicts so a sensitive field buried under an
    unrelated key (e.g. a nested spec inside `installed`) is masked as well. Fields outside the
    known-sensitive allowlist (e.g. `command`, `args`, `server_url`) are still scanned for
    embedded credential-looking tokens, since a Docker-run or URL-based config can carry secrets
    in those fields too.
    """
    redacted: dict[str, Any] = {}
    for key, value in spec.items():
        if key in _SENSITIVE_SPEC_FIELDS:
            redacted[key] = _mask(value)
        elif isinstance(value, dict):
            redacted[key] = _redact_sensitive_fields(value)
        elif isinstance(value, list):
            redacted[key] = _redact_list(value)
        elif isinstance(value, str):
            redacted[key] = _mask_embedded_secrets(value)
        else:
            redacted[key] = value
    return redacted


@dataclass
class McpServer:
    """A provisioned MCP server, as reported by `GET /admin/services/mcp/models`.

    `custom_spec` (the launch parameters, e.g. `command`/`args`/`envs`/`server_url`) is a custom
    model's own field, separate from `installed`. `fields` is the entry's install-form field
    schema (its `spec.fields` — `name`/`type`/`description`/`required`/`default` per field), the
    same shape `mcp install` resolves a spec from; it describes what installing this model would
    require (e.g. `brave-search` needing `BRAVE_API_KEY`), not a specific server's actual
    configuration, so it is unrelated to `custom_spec`.
    """

    id: str
    kind: str
    installed: bool | dict[str, Any]
    custom_model_id: str | None
    custom_spec: dict[str, Any] | None = None
    description: str | None = None
    fields: list[dict[str, Any]] | None = None

    def __str__(self) -> str:
        """Human-readable representation of the McpServer.

        `custom_model_id` is an internal id the user never has to pass to any command (they
        always refer to a server by name), so it's only shown in debug mode. `custom_spec`, when
        present, is shown separately from the `installed` status line under `parameters:` so the
        launch parameters aren't mistaken for part of the status. `fields` is shown only while the
        model isn't installed yet - once it is, either `parameters:` above already shows its real
        configuration (a custom model), or the install-form fields no longer describe anything
        actionable (a built-in one), so the same schema `mcp install` would resolve against is not
        worth repeating.
        """
        # `installed` is a plain bool for every model reported by this endpoint, but treat any
        # non-False value as installed (see `deepfellow.infra.utils.connection.is_installed`) in
        # case the backend ever reports it as a dict of runtime config here too.
        installed = is_installed(self.installed)
        lines = [
            f"id: {self.id}",
            f"kind: {self.kind}",
            f"installed: {installed}",
        ]
        if self.description:
            lines.append(f"description: {self.description}")
        if self.custom_spec:
            redacted_spec = _redact_sensitive_fields(self.custom_spec)
            lines.append("parameters:")
            lines.extend(f"  {key}: {value}" for key, value in redacted_spec.items())
        if self.fields and not installed:
            # Not filtered to `required: True` fields: a field can be optional at the schema
            # level while its `description` still names a required sub-value (e.g. `envs` for
            # brave-search is schema-optional but its description reads "Required variables:
            # BRAVE_API_KEY") - the full list is what the WebUI's install form shows too.
            lines.append("fields:")
            lines.extend(f"  {format_field(field)}" for field in self.fields)
        if state.debug:
            lines.append(f"custom_model_id: {self.custom_model_id}")
        return "\n".join(lines)


def ensure_name_available(name: str, server: str | None = None) -> str:
    """Raise if `name` is already registered (built-in or custom); otherwise return the resolved server URL.

    Meant to be called by the `add` command before it does anything else - before even asking for
    or reading a config - so a name collision is reported immediately. Infra's own provisioning
    endpoint also rejects a collision, but only after the config has already been converted and,
    for a Docker-image config, the user has been prompted for --prefix/--image-port, wasting that
    effort on a request that was always going to fail. The resolved server is returned so the
    caller can pass it on to `add`, avoiding a second interactive URL prompt on a brand-new setup
    that has no server configured yet.
    """
    server, api_key = resolve_infra_connection(server)
    existing = next((server_ for server_ in _list(server, api_key, quiet=True) if server_.id == name), None)
    if existing is not None:
        if existing.custom_model_id is None:
            echo.error(f"MCP server '{name}' is a built-in model. Choose a different name for your custom server.")
        else:
            echo.error(
                f"MCP server '{name}' already exists. Choose a different name, or run `mcp uninstall {name} "
                "--purge` first."
            )
        raise typer.Exit(1)
    return server


def add(
    name: str,
    config: dict[str, Any],
    server: str | None = None,
    prefix: str | None = None,
    image_port: int | None = None,
    stdin_is_tty: bool = True,
) -> str:
    """Convert a standard MCP client config and provision it as a custom model on the mcp service.

    Returns the custom model id.
    """
    server, api_key = resolve_infra_connection(server)

    spec = call_infra(
        lambda: make_request(
            method="POST",
            url=f"{server}/admin/mcp/convert-config",
            token=api_key,
            data={"config": config},
            err_msg="Unable to convert MCP config.",
            reraise=True,
        ),
        "Unable to convert MCP config.",
    )
    if not isinstance(spec, dict):
        echo.error("Unexpected response converting MCP config.")
        raise typer.Exit(1)

    display_spec = _redact_sensitive_fields(spec)
    echo.info("Converted MCP server config:\n" + "\n".join(f"{key}: {value}" for key, value in display_spec.items()))

    if spec.get("kind") == "custom":
        # A docker-run-based config can't be fully provisioned from the converted spec alone: the
        # backend can't infer a Docker image's listening port or endpoint prefix from `docker run`
        # arguments, so it requires both when adding a custom model (the WebUI collects them via
        # an extra form step after conversion — there is no CLI equivalent, so ask here instead).
        if not stdin_is_tty and (prefix is None or image_port is None):
            # Without a TTY on stdin (piped/redirected, whether or not it was also the config
            # source) a follow-up interactive prompt would hit an exhausted stream and crash with
            # EOFError instead of asking the user.
            echo.error("This MCP config requires --prefix and --image-port when the config is piped on stdin.")
            raise typer.Exit(1)

        spec["default_prefix"] = echo.prompt("Default endpoint prefix for this MCP server", from_args=prefix)
        image_port_arg = str(image_port) if image_port is not None else None
        spec["image_port"] = echo.prompt_until_valid(
            "Docker image port",
            validate_port,
            error_message="Invalid port - must be a number between 1 and 65535.",
            from_args=image_port_arg,
        )

    spec["id"] = name
    spec["name"] = name

    data = call_infra(
        lambda: make_request(
            method="POST",
            url=f"{server}/admin/services/{MCP_SERVICE_ID}/models/custom",
            token=api_key,
            data={"spec": spec},
            err_msg="Unable to add MCP server.",
            reraise=True,
        ),
        "Unable to add MCP server.",
        server=server,
        api_key=api_key,
    )
    if not isinstance(data, dict) or data.get("custom_model_id") is None:
        echo.error("MCP server was added, but the response was missing 'custom_model_id'.")
        raise typer.Exit(1)
    return str(data["custom_model_id"])


def list_servers(server: str | None = None) -> list[McpServer]:
    """List MCP servers (models of the mcp service)."""
    server, api_key = resolve_infra_connection(server)
    # quiet=True: a read-only list shouldn't re-announce "Updated config/secrets" every time it's
    # run against an already-known, already-working connection.
    return _list(server, api_key, quiet=True)


def _fetch_models(server: str, api_key: str, quiet: bool = False) -> list[dict[str, Any]]:
    """Fetch the raw list of mcp service models (built-in and custom)."""
    return get_service_models(server, api_key, MCP_SERVICE_ID, quiet=quiet, err_msg="Unable to list MCP servers.")


def _list(server: str, api_key: str, quiet: bool = False) -> list[McpServer]:
    """List MCP servers using an already-resolved connection."""
    servers = []
    for item in _fetch_models(server, api_key, quiet=quiet):
        spec = item.get("spec")
        servers.append(
            McpServer(
                id=item.get("id", ""),
                kind=item.get("type", ""),
                installed=item.get("installed", False),
                custom_model_id=item.get("custom"),
                custom_spec=item.get("custom_spec") if isinstance(item.get("custom_spec"), dict) else None,
                description=item.get("description") if isinstance(item.get("description"), str) else None,
                fields=spec.get("fields") if isinstance(spec, dict) else None,
            )
        )
    return servers


def _fetch_model_fields(server: str, api_key: str, name: str) -> list[dict[str, Any]]:
    """Fetch a single MCP model's install-form field schema by id.

    This is the same `spec.fields` shape `mcp list` deliberately ignores when showing a server's
    status (see `McpServer`) - here it is exactly what's needed: the fields Infra requires to
    install this model, e.g. `brave-search`'s `envs` field description naming `BRAVE_API_KEY` as
    required, matching what the WebUI's install form shows.
    """
    for item in _fetch_models(server, api_key, quiet=True):
        if item.get("id") == name:
            spec = item.get("spec")
            return spec.get("fields", []) if isinstance(spec, dict) else []

    echo.error(f"MCP server '{name}' not found.")
    raise typer.Exit(1)


def install(
    name: str,
    server: str | None = None,
    api_key: str | None = None,
    spec: str | None = None,
    set_args: list[str] | None = None,
    prompt_all: bool = True,
) -> None:
    """Install (start) an MCP model - a built-in one from Infra's catalog, or a custom one already registered via `add`.

    Prompts for any field the model's install-form schema marks as required (e.g. `brave-search`
    needs a `BRAVE_API_KEY`) unless it's supplied via `--set`/`--spec`, mirroring `service install`.
    A model added via `mcp add` typically needs no field values here - its configuration was
    already baked into its custom spec at `add` time - but still needs this call to actually be
    started, since `add` only registers it.
    """
    if spec is not None and not spec.strip():
        echo.error("--spec cannot be empty.")
        raise typer.Exit(1)
    if spec is not None and set_args:
        echo.error("--spec and --set cannot be used together. Use one or the other.")
        raise typer.Exit(1)

    server, api_key_resolved = resolve_infra_connection(server)

    if spec is not None:
        resolved_spec = parse_spec_json(spec)
    else:
        model_fields = _fetch_model_fields(server, api_key_resolved, name)
        set_values = parse_set_args(set_args or [])
        resolved_spec = build_spec_from_fields(model_fields, set_values, api_key, prompt_all=prompt_all)

    url = f"{server}/admin/services/{MCP_SERVICE_ID}/models/_?model_id={quote(name, safe='')}"

    try:
        data = call_infra(
            lambda: install_with_progress(url, api_key_resolved, data={"spec": resolved_spec}),
            "Unable to install MCP server.",
            server=server,
            api_key=api_key_resolved,
            quiet=spec is None,
            skip_if_message_contains="already installed",
        )
    except InfraInstallSkippedError:
        echo.info(f"MCP server '{name}' is already installed; skipping.")
        return

    if data.get("status", "").lower() != "ok":
        message = data.get("details")
        echo.error(f"Unable to install MCP server.{f' {message}' if message else ''}")
        if not message:
            echo.error("Check `docker compose logs infra` for details.")
        raise typer.Exit(1)

    echo.success(f"MCP server '{name}' installed.")


def uninstall(name: str, server: str | None = None, purge: bool = False) -> None:
    """Uninstall (stop) an MCP model instance by id - built-in or custom - mirroring `infra model uninstall`.

    Unlike `remove`, this does not touch a custom model's registration - it only stops/removes the
    running instance, so it works for built-in models too (e.g. `duckduckgo`). Use `remove` to
    delete a custom model's registration from the models list entirely.
    """
    server, api_key = resolve_infra_connection(server)

    url = f"{server}/admin/services/{MCP_SERVICE_ID}/models/_?model_id={quote(name, safe='')}"

    data = call_infra(
        lambda: make_request(
            method="DELETE",
            url=url,
            token=api_key,
            data={"purge": purge},
            err_msg="Unable to uninstall MCP server.",
            reraise=True,
        ),
        "Unable to uninstall MCP server.",
        server=server,
        api_key=api_key,
        quiet=True,
    )

    if data.get("status", "").lower() != "ok":
        echo.error("Unable to uninstall MCP server.")
        raise typer.Exit(1)


def remove(name: str, server: str | None = None) -> None:
    """Remove a custom MCP server's registration from the models list by name.

    Only valid for a custom model (one added via `mcp add`) - a built-in model's entry is not a
    registration that can be deleted, so it is rejected by `_find_by_name` instead.
    """
    server, api_key = resolve_infra_connection(server)

    mcp_server = _find_by_name(_list(server, api_key, quiet=True), name)

    data = call_infra(
        lambda: make_request(
            method="DELETE",
            url=f"{server}/admin/services/{MCP_SERVICE_ID}/models/custom/{mcp_server.custom_model_id}",
            token=api_key,
            err_msg="Unable to remove MCP server.",
            reraise=True,
        ),
        "Unable to remove MCP server.",
        server=server,
        api_key=api_key,
        quiet=True,
    )

    if data.get("status", "").lower() != "ok":
        echo.error("Unable to remove MCP server.")
        raise typer.Exit(1)


def _find_by_name(servers: list[McpServer], name: str) -> McpServer:
    """Find a provisioned MCP server by name, raising if not found or not removable."""
    for mcp_server in servers:
        if mcp_server.id == name:
            if mcp_server.custom_model_id is None:
                echo.error(
                    f"MCP server '{name}' is a built-in model and cannot be removed. "
                    f"Use `mcp uninstall {name} --purge` instead."
                )
                raise typer.Exit(1)
            return mcp_server

    echo.error(f"MCP server '{name}' not found.")
    raise typer.Exit(1)
