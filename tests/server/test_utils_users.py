from pathlib import Path
from unittest import mock

from deepfellow.server.utils.users import create_admin


@mock.patch("deepfellow.common.echo.Prompt.ask")
@mock.patch("deepfellow.server.utils.users.validate_email")
@mock.patch("deepfellow.server.utils.users.run")
def test_create_admin_prompt_email_validation_called(
    mock_run: mock.Mock, mock_validate_email: mock.Mock, mock_ask: mock.Mock
):
    mock_validate_email.return_value = "some@email.com"
    mock_ask.side_effect = ("name", "provided@email.com", "password")

    create_admin(Path(), None, None, None)

    assert mock_validate_email.call_count == 1
    assert mock_validate_email.call_args == mock.call("provided@email.com")
    assert "some@email.com" in mock_run.call_args_list[0][0][0]
