# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from typer.testing import CliRunner

from deepfellow.common.exceptions import DockerNetworkError
from deepfellow.common.state import state
from deepfellow.main import app
from deepfellow.update import UpdateStepsError, _run_step, _uses_local_image, update


def test_run_step_returns_true_when_step_succeeds() -> None:
    step = Mock()

    result = _run_step(step)

    assert result is True
    assert step.call_count == 1


def test_run_step_returns_false_when_step_raises_typer_exit() -> None:
    step = Mock(side_effect=typer.Exit(1))

    result = _run_step(step)

    assert result is False


@mock.patch.object(state, "debug", True)
def test_run_step_returns_false_when_step_raises_in_debug_mode() -> None:
    step = Mock(side_effect=DockerNetworkError("network gone"))

    result = _run_step(step)

    assert result is False


@mock.patch("deepfellow.update.load_compose_file")
def test_uses_local_image_returns_true_when_pull_policy_never(mock_load_compose_file: Mock) -> None:
    mock_load_compose_file.return_value = {"services": {"infra": {"pull_policy": "never"}}}

    result = _uses_local_image(Path("/some/dir"), "infra")

    assert result is True


@mock.patch("deepfellow.update.load_compose_file")
def test_uses_local_image_returns_false_when_pull_policy_absent(mock_load_compose_file: Mock) -> None:
    mock_load_compose_file.return_value = {"services": {"infra": {}}}

    result = _uses_local_image(Path("/some/dir"), "infra")

    assert result is False


@mock.patch("deepfellow.update.run")
@mock.patch("deepfellow.update.shutil.which", return_value="/usr/bin/deepfellow")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli")
def test_update_reexecs_remaining_steps_after_cli_update(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_which: Mock,
    mock_run: Mock,
) -> None:
    update(skip_cli=False)

    assert mock_update_cli.call_count == 1
    assert mock_which.call_args == mock.call("deepfellow")
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        [
            "/usr/bin/deepfellow",
            "--config",
            str(state.cli_config_file),
            "--secrets",
            str(state.cli_secrets_file),
            "update",
            "--skip-cli",
        ],
        raises=UpdateStepsError,
    )
    assert mock_update_infra.call_count == 0
    assert mock_update_server.call_count == 0


@pytest.mark.parametrize(
    ("attribute", "flag"),
    [
        ("debug", "--debug"),
        ("yes", "--yes"),
        ("non_interactive", "--non-interactive"),
    ],
)
@mock.patch("deepfellow.update.run")
@mock.patch("deepfellow.update.shutil.which", return_value="/usr/bin/deepfellow")
@mock.patch("deepfellow.update.update_cli")
def test_update_forwards_global_flags_to_new_process(
    mock_update_cli: Mock,
    mock_which: Mock,
    mock_run: Mock,
    attribute: str,
    flag: str,
) -> None:
    setattr(state, attribute, True)

    update(skip_cli=False)

    command = mock_run.call_args.args[0]
    assert flag in command
    assert command.index(flag) < command.index("update")
    assert {"--debug", "--yes", "--non-interactive"} & set(command) == {flag}


@mock.patch("deepfellow.update.run")
@mock.patch("deepfellow.update.shutil.which", return_value="/usr/bin/deepfellow")
@mock.patch("deepfellow.update.update_cli")
def test_update_forwards_config_and_secrets_paths_to_new_process(
    mock_update_cli: Mock,
    mock_which: Mock,
    mock_run: Mock,
    tmp_path: Path,
) -> None:
    state.cli_config_file = tmp_path / "custom-config"
    state.cli_secrets_file = tmp_path / "custom-secrets"

    update(skip_cli=False)

    command = mock_run.call_args.args[0]
    assert command[1:5] == ["--config", str(tmp_path / "custom-config"), "--secrets", str(tmp_path / "custom-secrets")]


