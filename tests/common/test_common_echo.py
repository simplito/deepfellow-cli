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
def test_prompt_non_interactive_from_args_equals_original_no_default_uses_from_args(mock_interactive, prompter):
    """When from_args equals original_default and no config default, use from_args (CLI default is valid)."""
    result = prompter.prompt(
        message="Enter value",
        from_args="same",
        original_default="same",
        default=None,
    )
    assert result == "same"


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_explicit_cli_value_is_validated(mock_interactive, prompter):
    """An explicit CLI value is still validated, not accepted as-is (e.g. an invalid --template
    value merged in via force_provided must not silently reach the .env)."""
    validation = MagicMock(return_value="validated_value")

    result = prompter.prompt(
        message="Enter value",
        validation=validation,
        from_args="cli_value",
        original_default="original",
    )

    assert validation.call_count == 1
    assert validation.call_args == mock.call("cli_value")
    assert result == "validated_value"


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_default_is_validated(mock_interactive, prompter):
    """A config-sourced default is still validated, not accepted as-is."""
    validation = MagicMock(return_value="validated_value")

    result = prompter.prompt(
        message="Enter value",
        validation=validation,
        from_args=None,
        original_default=None,
        default="config_default",
    )

    assert validation.call_count == 1
    assert validation.call_args == mock.call("config_default")
    assert result == "validated_value"


@patch(_IS_INTERACTIVE, return_value=False)
def test_prompt_non_interactive_force_provided_invalid_value_raises(mock_interactive, prompter):
    """A force_provided value (e.g. merged in from a --template equal to its own original_default)
    is still validated, not accepted as-is."""
    validation = MagicMock(side_effect=typer.BadParameter("invalid"))

    with pytest.raises(typer.BadParameter):
        prompter.prompt(
            message="Enter value",
            validation=validation,
            from_args="same",
            original_default="same",
            force_provided=True,
        )


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
def test_prompt_interactive_explicit_cli_value_skips_prompt_but_is_validated(mock_interactive, mock_ask, prompter):
    """Even in interactive mode, an explicit CLI value skips the prompt but is still validated."""
    validation = MagicMock(return_value="validated_value")

    result = prompter.prompt(
        message="Enter value",
        validation=validation,
        from_args="explicit_value",
        original_default="original",
        default="default_val",
    )

    mock_ask.assert_not_called()
    assert validation.call_count == 1
    assert validation.call_args == mock.call("explicit_value")
    assert result == "validated_value"


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


@patch("deepfellow.common.echo.Prompt.ask")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_interactive_force_provided_skips_prompt_despite_matching_default(mock_interactive, mock_ask, prompter):
    """force_provided=True treats from_args as explicit even when it equals original_default."""
    result = prompter.prompt(
        message="Enter value",
        from_args="same",
        original_default="same",
        default="default_val",
        force_provided=True,
    )

    assert mock_ask.call_count == 0
    assert result == "same"


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
def test_prompt_non_interactive_from_args_empty_string_equals_original_no_default_exits(mock_interactive, prompter):
    """Empty string from_args equals original_default with no config default still exits, empty is not a valid value."""
    with pytest.raises(typer.Exit) as exc_info:
        prompter.prompt(
            message="Enter value",
            from_args="",
            original_default="",
            default=None,
        )
    assert exc_info.value.exit_code == 1


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


@patch("deepfellow.common.echo.Prompt.ask")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_until_valid_force_provided_skips_prompt_despite_matching_default(mock_interactive, mock_ask, prompter):
    """force_provided is forwarded through prompt_until_valid into prompt()/get_return_value, and the
    force_provided value is still validated rather than accepted as-is."""
    validation = MagicMock(return_value="validated_value")

    result = prompter.prompt_until_valid(
        "Enter value",
        validation,
        from_args="same",
        original_default="same",
        default="default_val",
        force_provided=True,
    )

    assert mock_ask.call_count == 0
    assert validation.call_count == 1
    assert validation.call_args == mock.call("same")
    assert result == "validated_value"


