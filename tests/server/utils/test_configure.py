# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for configure_otel and configure_embedding."""

from unittest import mock

import pytest

from deepfellow.common.defaults import (
    DEFAULT_OTEL_URL,
    DEFAULT_VECTOR_DATABASE,
    DOCKER_COMPOSE_OTEL_COLLECTOR,
    SPARSE_EMBEDDING_MODEL,
    SPARSE_EMBEDDING_SIZE,
)
from deepfellow.server.utils.configure import configure_embedding, configure_otel


@pytest.fixture
def tmp_directory(tmp_path):
    return tmp_path


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_embedding_sparse_flag_skips_choice_and_prompts(mock_echo):
    result = configure_embedding("http://infra:8086", {}, "", "", embedding_sparse=True)

    assert result["model"] == SPARSE_EMBEDDING_MODEL
    assert result["size"] == SPARSE_EMBEDDING_SIZE
    assert result["active"] == 1
    assert result["endpoint"] == "http://infra:8086"
    assert mock_echo.choice.call_count == 0
    assert mock_echo.prompt.call_count == 0


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_embedding_sparse_returns_fixed_model_and_size(mock_echo):
    mock_echo.choice.return_value = "sparse"

    result = configure_embedding("http://infra:8086", {}, "", "")

    assert result["model"] == SPARSE_EMBEDDING_MODEL
    assert result["size"] == SPARSE_EMBEDDING_SIZE
    assert result["active"] == 1
    assert result["endpoint"] == "http://infra:8086"
    assert mock_echo.prompt.call_count == 0


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_embedding_dense_prompts_for_model_and_size(mock_echo):
    mock_echo.choice.return_value = "dense"
    mock_echo.prompt.side_effect = ["my-model", "512"]

    result = configure_embedding("http://infra:8086", {}, "", "")

    assert result["model"] == "my-model"
    assert result["size"] == "512"
    assert result["active"] == 1
    assert result["endpoint"] == "http://infra:8086"
    assert mock_echo.prompt.call_count == 2


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_embedding_reconfigure_sparse_defaults_to_sparse_type(mock_echo):
    mock_echo.choice.return_value = "sparse"
    original_env = {"df_vector_database": {"embedding": {"model": SPARSE_EMBEDDING_MODEL}}}

    configure_embedding("http://infra:8086", original_env, "", "")

    assert mock_echo.choice.call_count == 1
    assert mock_echo.choice.call_args == mock.call(
        "Choose embedding type",
        choices=["dense", "sparse"],
        default="sparse",
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_embedding_reconfigure_dense_defaults_to_dense_type(mock_echo):
    mock_echo.choice.return_value = "dense"
    mock_echo.prompt.side_effect = ["mxbai-embed-large", "1024"]
    original_env = {"df_vector_database": {"embedding": {"model": "mxbai-embed-large"}}}

    configure_embedding("http://infra:8086", original_env, "", "")

    assert mock_echo.choice.call_count == 1
    assert mock_echo.choice.call_args == mock.call(
        "Choose embedding type",
        choices=["dense", "sparse"],
        default="dense",
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_embedding_reconfigure_dense_prompts_default_from_existing_env(mock_echo):
    mock_echo.choice.return_value = "dense"
    mock_echo.prompt.side_effect = ["custom-model", "768"]
    original_env = {"df_vector_database": {"embedding": {"model": "custom-model", "size": "768"}}}

    configure_embedding("http://infra:8086", original_env, "", "")

    model_call, size_call = mock_echo.prompt.call_args_list
    assert model_call == mock.call(
        "Provide the model for embedding",
        from_args="",
        original_default=DEFAULT_VECTOR_DATABASE["embedding"]["model"],
        default="custom-model",
    )
    assert size_call == mock.call(
        "Provide the embedding size",
        from_args="",
        original_default=DEFAULT_VECTOR_DATABASE["embedding"]["size"],
        default="768",
    )


@mock.patch("deepfellow.server.utils.configure.save_compose_file")
@mock.patch("deepfellow.server.utils.configure.load_compose_file", return_value={})
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_otel_no_otel_chosen(mock_echo, mock_load, mock_save, tmp_directory):
    mock_echo.confirm.return_value = False

    result = configure_otel(tmp_directory, None, None)

    assert result.envs == {}
    assert result.docker_compose == {}
    assert mock_save.call_count == 0


@mock.patch("deepfellow.server.utils.configure.save_compose_file")
@mock.patch("deepfellow.server.utils.configure.load_compose_file", return_value={})
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_otel_external_server_provided(mock_echo, mock_load, mock_save, tmp_directory):
    mock_echo.confirm.return_value = True
    mock_echo.prompt_until_valid.return_value = "http://otel.example.com:4317"

    result = configure_otel(tmp_directory, None, None)

    assert result.envs["DF_OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://otel.example.com:4317"
    assert result.envs["DF_OTEL_TRACING_ENABLED"] == "true"
    assert result.docker_compose == {}
    assert mock_save.call_count == 0


@mock.patch("deepfellow.server.utils.configure.save_compose_file")
@mock.patch("deepfellow.server.utils.configure.load_compose_file", return_value={})
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_otel_local_run_debug_only(mock_echo, mock_load, mock_save, tmp_directory):
    # First confirm: "Do you have an Open Telemetry server ready?" -> False
    # Second confirm: "Do you want to run Open Telemetry from this machine?" -> True
    # Third confirm: "Do you want to export to Elasticsearch?" -> False
    mock_echo.confirm.side_effect = [False, True, False]

    result = configure_otel(tmp_directory, None, None)

    assert result.envs["DF_OTEL_EXPORTER_OTLP_ENDPOINT"] == DEFAULT_OTEL_URL
    assert result.envs["DF_OTEL_TRACING_ENABLED"] == "true"
    assert result.docker_compose == DOCKER_COMPOSE_OTEL_COLLECTOR
    assert mock_save.call_count == 1
    saved_config = mock_save.call_args[0][0]
    assert "elasticsearch" not in saved_config.get("exporters", {})
    assert "basicauth" not in saved_config.get("extensions", {})
    for pipeline in saved_config["service"]["pipelines"].values():
        assert pipeline["exporters"] == ["debug"]


@mock.patch("deepfellow.server.utils.configure.save_compose_file")
@mock.patch("deepfellow.server.utils.configure.load_compose_file", return_value={})
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_otel_local_run_with_elasticsearch(mock_echo, mock_load, mock_save, tmp_directory):
    # First confirm: "Do you have an Open Telemetry server ready?" -> False
    # Second confirm: "Do you want to run Open Telemetry from this machine?" -> True
    # Third confirm: "Do you want to export to Elasticsearch?" -> True
    mock_echo.confirm.side_effect = [False, True, True]
    mock_echo.prompt_until_valid.side_effect = [
        "https://elastic:9200",
        "traces",
        "user",
        "pass",
    ]

    result = configure_otel(tmp_directory, None, None)

    assert result.envs["DF_OTEL_EXPORTER_OTLP_ENDPOINT"] == DEFAULT_OTEL_URL
    assert result.envs["DF_OTEL_TRACING_ENABLED"] == "true"
    assert result.docker_compose == DOCKER_COMPOSE_OTEL_COLLECTOR
    assert mock_save.call_count == 1
    saved_config = mock_save.call_args[0][0]
    assert saved_config["exporters"]["elasticsearch"]["endpoint"] == "https://elastic:9200"
    assert saved_config["exporters"]["elasticsearch"]["traces_index"] == "traces"
    assert saved_config["extensions"]["basicauth"]["client_auth"]["username"] == "user"
    assert saved_config["extensions"]["basicauth"]["client_auth"]["password"] == "pass"
    for pipeline in saved_config["service"]["pipelines"].values():
        assert "elasticsearch" in pipeline["exporters"]
        assert "debug" in pipeline["exporters"]


@mock.patch("deepfellow.server.utils.configure.save_compose_file")
@mock.patch("deepfellow.server.utils.configure.load_compose_file", return_value={})
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_otel_url_provided_skips_prompts(mock_echo, mock_load, mock_save, tmp_directory):
    result = configure_otel(tmp_directory, "http://existing-otel:4317", None)

    assert result.envs["DF_OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://existing-otel:4317"
    assert mock_echo.confirm.call_count == 0
    assert mock_save.call_count == 0


@mock.patch("deepfellow.server.utils.configure.save_compose_file")
@mock.patch("deepfellow.server.utils.configure.load_compose_file", return_value={})
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_otel_local_run_debug_only_non_interactive_defaults(mock_echo, mock_load, mock_save, tmp_directory):
    # In non-interactive mode, echo.confirm uses defaults: False, True (config_file doesn't exist), False
    mock_echo.confirm.side_effect = [False, True, False]

    result = configure_otel(tmp_directory, None, None)

    assert result.docker_compose == DOCKER_COMPOSE_OTEL_COLLECTOR
    saved_config = mock_save.call_args[0][0]
    for pipeline in saved_config["service"]["pipelines"].values():
        assert pipeline["exporters"] == ["debug"]


@mock.patch("deepfellow.server.utils.configure.save_compose_file")
@mock.patch("deepfellow.server.utils.configure.load_compose_file", return_value={})
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_otel_local_flag_skips_prompts_debug_only(mock_echo, mock_load, mock_save, tmp_directory):
    result = configure_otel(tmp_directory, None, None, otel_local=True)

    assert result.docker_compose == DOCKER_COMPOSE_OTEL_COLLECTOR
    assert result.envs["DF_OTEL_EXPORTER_OTLP_ENDPOINT"] == DEFAULT_OTEL_URL
    assert result.envs["DF_OTEL_TRACING_ENABLED"] == "true"
    assert mock_echo.confirm.call_count == 0
    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_load.call_count == 0
    assert mock_save.call_count == 1
    saved_config = mock_save.call_args[0][0]
    assert mock_save.call_args == mock.call(
        saved_config,
        tmp_directory / "otel-collector-config.yaml",
        quiet=True,
        file_info="Open Telemetry collector configuration",
    )
    assert "elasticsearch" not in saved_config.get("exporters", {})
    assert "basicauth" not in saved_config.get("extensions", {})
    for pipeline in saved_config["service"]["pipelines"].values():
        assert pipeline["exporters"] == ["debug"]


@mock.patch("deepfellow.server.utils.configure.save_compose_file")
@mock.patch("deepfellow.server.utils.configure.load_compose_file", return_value={})
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_otel_flag_off_still_uses_prompt_flow(mock_echo, mock_load, mock_save, tmp_directory):
    mock_echo.confirm.side_effect = [False, False]

    result = configure_otel(tmp_directory, None, None)

    assert mock_echo.confirm.call_count == 2
    assert result.docker_compose == {}
    assert mock_save.call_count == 0
