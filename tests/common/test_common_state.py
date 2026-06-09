# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the state module."""

from deepfellow.common.defaults import DF_CLI_CONFIG_PATH, DF_CLI_SECRETS_PATH
from deepfellow.common.state import AppState, state


def test_appstate_call_returns_the_same_instance():
    assert AppState() is AppState()


def test_appstate_call_returns_the_module_level_state():
    assert AppState() is state


def test_appstate_second_construction_does_not_reset_existing_values():
    state.debug = True

    new = AppState()

    assert new.debug is True


def test_reset_restores_every_field_to_default():
    state.debug = True
    state.yes = True
    state.non_interactive = True
    state.cli_config = {"df_server_url": "http://example.com"}
    state.cli_config_file = DF_CLI_CONFIG_PATH / "other"
    state.cli_secrets_file = DF_CLI_SECRETS_PATH / "other"

    state.reset()

    assert state.debug is False
    assert state.yes is False
    assert state.non_interactive is False
    assert state.cli_config == {}
    assert state.cli_config_file == DF_CLI_CONFIG_PATH
    assert state.cli_secrets_file == DF_CLI_SECRETS_PATH


def test_reset_cli_config_is_a_fresh_dict():
    first = state.cli_config
    state.reset()

    assert state.cli_config is not first
    assert state.cli_config == {}