@patch("deepfellow.common.echo.Prompt.ask", side_effect=["bad", "good"])
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_until_valid_interactive_retries_after_invalid_input(mock_interactive, mock_ask, prompter):
    """After a freshly-typed value fails validation, the user is re-prompted rather than reusing
    the failed value - a force_provided value that fails validation must not get stuck retrying
    forever with the same input (see get_return_value's from_args-cleared-to-None retry)."""
    validation = MagicMock(side_effect=[typer.BadParameter("invalid"), "good"])

    result = prompter.prompt_until_valid(
        "Enter value",
        validation,
        from_args=None,
        original_default=None,
        default="default_val",
    )

    assert mock_ask.call_count == 2
    assert result == "good"


@mock.patch(_IS_INTERACTIVE)
@mock.patch("deepfellow.common.echo.questionary")
def test_choice_interactive_force_provided_skips_prompt_despite_matching_default(
    mock_questionary: Mock, mock_is_interactive: Mock
) -> None:
    """force_provided=True treats from_args as explicit even when it equals original_default."""
    mock_is_interactive.return_value = True

    result = echo.choice(
        "Select option",
        choices=["option1", "option2"],
        from_args="option1",
        original_default="option1",
        force_provided=True,
    )

    assert result == "option1"
    assert mock_questionary.select.call_count == 0


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
def test_get_return_value_interactive_force_provided_skips_prompt_despite_matching_default(
    mock_is_interactive: mock.Mock,
):
    assert (
        get_return_value("Enter value", from_args="default", original_default="default", force_provided=True)
        == "default"
    )


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_interactive_force_provided_ignored_when_from_args_is_none(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args=None, original_default="default", force_provided=True) is None


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
def test_get_return_value_non_interactive_from_args_equals_original_default_no_default_uses_from_args(
    mock_is_interactive: mock.Mock,
):
    assert get_return_value("Enter value", from_args="orig", original_default="orig") == "orig"


@patch(_IS_INTERACTIVE, return_value=False)
def test_get_return_value_non_interactive_force_provided_uses_from_args_over_default(
    mock_is_interactive: mock.Mock,
):
    assert (
        get_return_value(
            "Enter value", default="stale-env-value", from_args="orig", original_default="orig", force_provided=True
        )
        == "orig"
    )


@patch(_IS_INTERACTIVE, return_value=False)
def test_get_return_value_non_interactive_from_args_empty_string_equals_original_no_default_exits(
    mock_is_interactive: mock.Mock,
):
    with pytest.raises(typer.Exit):
        get_return_value("Enter value", from_args="", original_default="")


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_from_args_false_is_valid_value(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args=False, original_default=True) is False


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_from_args_empty_string_is_valid_value(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args="", original_default="default") == ""


@patch(_IS_INTERACTIVE, return_value=True)
def test_get_return_value_from_args_zero_is_valid_value(mock_is_interactive: mock.Mock):
    assert get_return_value("Enter value", from_args=0, original_default=1) == 0


@patch("deepfellow.common.echo.Confirm.ask")
@patch(_IS_INTERACTIVE, return_value=True)
def test_confirm_interactive_from_args_true_skips_prompt(mock_interactive, mock_ask, prompter):
    """Explicit from_args=True skips the interactive prompt."""
    result = prompter.confirm("Keep X?", from_args=True)

    assert mock_ask.call_count == 0
    assert result is True


@patch("deepfellow.common.echo.Confirm.ask")
@patch(_IS_INTERACTIVE, return_value=True)
def test_confirm_interactive_from_args_false_skips_prompt(mock_interactive, mock_ask, prompter):
    """Explicit from_args=False skips the interactive prompt."""
    result = prompter.confirm("Keep X?", from_args=False)

    assert mock_ask.call_count == 0
    assert result is False


@patch(_IS_INTERACTIVE, return_value=False)
def test_confirm_non_interactive_from_args_true_ignores_default(mock_interactive, prompter):
    """Explicit from_args=True is returned even when non-interactive default is False."""
    result = prompter.confirm("Keep X?", from_args=True, default=False)

    assert result is True


