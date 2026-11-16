# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import stat
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.defaults import (
    DF_WORKSPACE_IMAGE,
    MONGO_IMAGE,
    WORKSPACE_MONGO_SERVICE,
    WORKSPACE_REDIS_IMAGE,
    WORKSPACE_REDIS_SERVICE,
)
from deepfellow.common.docker import load_compose_file
from deepfellow.common.exceptions import DockerNetworkError, InstallError
from deepfellow.workspace.utils.install import (
    apply_local_image,
    apply_service_images,
    build_compose,
    build_env,
    current_service_images,
    has_unprotected_mongo,
    incomplete_groups,
    install,
    missing_values,
    protect_existing_mongo,
    read_existing_env,
    read_installed_env,
    resolve_local_image,
    resolve_stack_settings,
    validate_env,
    write_stack,
)

PASSED: dict[str, str | None] = {
    "DF_SERVER_URL": "https://df.example.com/v1",
    "DF_SERVER_API_KEY": "key",
    "DF_SERVER_ORGANIZATION_ID": "org",
    "DF_SERVER_PROJECT_ID": "proj",
    "SMALL_MODEL": "small",
}

STACK_ENV: dict[str, str] = {
    **{key: value for key, value in PASSED.items() if value},
    "DF_WORKSPACE_IMAGE": "img:2",
    "DF_WORKSPACE_PORT": "3001",
    "DF_WORKSPACE_BIND_ADDRESS": "127.0.0.1",
    "DF_WORKSPACE_DOCKER_NETWORK": "net",
}


def _install(
    directory: Path,
    existing: dict[str, str] | None = None,
    passed: dict[str, str | None] | None = None,
    force: bool = False,
) -> dict[str, str]:
    return install(directory, "img:1", 3000, "", "net", existing or {}, PASSED if passed is None else passed, force)


def test_default_image_is_pinned_to_v0_7_1() -> None:
    assert DF_WORKSPACE_IMAGE.endswith("deepfellow-workspace:v0.7.1")


def test_build_compose_local_image_never_pulls_the_app_image() -> None:
    compose = build_compose("img:1", 3000, "", "net", local_image=True)

    assert compose["services"]["workspace"]["pull_policy"] == "never"


def test_build_compose_registry_image_has_no_pull_policy() -> None:
    compose = build_compose("img:1", 3000, "", "net")

    assert "pull_policy" not in compose["services"]["workspace"]


@pytest.mark.parametrize(
    ("existing", "given", "expected"),
    [
        ({}, None, False),
        ({"DF_WORKSPACE_LOCAL_IMAGE": "true"}, None, True),
        ({"DF_WORKSPACE_LOCAL_IMAGE": "true"}, False, False),
        ({}, True, True),
    ],
)
def test_resolve_local_image_prefers_given_choice_then_previous_install(
    existing: dict[str, str], given: bool | None, expected: bool
) -> None:
    assert resolve_local_image(existing, given) is expected


def test_apply_local_image_sets_marker_when_local() -> None:
    env: dict[str, str] = {}

    reset = apply_local_image(env, True)

    assert env == {"DF_WORKSPACE_LOCAL_IMAGE": "true"}
    assert reset == ()