@mock.patch("deepfellow.update.run")
@mock.patch("deepfellow.update.shutil.which")
@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli")
def test_update_skip_cli_runs_steps_in_process(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
    mock_which: Mock,
    mock_run: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    server_dir = mock_get_server_dir.return_value
    server_dir.is_dir.return_value = True
    mock_load_compose_file.return_value = {"services": {}}

    update(skip_cli=True)

    assert mock_update_cli.call_count == 0
    assert mock_which.call_count == 0
    assert mock_run.call_count == 0
    assert mock_update_infra.call_count == 1
    assert mock_update_infra.call_args == mock.call(
        directory=mock_infra_dir, image=mock.ANY, local_image=False, tag=None
    )
    assert mock_update_server.call_count == 1
    assert mock_update_server.call_args == mock.call(
        directory=server_dir,
        image=mock.ANY,
        local_image=False,
        tag=None,
        nightshift=None,
        rabbitmq_url=None,
        rabbitmq_username="",
        rabbitmq_password="",
    )


@pytest.mark.parametrize(
    ("non_interactive", "yes", "expected_nightshift"),
    [(True, False, False), (True, True, None), (False, False, None), (False, True, None)],
)
@mock.patch("deepfellow.update.load_compose_file", return_value={"services": {}})
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
def test_update_skip_cli_skips_nightshift_only_when_unattended(
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
    non_interactive: bool,
    yes: bool,
    expected_nightshift: bool | None,
) -> None:
    mock_infra_dir.is_dir.return_value = False
    mock_get_server_dir.return_value.is_dir.return_value = True
    state.non_interactive = non_interactive
    state.yes = yes

    update(skip_cli=True)

    assert mock_update_server.call_count == 1
    assert mock_update_server.call_args.kwargs["nightshift"] is expected_nightshift


@mock.patch("deepfellow.update.run")
@mock.patch("deepfellow.update.shutil.which")
@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli", side_effect=typer.Exit(1))
def test_update_falls_back_to_in_process_when_cli_update_fails(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
    mock_which: Mock,
    mock_run: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True
    mock_load_compose_file.return_value = {"services": {}}

    with pytest.raises(typer.Exit) as exc_info:
        update(skip_cli=False)

    assert exc_info.value.exit_code == 1
    assert mock_which.call_count == 0
    assert mock_run.call_count == 0
    assert mock_update_infra.call_count == 1
    assert mock_update_server.call_count == 1


@mock.patch("deepfellow.update.echo")
@mock.patch("deepfellow.update.run")
@mock.patch("deepfellow.update.shutil.which", return_value=None)
@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli")
def test_update_falls_back_to_in_process_when_executable_not_found(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
    mock_which: Mock,
    mock_run: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True
    mock_load_compose_file.return_value = {"services": {}}

    update(skip_cli=False)

    assert mock_update_cli.call_count == 1
    assert mock_run.call_count == 0
    assert mock_update_infra.call_count == 1
    assert mock_update_server.call_count == 1
    assert mock_echo.warning.call_count == 1
    assert "isn't on PATH" in mock_echo.warning.call_args.args[0]


def test_update_skip_cli_hidden_from_help() -> None:
    result = CliRunner().invoke(app, ["update", "--help"])

    assert result.exit_code == 0
    assert "--skip-cli" not in result.output


def _start_failure() -> UpdateStepsError:
    """Build the error `run()` raises when the process can't be started (the OSError is chained)."""
    exc = UpdateStepsError("[Errno 13] Permission denied")
    exc.__cause__ = PermissionError(13, "Permission denied")
    return exc


@mock.patch("deepfellow.update.echo")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.run", side_effect=UpdateStepsError(None))
@mock.patch("deepfellow.update.shutil.which", return_value="/usr/bin/deepfellow")
@mock.patch("deepfellow.update.update_cli")
def test_update_exits_1_when_new_process_fails(
    mock_update_cli: Mock,
    mock_which: Mock,
    mock_run: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_echo: Mock,
) -> None:
    with pytest.raises(typer.Exit) as exc_info:
        update(skip_cli=False)

    assert exc_info.value.exit_code == 1
    assert mock_run.call_count == 1
    assert mock_update_infra.call_count == 0
    assert mock_update_server.call_count == 0
    assert mock_echo.error.call_count == 1
    message = mock_echo.error.call_args.args[0]
    assert "/usr/bin/deepfellow" in message
    assert "`deepfellow update --skip-cli`" in message


@mock.patch("deepfellow.update.echo")
@mock.patch("deepfellow.update.load_compose_file", return_value={"services": {}})
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.run", side_effect=_start_failure())
@mock.patch("deepfellow.update.shutil.which", return_value="/usr/bin/deepfellow")
@mock.patch("deepfellow.update.update_cli")
def test_update_falls_back_to_in_process_when_new_process_cant_start(
    mock_update_cli: Mock,
    mock_which: Mock,
    mock_run: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True

    update(skip_cli=False)

    assert mock_run.call_count == 1
    assert mock_update_infra.call_count == 1
    assert mock_update_server.call_count == 1
    assert mock_echo.error.call_count == 0
    assert mock_echo.warning.call_count == 1
    message = mock_echo.warning.call_args.args[0]
    assert "/usr/bin/deepfellow" in message
    assert "Permission denied" in message


@mock.patch("deepfellow.update.echo")
@mock.patch("deepfellow.update.load_compose_file", return_value={"services": {}})
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra", side_effect=typer.Exit(1))
@mock.patch("deepfellow.update.run", side_effect=_start_failure())
@mock.patch("deepfellow.update.shutil.which", return_value="/usr/bin/deepfellow")
@mock.patch("deepfellow.update.update_cli")
def test_update_exits_1_when_in_process_fallback_step_fails(
    mock_update_cli: Mock,
    mock_which: Mock,
    mock_run: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True

    with pytest.raises(typer.Exit) as exc_info:
        update(skip_cli=False)

    assert exc_info.value.exit_code == 1
    assert mock_update_server.call_count == 1


@mock.patch("deepfellow.update.echo")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
def test_update_skips_missing_infra_and_server(
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = False
    mock_get_server_dir.return_value.is_dir.return_value = False

    update(skip_cli=True)

    assert mock_update_infra.call_count == 0
    assert mock_update_server.call_count == 0
    assert mock_echo.info.call_count == 2


@mock.patch("deepfellow.update.echo")
@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
def test_update_skips_infra_and_server_pinned_to_local_image(
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True
    mock_load_compose_file.return_value = {
        "services": {"infra": {"pull_policy": "never"}, "server": {"pull_policy": "never"}}
    }

    update(skip_cli=True)

    assert mock_update_infra.call_count == 0
    assert mock_update_server.call_count == 0
    assert mock_echo.info.call_count == 2


@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra", side_effect=typer.Exit(1))
def test_update_skip_cli_exits_1_when_a_step_fails(
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True
    mock_load_compose_file.return_value = {"services": {}}

    with pytest.raises(typer.Exit) as exc_info:
        update(skip_cli=True)

    assert exc_info.value.exit_code == 1
    assert mock_update_server.call_count == 1