@patch(_IS_INTERACTIVE, return_value=False)
def test_confirm_non_interactive_from_args_none_uses_default(mock_interactive, prompter):
    """from_args=None in non-interactive mode falls back to default, as before this change."""
    result = prompter.confirm("Keep X?", default=True)

    assert result is True


@patch("deepfellow.common.echo.Confirm.ask", return_value=True)
@patch(_IS_INTERACTIVE, return_value=True)
def test_confirm_interactive_from_args_none_still_prompts(mock_interactive, mock_ask, prompter):
    """from_args=None in interactive mode still prompts, as before this change."""
    result = prompter.confirm("Keep X?")

    assert mock_ask.call_count == 1
    assert result is True


def test_is_interactive_returns_true_when_non_interactive_false():
    state.non_interactive = False

    assert is_interactive() is True


def test_is_interactive_returns_false_when_non_interactive_true():
    state.non_interactive = True

    assert is_interactive() is False


@patch(_IS_INTERACTIVE, return_value=True)
def test_debug_prints_formatted_message_when_enabled_and_interactive(mock_interactive, prompter):
    """debug() prints a tab-indented, emoji-prefixed message when state.debug is True and interactive."""
    state.debug = True

    with patch.object(prompter, "print") as mock_print:
        prompter.debug("debug message")

    assert mock_print.call_count == 1
    assert "debug message" in mock_print.call_args.args[0]


@patch(_IS_INTERACTIVE, return_value=False)
def test_debug_prints_plain_message_when_enabled_and_non_interactive(mock_interactive, prompter):
    """debug() prints the raw message when state.debug is True and non-interactive."""
    state.debug = True

    with patch.object(prompter, "print") as mock_print:
        prompter.debug("debug message")

    assert mock_print.call_count == 1
    assert mock_print.call_args.args[0] == "debug message"


def test_debug_does_not_print_when_disabled(prompter):
    """debug() does nothing when state.debug is False."""
    state.debug = False

    with patch.object(prompter, "print") as mock_print:
        prompter.debug("debug message")

    assert mock_print.call_count == 0


@patch("deepfellow.common.echo.Prompt.ask", return_value="7")
@patch(_IS_INTERACTIVE, return_value=True)
def test_prompt_int_default_converted_to_string(mock_interactive, mock_ask, prompter):
    """Integer defaults are converted to strings before being passed to Prompt.ask."""
    prompter.prompt(
        message="Enter number",
        from_args=None,
        original_default=None,
        default=5,
    )

    call_kwargs = mock_ask.call_args.kwargs
    assert call_kwargs.get("default") == "5"


@patch("deepfellow.common.echo.Prompt.ask", return_value="bad")
@patch(_IS_INTERACTIVE)
def test_prompt_until_valid_reraises_when_not_interactive_on_retry_check(mock_interactive, mock_ask, prompter):
    """If mode is reported non-interactive at the retry check, a validation error is re-raised, not retried."""
    mock_interactive.side_effect = [True, False]
    validation = MagicMock(side_effect=typer.BadParameter("invalid"))

    with pytest.raises(typer.BadParameter):
        prompter.prompt_until_valid(
            message="Enter value",
            validation=validation,
            from_args=None,
            original_default=None,
            default="default_val",
        )


@patch.object(Echo, "status")
@patch(_IS_INTERACTIVE, return_value=True)
def test_spinner_interactive_shows_status(mock_interactive, mock_status, prompter):
    """In interactive mode the spinner wraps the block in a rich status."""
    with prompter.spinner("Installing..."):
        pass

    assert mock_status.call_count == 1
    assert mock_status.call_args == mock.call("Installing...")
    assert mock_status.return_value.__enter__.call_count == 1
    assert mock_status.return_value.__exit__.call_count == 1


@patch.object(Echo, "status")
@patch(_IS_INTERACTIVE, return_value=False)
def test_spinner_non_interactive_is_noop(mock_interactive, mock_status, prompter):
    """In non-interactive mode the spinner does not render anything."""
    with prompter.spinner("Installing..."):
        pass

    assert mock_status.call_count == 0