def test_apply_local_image_drops_marker_when_not_local() -> None:
    env = {"DF_WORKSPACE_LOCAL_IMAGE": "true"}

    reset = apply_local_image(env, False)

    assert env == {}
    assert reset == ("DF_WORKSPACE_LOCAL_IMAGE",)


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_local_image_writes_marker_and_pull_policy(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    directory = tmp_path / "ws"

    install(directory, "img:1", 3000, "", "net", {}, PASSED, False, local_image=True)

    assert read_existing_env(directory)["DF_WORKSPACE_LOCAL_IMAGE"] == "true"
    assert load_compose_file(directory / "compose.yaml")["services"]["workspace"]["pull_policy"] == "never"


def test_build_compose_data_services_are_private() -> None:
    compose = build_compose("img:1", 3000, "", "net")

    for name in ("workspace-mongo-db", "workspace-redis"):
        service = compose["services"][name]
        assert "ports" not in service
        assert "networks" not in service


def test_build_compose_only_app_joins_infra_network_and_publishes_port() -> None:
    compose = build_compose("img:1", 3001, "127.0.0.1", "net")

    app = compose["services"]["workspace"]
    assert app["networks"] == ["default", "net"]
    assert app["ports"] == ["127.0.0.1:3001:3000"]
    assert app["image"] == "img:1"
    assert compose["networks"] == {"net": {"external": True}}


def test_build_compose_empty_bind_address_publishes_on_all_interfaces() -> None:
    compose = build_compose("img:1", 3000, "", "net")

    assert compose["services"]["workspace"]["ports"] == [":3000:3000"]


def test_build_compose_app_waits_for_healthy_mongo_and_redis() -> None:
    compose = build_compose("img:1", 3000, "", "net")

    app = compose["services"]["workspace"]
    assert app["depends_on"]["workspace-mongo-db"] == {"condition": "service_healthy"}
    assert app["depends_on"]["workspace-redis"] == {"condition": "service_healthy"}
    assert compose["services"]["workspace-redis"]["healthcheck"]["test"] == ["CMD", "redis-cli", "ping"]


def test_build_compose_app_uses_own_mongo_and_redis_and_declares_volume() -> None:
    compose = build_compose("img:1", 3000, "", "net")

    environment = compose["services"]["workspace"]["environment"]
    assert (
        "MONGO_DB_URL=mongodb://workspace:${DF_WORKSPACE_MONGO_PASSWORD}@workspace-mongo-db:27017/"
        "?replicaSet=rs0&authSource=admin"
    ) in environment
    assert "MONGO_DB_NAME=workspace_db" in environment
    assert "REDIS_URL=redis://workspace-redis:6379" in environment
    assert "workspace-mongo-db" in compose["volumes"]


def test_build_env_generates_app_secret_of_sufficient_length() -> None:
    env = build_env({}, PASSED, 3000)

    assert len(env["APP_SECRET"]) >= 32


def test_build_env_generates_mongo_password_and_keyfile_for_local_mongo() -> None:
    env = build_env({}, PASSED, 3000)

    assert len(env["DF_WORKSPACE_MONGO_PASSWORD"]) >= 32
    assert 6 <= len(env["DF_WORKSPACE_MONGO_KEY"]) <= 1024


def test_build_env_keeps_existing_mongo_password_and_keyfile() -> None:
    existing = {"DF_WORKSPACE_MONGO_PASSWORD": "pw", "DF_WORKSPACE_MONGO_KEY": "key"}

    env = build_env(existing, PASSED, 3000)

    assert env["DF_WORKSPACE_MONGO_PASSWORD"] == "pw"
    assert env["DF_WORKSPACE_MONGO_KEY"] == "key"


def test_build_env_skips_mongo_secrets_for_external_mongo() -> None:
    env = build_env({}, {**PASSED, "MONGO_DB_URL": "mongodb://x/"}, 3000)

    assert "DF_WORKSPACE_MONGO_PASSWORD" not in env
    assert "DF_WORKSPACE_MONGO_KEY" not in env


def test_build_env_generates_mcp_auth_token_when_none_given() -> None:
    env = build_env({}, PASSED, 3000)

    assert len(env["MCP_AUTH_TOKEN"]) >= 32


def test_build_env_keeps_existing_mcp_auth_token() -> None:
    env = build_env({"MCP_AUTH_TOKEN": "t" * 40}, PASSED, 3000)

    assert env["MCP_AUTH_TOKEN"] == "t" * 40


def test_build_env_passed_mcp_auth_token_replaces_existing() -> None:
    env = build_env({"MCP_AUTH_TOKEN": "t" * 40}, {**PASSED, "MCP_AUTH_TOKEN": "n" * 20}, 3000)

    assert env["MCP_AUTH_TOKEN"] == "n" * 20


def test_build_env_keeps_existing_app_secret() -> None:
    env = build_env({"APP_SECRET": "x" * 40}, PASSED, 3000)

    assert env["APP_SECRET"] == "x" * 40


def test_build_env_passed_value_overrides_existing_and_none_keeps_it() -> None:
    existing = {"DF_SERVER_URL": "old", "DF_SERVER_API_KEY": "oldkey"}

    env = build_env(existing, {"DF_SERVER_URL": "new", "DF_SERVER_API_KEY": None}, 3000)

    assert env["DF_SERVER_URL"] == "new"
    assert env["DF_SERVER_API_KEY"] == "oldkey"


def test_build_env_public_url_defaults_from_port() -> None:
    assert build_env({}, PASSED, 4000)["PUBLIC_URL"] == "http://localhost:4000"


def test_build_env_existing_public_url_is_kept_without_explicit_value() -> None:
    env = build_env({"PUBLIC_URL": "https://old.example.com"}, PASSED, 4000)

    assert env["PUBLIC_URL"] == "https://old.example.com"


def test_build_env_existing_default_public_url_follows_changed_port() -> None:
    env = build_env({"PUBLIC_URL": "http://localhost:3000"}, PASSED, 3100)

    assert env["PUBLIC_URL"] == "http://localhost:3100"


def test_build_env_explicit_public_url_replaces_existing() -> None:
    env = build_env({"PUBLIC_URL": "https://old.example.com"}, {"PUBLIC_URL": "https://new.example.com"}, 4000)

    assert env["PUBLIC_URL"] == "https://new.example.com"


def test_build_env_empty_existing_public_url_uses_default() -> None:
    env = build_env({"PUBLIC_URL": ""}, PASSED, 3000)

    assert env["PUBLIC_URL"] == "http://localhost:3000"


def test_build_env_trusted_origins_passed_replaces_and_missing_keeps_existing() -> None:
    existing = {"TRUSTED_ORIGINS": "https://a.example.com"}

    kept = build_env(existing, {"TRUSTED_ORIGINS": None}, 3000)
    replaced = build_env(existing, {"TRUSTED_ORIGINS": "https://b.example.com"}, 3000)

    assert kept["TRUSTED_ORIGINS"] == "https://a.example.com"
    assert replaced["TRUSTED_ORIGINS"] == "https://b.example.com"


def test_build_env_keeps_unrelated_existing_keys() -> None:
    env = build_env({"SMTP_HOST": "smtp.example.com"}, PASSED, 3000)

    assert env["SMTP_HOST"] == "smtp.example.com"


@pytest.mark.parametrize("value", ["a\nAPP_SECRET=b", "a\rb"])
def test_build_env_value_with_line_break_raises(value: str) -> None:
    with pytest.raises(InstallError, match="DF_SERVER_API_KEY"):
        build_env({}, {"DF_SERVER_API_KEY": value}, 3000)


def test_missing_values_lists_absent_required_keys() -> None:
    assert missing_values({"DF_SERVER_URL": "u"}) == [
        "DF_SERVER_API_KEY",
        "DF_SERVER_ORGANIZATION_ID",
        "DF_SERVER_PROJECT_ID",
        "SMALL_MODEL",
    ]


def test_read_existing_env_without_file_returns_empty(tmp_path: Path) -> None:
    assert read_existing_env(tmp_path) == {}


def test_read_existing_env_reads_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("APP_SECRET=abc\n")

    assert read_existing_env(tmp_path) == {"APP_SECRET": "abc"}


def test_read_existing_env_unescapes_compose_dollars(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SMTP_PASSWORD=Pa$$word12!\n")

    assert read_existing_env(tmp_path) == {"SMTP_PASSWORD": "Pa$word12!"}


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_escapes_dollar_in_env_for_compose(mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path) -> None:
    directory = tmp_path / "ws"

    _install(directory, passed={**PASSED, "MCP_AUTH_TOKEN": "Pa$word-1234567890"})

    assert 'MCP_AUTH_TOKEN="Pa$$word-1234567890"' in (directory / ".env").read_text()
    assert read_existing_env(directory)["MCP_AUTH_TOKEN"] == "Pa$word-1234567890"


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_quotes_env_values_for_compose(mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path) -> None:
    directory = tmp_path / "ws"

    _install(directory, passed={**PASSED, "MCP_AUTH_TOKEN": "pa ss #1-1234567890"})

    assert 'MCP_AUTH_TOKEN="pa ss #1-1234567890"' in (directory / ".env").read_text()
    assert read_existing_env(directory)["MCP_AUTH_TOKEN"] == "pa ss #1-1234567890"


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_writes_private_env_and_compose_and_starts(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    directory = tmp_path / "ws"

    _install(directory)

    assert (directory / "compose.yaml").is_file()
    assert stat.S_IMODE((directory / ".env").stat().st_mode) == 0o600
    env_text = (directory / ".env").read_text()
    for expected in ("APP_SECRET=", 'PUBLIC_URL="http://localhost:3000"', 'DF_SERVER_PROJECT_ID="proj"'):
        assert expected in env_text
    assert mock_ensure_network.call_args == mock.call("net")
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=directory, raises=InstallError
    )


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_reinstall_keeps_app_secret_and_tightens_mode(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    directory = tmp_path / "ws"
    _install(directory)
    env_file = directory / ".env"
    first = env_file.read_text()
    env_file.chmod(0o644)

    _install(directory, existing=read_existing_env(directory), passed={}, force=True)

    assert env_file.read_text() == first
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600


@mock.patch("deepfellow.workspace.utils.install.run")
def test_install_missing_values_raises_and_writes_nothing(mock_run: Mock, tmp_path: Path) -> None:
    directory = tmp_path / "ws"

    with pytest.raises(InstallError, match="DF_SERVER_API_KEY"):
        _install(directory, passed={"DF_SERVER_URL": "u"})

    assert not directory.exists()
    assert mock_run.call_count == 0


@mock.patch("deepfellow.workspace.utils.install.ensure_network", side_effect=DockerNetworkError("boom"))
def test_install_network_failure_raises_install_error(mock_ensure_network: Mock, tmp_path: Path) -> None:
    with pytest.raises(InstallError, match="boom"):
        _install(tmp_path / "ws")


@mock.patch("deepfellow.workspace.utils.install.run", side_effect=InstallError(None))
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_compose_up_failure_explains_recovery(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    directory = tmp_path / "ws"

    with pytest.raises(InstallError) as exc_info:
        _install(directory)

    message = str(exc_info.value)
    assert "None" not in message
    assert "see the Docker output above" in message
    assert "--force-install" in message
    assert str(directory) in message


@mock.patch("deepfellow.workspace.utils.install.run", side_effect=InstallError(None))
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_compose_up_failure_uses_the_callers_retry_hint(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    with pytest.raises(InstallError) as exc_info:
        install(tmp_path / "ws", "img:1", 3000, "", "net", {}, PASSED, False, retry_hint="run 'suite install --resume'")

    message = str(exc_info.value)
    assert "run 'suite install --resume'" in message
    assert "--force-install" not in message


@mock.patch("deepfellow.workspace.utils.install.echo")
@mock.patch("deepfellow.workspace.utils.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_over_existing_directory_non_interactive_never_suggests_deleting_it(
    mock_ensure_network: Mock,
    mock_run: Mock,
    mock_interactive: Mock,
    mock_echo: Mock,
    tmp_path: Path,
) -> None:
    mock_echo.confirm.return_value = False

    with pytest.raises(typer.Exit):
        _install(tmp_path)

    hint = mock_echo.info.call_args.args[0]
    assert "--force-install" in hint
    assert "rm -rf" not in hint
    assert mock_run.call_count == 0


@mock.patch("deepfellow.workspace.utils.install.echo")
@mock.patch("deepfellow.workspace.utils.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_over_existing_directory_confirmed_proceeds(
    mock_ensure_network: Mock,
    mock_run: Mock,
    mock_interactive: Mock,
    mock_echo: Mock,
    tmp_path: Path,
) -> None:
    mock_echo.confirm.return_value = True

    _install(tmp_path)

    assert mock_echo.confirm.call_args.kwargs == {"ignore_yes": True}
    assert mock_run.call_count == 1


def test_build_compose_external_mongo_has_no_mongo_service_volume_or_url_override() -> None:
    compose = build_compose("img:1", 3000, "", "net", local_mongo=False)

    app = compose["services"]["workspace"]
    assert "workspace-mongo-db" not in compose["services"]
    assert "workspace-mongo-db" not in app["depends_on"]
    assert not any(item.startswith("MONGO_DB_") for item in app["environment"])
    assert "volumes" not in compose
    assert "REDIS_URL=redis://workspace-redis:6379" in app["environment"]


def test_build_compose_external_redis_has_no_redis_service_or_url_override() -> None:
    compose = build_compose("img:1", 3000, "", "net", local_redis=False)

    app = compose["services"]["workspace"]
    assert "workspace-redis" not in compose["services"]
    assert "workspace-redis" not in app["depends_on"]
    assert not any(item.startswith("REDIS_URL=") for item in app["environment"])
    assert "workspace-mongo-db" in compose["volumes"]


def test_build_compose_all_external_app_has_no_depends_on() -> None:
    compose = build_compose("img:1", 3000, "", "net", local_mongo=False, local_redis=False)

    assert list(compose["services"]) == ["workspace"]
    assert "depends_on" not in compose["services"]["workspace"]


def test_incomplete_groups_complete_or_absent_groups_are_fine() -> None:
    full = {
        "BOOTSTRAP_ADMIN_NAME": "a",
        "BOOTSTRAP_ADMIN_EMAIL": "a@example.com",
        "BOOTSTRAP_ADMIN_PASSWORD": "p",
        "SMTP_HOST": "h",
        "SMTP_USERNAME": "u",
        "SMTP_PASSWORD": "p",
        "EMAIL_FROM_ADDRESS": "a@example.com",
    }

    assert incomplete_groups({}) == []
    assert incomplete_groups(full) == []


def test_incomplete_groups_partial_admin_names_missing_keys() -> None:
    problems = incomplete_groups({"BOOTSTRAP_ADMIN_EMAIL": "a@example.com"})

    assert len(problems) == 1
    assert "BOOTSTRAP_ADMIN_NAME" in problems[0]
    assert "BOOTSTRAP_ADMIN_PASSWORD" in problems[0]


def test_incomplete_groups_sender_name_alone_counts_as_partial_email() -> None:
    problems = incomplete_groups({"EMAIL_FROM_NAME": "Workspace"})

    assert len(problems) == 1
    assert "SMTP_HOST" in problems[0]


def test_incomplete_groups_smtp_port_alone_is_not_email_configuration() -> None:
    assert incomplete_groups({"SMTP_PORT": "465"}) == []


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_partial_smtp_is_rejected_before_writing(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    directory = tmp_path / "ws"

    with pytest.raises(InstallError, match="SMTP_HOST"):
        _install(directory, passed=PASSED | {"SMTP_USERNAME": "u"})

    assert not directory.exists()
    assert mock_run.call_count == 0


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_database_name_without_external_mongo_is_rejected(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    with pytest.raises(InstallError, match="MONGO_DB_NAME"):
        _install(tmp_path / "ws", passed=PASSED | {"MONGO_DB_NAME": "x"})


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_external_mongo_and_redis_urls_go_to_env_and_drop_local_services(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    directory = tmp_path / "ws"
    passed = PASSED | {"MONGO_DB_URL": "mongodb://db:27017/?replicaSet=rs0", "REDIS_URL": "redis://cache:6379"}

    _install(directory, passed=passed)

    env_text = (directory / ".env").read_text()
    assert "MONGO_DB_URL=" in env_text
    assert 'REDIS_URL="redis://cache:6379"' in env_text
    assert "workspace-mongo-db" not in (directory / "compose.yaml").read_text()
    assert "workspace-redis" not in (directory / "compose.yaml").read_text()


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_reset_forgets_keys_of_previous_install(
    mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path
) -> None:
    directory = tmp_path / "ws"
    _install(directory, passed={**PASSED, "REDIS_URL": "redis://r:6379"})
    existing = read_existing_env(directory)

    _install_reset(directory, existing)

    env_text = (directory / ".env").read_text()
    assert "REDIS_URL" not in env_text
    assert 'APP_SECRET="' + existing["APP_SECRET"] + '"' in env_text
    assert "workspace-redis" in (directory / "compose.yaml").read_text()


def _install_reset(directory: Path, existing: dict[str, str]) -> dict[str, str]:
    return install(directory, "img:1", 3000, "", "net", existing, {}, True, reset=("REDIS_URL",))


def test_resolve_stack_settings_uses_defaults_without_existing_or_given() -> None:
    result = resolve_stack_settings({}, None, None, None, None)

    assert result == (DF_WORKSPACE_IMAGE, 3000, "", "deepfellow-infra-net")


def test_resolve_stack_settings_restores_values_from_existing_env() -> None:
    existing = {
        "DF_WORKSPACE_IMAGE": "img:9",
        "DF_WORKSPACE_PORT": "8080",
        "DF_WORKSPACE_BIND_ADDRESS": "127.0.0.1",
        "DF_WORKSPACE_DOCKER_NETWORK": "mynet",
    }

    result = resolve_stack_settings(existing, None, None, None, None)

    assert result == ("img:9", 8080, "127.0.0.1", "mynet")


def test_resolve_stack_settings_given_values_win_and_empty_bind_address_resets() -> None:
    existing = {"DF_WORKSPACE_PORT": "8080", "DF_WORKSPACE_BIND_ADDRESS": "127.0.0.1"}

    result = resolve_stack_settings(existing, "img:2", 9000, "", "other")

    assert result == ("img:2", 9000, "", "other")


@pytest.mark.parametrize(
    "existing",
    [{"DF_WORKSPACE_PORT": "abc"}, {"DF_WORKSPACE_PORT": "0"}, {"DF_WORKSPACE_BIND_ADDRESS": "nope"}],
)
def test_resolve_stack_settings_invalid_stored_value_raises(existing: dict[str, str]) -> None:
    with pytest.raises(InstallError):
        resolve_stack_settings(existing, None, None, None, None)


@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_persists_stack_settings_in_env(mock_ensure_network: Mock, mock_run: Mock, tmp_path: Path) -> None:
    directory = tmp_path / "ws"

    _install(directory)

    stored = read_existing_env(directory)
    assert stored["DF_WORKSPACE_IMAGE"] == "img:1"
    assert stored["DF_WORKSPACE_PORT"] == "3000"
    assert stored["DF_WORKSPACE_BIND_ADDRESS"] == ""
    assert stored["DF_WORKSPACE_DOCKER_NETWORK"] == "net"


def _old_install(directory: Path, volume: bool = True) -> None:
    directory.mkdir()
    (directory / "compose.yaml").write_text(
        "services: {}\n" + ("volumes:\n  workspace-mongo-db: {}\n" if volume else "")
    )


def test_has_unprotected_mongo_true_for_old_volume_without_password(tmp_path: Path) -> None:
    _old_install(tmp_path / "ws")

    assert has_unprotected_mongo(tmp_path / "ws", {"APP_SECRET": "x"}) is True


def test_has_unprotected_mongo_false_when_password_known(tmp_path: Path) -> None:
    _old_install(tmp_path / "ws")

    assert has_unprotected_mongo(tmp_path / "ws", {"DF_WORKSPACE_MONGO_PASSWORD": "p"}) is False


def test_has_unprotected_mongo_false_without_previous_volume_or_compose(tmp_path: Path) -> None:
    _old_install(tmp_path / "ws", volume=False)

    assert has_unprotected_mongo(tmp_path / "ws", {}) is False
    assert has_unprotected_mongo(tmp_path / "none", {}) is False


@mock.patch("deepfellow.workspace.utils.install.time.sleep")
@mock.patch("deepfellow.workspace.utils.install.run")
def test_protect_existing_mongo_retries_until_user_is_created(mock_run: Mock, mock_sleep: Mock, tmp_path: Path) -> None:
    mock_run.side_effect = [None, InstallError("not ready"), None]

    protect_existing_mongo(tmp_path, "secret")

    assert mock_run.call_count == 3
    assert mock_sleep.call_count == 1
    assert "secret" not in str(mock_run.call_args.args)
    assert mock_run.call_args.kwargs["extra_env"] == {"MONGO_PW": "secret"}


@mock.patch("deepfellow.workspace.utils.install.time.sleep")
@mock.patch("deepfellow.workspace.utils.install.run")
def test_protect_existing_mongo_gives_up_with_install_error(mock_run: Mock, mock_sleep: Mock, tmp_path: Path) -> None:
    mock_run.side_effect = [None] + [InstallError("no")] * 30

    with pytest.raises(InstallError, match="Could not add the root user"):
        protect_existing_mongo(tmp_path, "secret")


@mock.patch("deepfellow.workspace.utils.install.protect_existing_mongo")
@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_over_old_unprotected_mongo_adds_root_user_with_new_password(
    mock_ensure_network: Mock, mock_run: Mock, mock_protect: Mock, tmp_path: Path
) -> None:
    directory = tmp_path / "ws"
    _old_install(directory)

    env = _install(directory, existing={"APP_SECRET": "abc"}, force=True)

    assert mock_protect.call_count == 1
    assert mock_protect.call_args == mock.call(directory, env["DF_WORKSPACE_MONGO_PASSWORD"])


@mock.patch("deepfellow.workspace.utils.install.protect_existing_mongo")
@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_fresh_does_not_touch_mongo_users(
    mock_ensure_network: Mock, mock_run: Mock, mock_protect: Mock, tmp_path: Path
) -> None:
    _install(tmp_path / "ws")

    assert mock_protect.call_count == 0


@mock.patch("deepfellow.workspace.utils.install.protect_existing_mongo")
@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_failed_mongo_migration_restores_old_env_so_rerun_migrates_again(
    mock_ensure_network: Mock, mock_run: Mock, mock_protect: Mock, tmp_path: Path
) -> None:
    # Arrange
    directory = tmp_path / "ws"
    _old_install(directory)
    (directory / ".env").write_text("APP_SECRET=abc\n")
    old_env = (directory / ".env").read_text()
    mock_protect.side_effect = InstallError("no")

    # Act
    with pytest.raises(InstallError):
        _install(directory, existing={"APP_SECRET": "abc"}, force=True)

    # Assert
    assert (directory / ".env").read_text() == old_env
    assert has_unprotected_mongo(directory, {}) is True


@mock.patch("deepfellow.workspace.utils.install.protect_existing_mongo")
@mock.patch("deepfellow.workspace.utils.install.run")
@mock.patch("deepfellow.workspace.utils.install.ensure_network")
def test_install_failed_network_before_mongo_migration_restores_old_env(
    mock_ensure_network: Mock, mock_run: Mock, mock_protect: Mock, tmp_path: Path
) -> None:
    # Arrange
    directory = tmp_path / "ws"
    _old_install(directory)
    (directory / ".env").write_text("APP_SECRET=abc\n")
    old_env = (directory / ".env").read_text()
    mock_ensure_network.side_effect = DockerNetworkError("no network")

    # Act
    with pytest.raises(InstallError):
        _install(directory, existing={"APP_SECRET": "abc"}, force=True)

    # Assert
    assert mock_protect.call_count == 0
    assert (directory / ".env").read_text() == old_env


def test_write_stack_round_trips_dollar_hash_and_quotes(tmp_path: Path):
    env = {**STACK_ENV, "SMTP_PASSWORD": 'a$b #c "d"'}

    write_stack(tmp_path, env)

    assert read_existing_env(tmp_path)["SMTP_PASSWORD"] == 'a$b #c "d"'


def test_write_stack_compose_has_local_services_when_urls_empty(tmp_path: Path):
    env = {**STACK_ENV, "MONGO_DB_URL": "", "REDIS_URL": ""}

    write_stack(tmp_path, env)

    services = load_compose_file(tmp_path / "compose.yaml")["services"]
    assert WORKSPACE_MONGO_SERVICE in services
    assert WORKSPACE_REDIS_SERVICE in services


def test_write_stack_compose_drops_mongo_for_external_url(tmp_path: Path):
    env = {**STACK_ENV, "MONGO_DB_URL": "mongodb://db:27017/?replicaSet=rs0"}

    write_stack(tmp_path, env)

    compose = load_compose_file(tmp_path / "compose.yaml")
    assert WORKSPACE_MONGO_SERVICE not in compose["services"]
    assert "volumes" not in compose


def test_write_stack_compose_uses_env_image_and_port(tmp_path: Path):
    write_stack(tmp_path, STACK_ENV)

    app = load_compose_file(tmp_path / "compose.yaml")["services"]["workspace"]
    assert app["image"] == "img:2"
    assert app["ports"] == ["127.0.0.1:3001:3000"]
    assert app["networks"] == ["default", "net"]


def test_write_stack_applies_given_service_images(tmp_path: Path):
    images = {WORKSPACE_MONGO_SERVICE: "mongo:old", WORKSPACE_REDIS_SERVICE: "redis:old"}

    write_stack(tmp_path, STACK_ENV, images=images)

    assert current_service_images(tmp_path) == images


def test_write_stack_without_images_uses_cli_images(tmp_path: Path):
    write_stack(tmp_path, STACK_ENV)

    assert current_service_images(tmp_path) == {
        WORKSPACE_MONGO_SERVICE: MONGO_IMAGE,
        WORKSPACE_REDIS_SERVICE: WORKSPACE_REDIS_IMAGE,
    }


def test_current_service_images_skips_missing_services(tmp_path: Path):
    write_stack(tmp_path, {**STACK_ENV, "REDIS_URL": "redis://cache:6379"})

    result = current_service_images(tmp_path)

    assert result == {WORKSPACE_MONGO_SERVICE: MONGO_IMAGE}


def test_current_service_images_without_compose_returns_empty(tmp_path: Path):
    result = current_service_images(tmp_path)

    assert result == {}


def test_apply_service_images_ignores_service_not_in_compose():
    compose = build_compose("img:1", 3000, "", "net", local_redis=False)

    apply_service_images(compose, {WORKSPACE_REDIS_SERVICE: "redis:old", WORKSPACE_MONGO_SERVICE: "mongo:old"})

    assert WORKSPACE_REDIS_SERVICE not in compose["services"]
    assert compose["services"][WORKSPACE_MONGO_SERVICE]["image"] == "mongo:old"


def test_validate_env_raises_on_missing_required():
    env = {key: value for key, value in STACK_ENV.items() if key != "SMALL_MODEL"}

    with pytest.raises(InstallError, match="SMALL_MODEL"):
        validate_env(env)


def test_validate_env_treats_empty_required_value_as_missing():
    env = {**STACK_ENV, "DF_SERVER_URL": ""}

    with pytest.raises(InstallError, match="DF_SERVER_URL"):
        validate_env(env)


def test_validate_env_returns_incomplete_smtp_group():
    env = {**STACK_ENV, "SMTP_HOST": "smtp.example.com"}

    result = validate_env(env)

    assert len(result) == 1
    assert "SMTP_USERNAME" in result[0]


@mock.patch("deepfellow.workspace.utils.install.echo")
def test_read_installed_env_returns_settings(mock_echo: Mock, tmp_path: Path):
    write_stack(tmp_path, STACK_ENV)

    result = read_installed_env(tmp_path)

    assert result["SMALL_MODEL"] == "small"


@mock.patch("deepfellow.workspace.utils.install.echo")
def test_read_installed_env_without_file_exits(mock_echo: Mock, tmp_path: Path):
    with pytest.raises(typer.Exit) as exc_info:
        read_installed_env(tmp_path)

    assert exc_info.value.exit_code == 1
    assert "workspace install" in str(mock_echo.error.call_args.args[0])


@mock.patch("deepfellow.workspace.utils.install.read_env_file", side_effect=PermissionError("denied"))
@mock.patch("deepfellow.workspace.utils.install.echo")
def test_read_installed_env_unreadable_file_exits(mock_echo: Mock, mock_read_env_file: Mock, tmp_path: Path):
    (tmp_path / ".env").write_text("A=1\n")

    with pytest.raises(typer.Exit) as exc_info:
        read_installed_env(tmp_path)

    assert exc_info.value.exit_code == 1
    assert "Cannot read" in str(mock_echo.error.call_args.args[0])


@pytest.mark.parametrize("content", ["", "services: [a, b]\n", "- just a list\n"])
def test_current_service_images_ignores_compose_without_services_mapping(content: str, tmp_path: Path):
    (tmp_path / "compose.yaml").write_text(content)

    result = current_service_images(tmp_path)

    assert result == {}


def test_current_service_images_invalid_yaml_raises(tmp_path: Path):
    (tmp_path / "compose.yaml").write_text("services: [unclosed")

    with pytest.raises(InstallError, match="Cannot read"):
        current_service_images(tmp_path)


@mock.patch("deepfellow.workspace.utils.install.save_compose_file", side_effect=OSError("disk full"))
def test_write_stack_write_failure_raises_install_error(mock_save_compose_file: Mock, tmp_path: Path):
    with pytest.raises(InstallError, match="disk full"):
        write_stack(tmp_path, STACK_ENV)
