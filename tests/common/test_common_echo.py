# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the echo module."""

from unittest import mock
from unittest.mock import MagicMock, Mock, patch

import pytest
import typer

from deepfellow.common.echo import Echo, echo, get_return_value, is_interactive
from deepfellow.common.state import state

_IS_INTERACTIVE = "deepfellow.common.echo.is_interactive"


@pytest.fixture
def prompter():
    """Create instance of class containing prompt method."""
    return Echo()  # Replace with actual class name


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_with_explicit_cli_value(mock_interactive, prompter):
    """When from_args differs from original_default, return from_args."""
    result = prompter.prompt(
        message="Enter value",
        from_args="cli_value",
        original_default="original",
        default="config_default",
    )
    assert result == "cli_value"


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_from_args_none_uses_default(mock_interactive, prompter):
    """When from_args is None, return default."""
    result = prompter.prompt(
        message="Enter value",
        from_args=None,
        original_default="original",
        default="config_default",
    )
    assert result == "config_default"


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_from_args_equals_original_uses_default(mock_interactive, prompter):
    """When from_args equals original_default, return default."""
    result = prompter.prompt(
        message="Enter value",
        from_args="same_value",
        original_default="same_value",
        default="config_default",
    )
    assert result == "config_default"


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_no_value_no_default_exits(mock_interactive, prompter):
    """When no CLI value and no default, raise Exit."""
    with pytest.raises(typer.Exit) as exc_info:
        prompter.prompt(
            message="Enter value",
            from_args=None,
            original_default=None,
            default=None,
        )
    assert exc_info.value.exit_code == 1


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_from_args_equals_original_no_default_exits(mock_interactive, prompter):
    """When from_args equals original_default and no default, raise Exit."""
    with pytest.raises(typer.Exit) as exc_info:
        prompter.prompt(
            message="Enter value",
            from_args="same",
            original_default="same",
            default=None,
        )
    assert exc_info.value.exit_code == 1


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_explicit_cli_value_skips_validation(mock_interactive, prompter):
    """Validation is NOT applied to explicit CLI values (already validated)."""
    validation = MagicMock(return_value="validated_value")

    result = prompter.prompt(
        message="Enter value",
        validation=validation,
        from_args="cli_value",
        original_default="original",
    )

    validation.assert_not_called()
    assert result == "cli_value"


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_default_skips_validation(mock_interactive, prompter):
    """Validation is NOT applied to default values (already validated)."""
    validation = MagicMock(return_value="validated_value")

    result = prompter.prompt(
        message="Enter value",
        validation=validation,
        from_args=None,
        original_default=None,
        default="config_default",
    )

    validation.assert_not_called()
    assert result == "config_default"


@patch("deepfellow.common.echo.Prompt.ask", return_value="user_input")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_interactive_user_input_gets_validated(mock_interactive, mock_ask, prompter):
    """Validation IS applied to user input from Prompt.ask()."""
    validation = MagicMock(return_value="validated_input")

    result = prompter.prompt(
        message="Enter value",
        validation=validation,
        from_args=None,
        original_default=None,
        default="default_val",
    )

    validation.assert_called_once_with("user_input")
    assert result == "validated_input"


@patch("deepfellow.common.echo.Prompt.ask")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_interactive_explicit_cli_value_skips_validation(mock_interactive, mock_ask, prompter):
    """Even in interactive mode, explicit CLI values skip validation."""
    validation = MagicMock(return_value="validated_value")

    result = prompter.prompt(
        message="Enter value",
        validation=validation,
        from_args="explicit_value",
        original_default="original",
        default="default_val",
    )

    mock_ask.assert_not_called()
    validation.assert_not_called()
    assert result == "explicit_value"


@patch("deepfellow.common.echo.Prompt.ask", return_value="user_input")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_interactive_from_args_none_prompts_user(mock_interactive, mock_ask, prompter):
    """When from_args is None in interactive mode, prompt user."""
    result = prompter.prompt(
        message="Enter value",
        from_args=None,
        original_default=None,
        default="default_val",
    )

    mock_ask.assert_called_once()
    assert result == "user_input"


@patch("deepfellow.common.echo.Prompt.ask", return_value="user_input")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_interactive_from_args_equals_original_prompts_user(mock_interactive, mock_ask, prompter):
    """When from_args equals original_default, prompt user."""
    result = prompter.prompt(
        message="Enter value",
        from_args="same",
        original_default="same",
        default="default_val",
    )

    mock_ask.assert_called_once()
    assert result == "user_input"


@patch("deepfellow.common.echo.Prompt.ask")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_interactive_explicit_cli_value_skips_prompt(mock_interactive, mock_ask, prompter):
    """When from_args differs from original_default, don't prompt."""
    result = prompter.prompt(
        message="Enter value",
        from_args="explicit_value",
        original_default="original",
        default="default_val",
    )

    mock_ask.assert_not_called()
    assert result == "explicit_value"


@patch("deepfellow.common.echo.Prompt.ask", return_value="user_input")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_interactive_with_validation(mock_interactive, mock_ask, prompter):
    """Validation callback is applied to user input."""
    validation = MagicMock(return_value="validated_input")

    result = prompter.prompt(
        message="Enter value",
        validation=validation,
        from_args=None,
        original_default=None,
        default="default_val",
    )

    validation.assert_called_once_with("user_input")
    assert result == "validated_input"


@patch("deepfellow.common.echo.Prompt.ask", return_value="secret")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_password_mode_masks_default(mock_interactive, mock_ask, prompter):
    """Password mode masks the default value in the prompt message."""
    prompter.prompt(
        message="Enter password",
        from_args=None,
        original_default=None,
        default="mysecretpassword",
        password=True,
    )

    call_kwargs = mock_ask.call_args.kwargs
    # Default should be masked as "my***rd" in prompt message
    assert "my***rd" in mock_ask.call_args.kwargs.get("prompt", "") or call_kwargs.get("password") is True
    assert call_kwargs.get("show_default") is False


@patch("deepfellow.common.echo.Prompt.ask", return_value="secret")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_password_mode_without_default(mock_interactive, mock_ask, prompter):
    """Password mode without default doesn't modify message."""
    prompter.prompt(
        message="Enter password",
        from_args=None,
        original_default=None,
        default=None,
        password=True,
    )

    call_kwargs = mock_ask.call_args.kwargs
    assert call_kwargs.get("password") is True
    assert call_kwargs.get("show_default") is True


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_from_args_empty_string_is_user_provided(mock_interactive, prompter):
    """Empty string from_args is treated as user-provided value."""
    result = prompter.prompt(
        message="Enter value",
        from_args="",
        original_default=None,
        default="default_val",
    )
    assert result == ""


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_from_args_empty_string_equals_original_uses_default(mock_interactive, prompter):
    """Empty string from_args equals original_default uses default."""
    result = prompter.prompt(
        message="Enter value",
        from_args="",
        original_default="",
        default="default_val",
    )
    assert result == "default_val"


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_both_from_args_and_original_default_none(mock_interactive, prompter):
    """When both are None, from_args is not considered user-provided."""
    result = prompter.prompt(
        message="Enter value",
        from_args=None,
        original_default=None,
        default="default_val",
    )
    assert result == "default_val"


@patch("deepfellow.common.echo.Prompt.ask", return_value="")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_user_enters_empty_string(mock_interactive, mock_ask, prompter):
    """User entering empty string in interactive mode."""
    result = prompter.prompt(
        message="Enter value",
        from_args=None,
        original_default=None,
        default="default_val",
    )
    assert result == ""


@patch("deepfellow.common.echo.Prompt.ask", return_value="choice1")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_kwargs_passed_to_prompt_ask(mock_interactive, mock_ask, prompter):
    """Additional kwargs are passed to Prompt.ask."""
    prompter.prompt(
        message="Choose option",
        from_args=None,
        original_default=None,
        default="choice1",
        choices=["choice1", "choice2", "choice3"],
    )

    call_kwargs = mock_ask.call_args.kwargs
    assert call_kwargs.get("choices") == ["choice1", "choice2", "choice3"]


@mock.patch(_IS_INTERACTIVE)
@mock.patch("deepfellow.common.echo.questionary")
def test_choice_interactive(mock_questionary: Mock, mock_is_interactive: Mock) -> None:
    """Test choice method in interactive mode."""
    mock_is_interactive.return_value = True
    mock_questionary.select.return_value.ask.return_value = "option1"

    result = echo.choice("Select option", choices=["option1", "option2"])

    assert result == "option1"
    mock_questionary.select.assert_called_once()


@mock.patch(_IS_INTERACTIVE)
def test_choice_not_interactive_no_default(mock_is_interactive: Mock) -> None:
    """Test choice method in non-interactive mode without default value."""
    mock_is_interactive.return_value = False

    with pytest.raises(typer.Exit):
        echo.choice("Select option", choices=["option1", "option2"])

    # Check that error was called


@mock.patch(_IS_INTERACTIVE)
def test_choice_not_interactive_with_default(mock_is_interactive: Mock) -> None:
    """Test choice method in non-interactive mode with default value."""
    mock_is_interactive.return_value = False

    result = echo.choice("Select option", choices=["option1", "option2"], default="option2")

    assert result == "option2"


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_interactive_no_args_returns_none(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value") is None


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_interactive_from_args_provided(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args="custom", original_default="default") == "custom"


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_interactive_from_args_equals_original_default_returns_none(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args="default", original_default="default") is None


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_interactive_from_args_none_returns_none(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args=None, original_default="default") is None


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_interactive_default_ignored_when_no_args(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", default="fallback") is None


@patch(_IS_INTERACTIVE, return_value=False)
def test_get_return_value_non_interactive_from_args_provided(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args="custom", original_default="default") == "custom"


@patch(_IS_INTERACTIVE, return_value=False)
def test_get_return_value_non_interactive_falls_back_to_default(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", default="fallback") == "fallback"


@patch(_IS_INTERACTIVE, return_value=False)
def test_get_return_value_non_interactive_no_args_no_default_exits(mock_is_interactive: mock.Mock):
    with pytest.raises(typer.Exit):
        get_return_value("Enter value")


@patch(_IS_INTERACTIVE, return_value=False)
def test_get_return_value_non_interactive_from_args_equals_original_default_uses_default(
    mock_is_interactive: mock.Mock,
):
    assert get_return_value("Enter value", default="fallback", from_args="orig", original_default="orig") == "fallback"


@patch(_IS_INTERACTIVE, return_value=False)
def test_get_return_value_non_interactive_from_args_equals_original_default_no_default_exits(
    mock_is_interactive: mock.Mock,
):
    with pytest.raises(typer.Exit):
        get_return_value("Enter value", from_args="orig", original_default="orig")


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_from_args_false_is_valid_value(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args=False, original_default=True) is False


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_from_args_empty_string_is_valid_value(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args="", original_default="default") == ""


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_from_args_zero_is_valid_value(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args=0, original_default=1) == 0


def test_is_interactive_returns_true_when_non_interactive_false():
    state.non_interactive = False

    assert is_interactive() is True


def test_is_interactive_returns_false_when_non_interactive_true():
    state.non_interactive = True

    assert is_interactive() is False
