# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for configure_otel, configure_embedding, configure_infra and configure_milvus_specific_fields."""

from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.common.defaults import (
    ALLOWED_VECTOR_DB_TYPES,
    DEFAULT_OTEL_URL,
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_URL,
    DOCKER_COMPOSE_OTEL_COLLECTOR,
    MILVUS_DATABASE,
    MONGO_DB_INIT_SH,
    QDRANT_DATABASE,
    SPARSE_EMBEDDING_MODEL,
    SPARSE_EMBEDDING_SIZE,
)
from deepfellow.common.validation import validate_truthy, validate_url
from deepfellow.server.utils.configure import (
    configure_embedding,
    configure_infra,
    configure_milvus_specific_fields,
    configure_mongo,
    configure_otel,
    configure_vector_db,
    is_custom_vectordb,
    should_use_vector_db,
)


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
        force_provided=False,
    )
    assert size_call == mock.call(
        "Provide the embedding size",
        from_args="",
        original_default=DEFAULT_VECTOR_DATABASE["embedding"]["size"],
        default="768",
        force_provided=False,
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
def test_configure_otel_url_provided_directly_is_validated(mock_echo, mock_load, mock_save, tmp_directory):
    """A caller passing otel_url directly (bypassing the interactive prompt, which validates
    itself) still gets the URL validated, instead of it being silently written unchecked."""
    with pytest.raises(typer.BadParameter):
        configure_otel(tmp_directory, "not-a-url", None)

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


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_infra_returns_url_and_api_key(mock_echo):
    mock_echo.prompt_until_valid.side_effect = ["http://infra:8086", "secret-key"]

    result = configure_infra("secret-key", "http://infra:8086", None)

    assert result == {"DF_INFRA__URL": "http://infra:8086", "DF_INFRA__API_KEY": "secret-key"}


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_infra_force_provided_url_reaches_prompt_until_valid(mock_echo):
    """force_provided_url must reach echo.prompt_until_valid's own force_provided kwarg, so a
    --template config value equal to infra_url's own original_default (DF_INFRA_URL) is not
    mistaken for "nothing was provided" and re-prompted for."""
    mock_echo.prompt_until_valid.side_effect = [DF_INFRA_URL, "secret-key"]

    configure_infra("secret-key", DF_INFRA_URL, None, force_provided_url=True)

    assert mock_echo.prompt_until_valid.call_args_list[0] == mock.call(
        "Provide DeepFellow Infra URL",
        validate_url,
        error_message="Invalid DeepFellow Infra URL. Please try again.",
        from_args=DF_INFRA_URL,
        original_default=DF_INFRA_URL,
        default=DF_INFRA_URL,
        force_provided=True,
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_infra_force_provided_url_defaults_to_false(mock_echo):
    """Without an explicit force_provided_url, configure_infra must not force it - the flag's
    absence must not accidentally suppress the prompt for a value that was never provided."""
    mock_echo.prompt_until_valid.side_effect = [DF_INFRA_URL, "secret-key"]

    configure_infra("secret-key", DF_INFRA_URL, None)

    assert mock_echo.prompt_until_valid.call_args_list[0].kwargs["force_provided"] is False


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_infra_force_provided_api_key_reaches_prompt_until_valid(mock_echo):
    """force_provided_api_key must reach echo.prompt_until_valid's own force_provided kwarg - the
    built-in "workspace" template deliberately omits infra_api_key (see
    deepfellow.server.utils.templates.BUILTIN_TEMPLATES), but a custom YAML template could still
    supply one equal to its own original_default (None), which needs the same handling."""
    mock_echo.prompt_until_valid.side_effect = [DF_INFRA_URL, "secret-key"]

    configure_infra("secret-key", DF_INFRA_URL, None, force_provided_api_key=True)

    assert mock_echo.prompt_until_valid.call_args_list[1] == mock.call(
        "Provide Deepfellow Infra API KEY",
        validation=validate_truthy,
        from_args="secret-key",
        original_default=None,
        default="",
        password=True,
        force_provided=True,
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_milvus_specific_fields_generates_credentials_when_missing(mock_echo):
    """Custom Milvus with no credentials provided must not raise KeyError, and must generate
    fresh user/password values rather than defaulting to something empty/missing."""
    mock_echo.prompt_until_valid.side_effect = ["deepfellow-db", "generated-user", "generated-password"]

    result = configure_milvus_specific_fields({}, "deepfellow", "", "")

    assert result == {"db": "deepfellow-db", "user": "generated-user", "password": "generated-password"}
    assert mock_echo.prompt_until_valid.call_count == 3
    generated_username = mock_echo.prompt_until_valid.call_args_list[1].kwargs["default"]
    generated_password = mock_echo.prompt_until_valid.call_args_list[2].kwargs["default"]
    assert len(generated_username) == 8
    assert len(generated_password) == 12
    assert mock_echo.prompt_until_valid.call_args_list[1] == mock.call(
        "Provide Milvus provider user",
        validate_truthy,
        from_args="",
        original_default="",
        default=generated_username,
    )
    assert mock_echo.prompt_until_valid.call_args_list[2] == mock.call(
        "Provide Milvus provider password",
        validate_truthy,
        from_args="",
        original_default="",
        default=generated_password,
        password=True,
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_milvus_specific_fields_explicit_username_not_overridden_by_env(mock_echo):
    """A --vectordb-username explicitly provided on the CLI must reach echo as a distinct
    from_args (differing from original_default), so it is not silently replaced by a stale
    user/password already present in the existing .env (original_provider)."""
    mock_echo.prompt_until_valid.side_effect = ["deepfellow-db", "explicit-user", "explicit-password"]
    original_provider = {"user": "stale-env-user", "password": "stale-env-password"}

    result = configure_milvus_specific_fields(original_provider, "deepfellow", "explicit-user", "explicit-password")

    assert result == {"db": "deepfellow-db", "user": "explicit-user", "password": "explicit-password"}
    assert mock_echo.prompt_until_valid.call_args_list[1] == mock.call(
        "Provide Milvus provider user",
        validate_truthy,
        from_args="explicit-user",
        original_default="",
        default="stale-env-user",
    )
    assert mock_echo.prompt_until_valid.call_args_list[2] == mock.call(
        "Provide Milvus provider password",
        validate_truthy,
        from_args="explicit-password",
        original_default="",
        default="stale-env-password",
        password=True,
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_milvus_specific_fields_force_provided_database_name_reaches_prompt(mock_echo: mock.MagicMock):
    mock_echo.prompt_until_valid.side_effect = ["deepfellow-db", "generated-user", "generated-password"]

    configure_milvus_specific_fields({}, "deepfellow", "", "", force_provided_database_name=True)

    assert mock_echo.prompt_until_valid.call_args_list[0] == mock.call(
        "Provide Milvus provider database name",
        validate_truthy,
        from_args="deepfellow",
        original_default=MILVUS_DATABASE["provider"]["db"],
        default="deepfellow",
        force_provided=True,
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_should_use_vector_db_false_when_disabled_and_not_default(mock_echo):
    default_active = DEFAULT_VECTOR_DATABASE["provider"]["active"]

    result = should_use_vector_db(0 if default_active else 1)

    assert result is False
    assert mock_echo.warning.call_count == 1
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.configure.echo")
def test_should_use_vector_db_false_when_user_declines(mock_echo):
    mock_echo.confirm.return_value = False
    default_active = DEFAULT_VECTOR_DATABASE["provider"]["active"]

    result = should_use_vector_db(default_active)

    assert result is False
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.utils.configure.echo")
def test_should_use_vector_db_true_when_user_confirms(mock_echo):
    mock_echo.confirm.return_value = True
    default_active = DEFAULT_VECTOR_DATABASE["provider"]["active"]

    result = should_use_vector_db(default_active)

    assert result is True
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.utils.configure.echo")
def test_is_custom_vectordb_true_when_qdrant_url_changed(mock_echo):
    result = is_custom_vectordb("qdrant", "http://custom-qdrant:6333", "")

    assert result is True
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.configure.echo")
def test_is_custom_vectordb_true_when_milvus_db_name_changed(mock_echo):
    result = is_custom_vectordb(
        "milvus",
        MILVUS_DATABASE["provider"]["url"],
        "custom-db-name",
    )

    assert result is True
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.configure.echo")
def test_is_custom_vectordb_false_when_defaults_and_local_confirmed(mock_echo):
    mock_echo.confirm.return_value = True

    result = is_custom_vectordb(
        "qdrant",
        QDRANT_DATABASE["provider"]["url"],
        "",
    )

    assert result is False
    assert mock_echo.confirm.call_args == mock.call(
        "Install a local vector database for DeepFellow Server?", default=True
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_is_custom_vectordb_true_when_defaults_and_local_declined(mock_echo):
    mock_echo.confirm.return_value = False

    result = is_custom_vectordb(
        "milvus",
        MILVUS_DATABASE["provider"]["url"],
        MILVUS_DATABASE["provider"]["db"],
    )

    assert result is True


@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=False)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_returns_inactive_env_when_declined(mock_echo, mock_should_use_vector_db):
    active, env = configure_vector_db(
        "http://infra:8086",
        {},
        0,
        "qdrant",
        "http://qdrant:6333",
        "",
        "",
        "",
        "",
        "",
        False,
        "qdrant",
    )

    assert active is False
    assert env == {
        "DF_VECTOR_DATABASE__PROVIDER__ACTIVE": "0",
        "DF_VECTOR_DATABASE__EMBEDDING__ACTIVE": "0",
    }
    assert mock_should_use_vector_db.call_count == 1


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=False)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_managed_qdrant_generates_credentials(mock_echo, mock_should_use_vector_db, mock_is_custom):
    mock_echo.choice.return_value = "qdrant"

    active, env = configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        "http://qdrant:6333",
        "",
        "",
        "",
        "",
        "",
        True,
        "qdrant",
    )

    assert active is False
    assert env["DF_VECTOR_DATABASE__PROVIDER__TYPE"] == "qdrant"
    assert env["DF_VECTOR_DATABASE__PROVIDER__USER"]
    assert env["DF_VECTOR_DATABASE__PROVIDER__PASSWORD"]
    assert env["DF_VECTOR_DATABASE__EMBEDDING__MODEL"] == SPARSE_EMBEDDING_MODEL


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=True)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_custom_qdrant_prompts_for_url(mock_echo, mock_should_use_vector_db, mock_is_custom):
    mock_echo.choice.return_value = "qdrant"
    mock_echo.prompt_until_valid.return_value = "http://custom-qdrant:6333"

    active, env = configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        "http://custom-qdrant:6333",
        "",
        "",
        "",
        "",
        "",
        True,
        "qdrant",
    )

    assert active is True
    assert env["DF_VECTOR_DATABASE__PROVIDER__URL"] == "http://custom-qdrant:6333"
    assert env["DF_VECTOR_DATABASE__PROVIDER__TYPE"] == "qdrant"


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=True)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_force_provided_url_reaches_prompt_until_valid(
    mock_echo, mock_should_use_vector_db, mock_is_custom
):
    """force_provided_url must reach echo.prompt_until_valid's own force_provided kwarg for the
    vector database's own URL, so a --template config value equal to vectordb_url's own
    original_default is not mistaken for "nothing was provided" and re-prompted for."""
    mock_echo.choice.return_value = "qdrant"
    default_url = QDRANT_DATABASE["provider"]["url"]
    mock_echo.prompt_until_valid.return_value = default_url

    configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        default_url,
        "",
        "",
        "",
        "",
        "",
        True,
        "qdrant",
        force_provided_url=True,
    )

    assert mock_echo.prompt_until_valid.call_args == mock.call(
        "Provide Qdrant instance URL",
        validate_url,
        default=default_url,
        from_args=default_url,
        original_default=default_url,
        force_provided=True,
    )


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=True)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_force_provided_url_defaults_to_false(mock_echo, mock_should_use_vector_db, mock_is_custom):
    """Without an explicit force_provided_url, configure_vector_db must not force it - the flag's
    absence must not accidentally suppress the prompt for a value that was never provided."""
    mock_echo.choice.return_value = "qdrant"
    default_url = QDRANT_DATABASE["provider"]["url"]
    mock_echo.prompt_until_valid.return_value = default_url

    configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        default_url,
        "",
        "",
        "",
        "",
        "",
        True,
        "qdrant",
    )

    assert mock_echo.prompt_until_valid.call_args.kwargs["force_provided"] is False


@mock.patch("deepfellow.server.utils.configure.configure_milvus_specific_fields")
@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=True)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_custom_milvus_merges_specific_fields(
    mock_echo, mock_should_use_vector_db, mock_is_custom, mock_configure_milvus_specific_fields
):
    mock_echo.choice.return_value = "milvus"
    mock_echo.prompt_until_valid.return_value = "http://milvus:19530"
    mock_configure_milvus_specific_fields.return_value = {
        "db": "deepfellow-db",
        "user": "milvus-user",
        "password": "milvus-password",
    }

    active, env = configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "milvus",
        "http://milvus:19530",
        "deepfellow",
        "",
        "",
        "",
        "",
        True,
        "milvus",
    )

    assert active is True
    assert env["DF_VECTOR_DATABASE__PROVIDER__DB"] == "deepfellow-db"
    assert env["DF_VECTOR_DATABASE__PROVIDER__USER"] == "milvus-user"
    assert env["DF_VECTOR_DATABASE__PROVIDER__PASSWORD"] == "milvus-password"
    assert mock_configure_milvus_specific_fields.call_count == 1


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=False)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_managed_switches_default_url_on_type_change(
    mock_echo, mock_should_use_vector_db, mock_is_custom
):
    mock_echo.choice.return_value = "milvus"

    active, env = configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        DEFAULT_VECTOR_DATABASE["provider"]["url"],
        "",
        "",
        "",
        "",
        "",
        True,
        "milvus",
    )

    assert active is False
    assert env["DF_VECTOR_DATABASE__PROVIDER__URL"] == MILVUS_DATABASE["provider"]["url"]
    assert mock_is_custom.call_args == mock.call("milvus", MILVUS_DATABASE["provider"]["url"], "")


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=False)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_managed_generates_only_missing_password(
    mock_echo, mock_should_use_vector_db, mock_is_custom
):
    mock_echo.choice.return_value = "qdrant"

    active, env = configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        "http://qdrant:6333",
        "",
        "given-user",
        "",
        "",
        "",
        True,
        "qdrant",
    )

    assert active is False
    assert "DF_VECTOR_DATABASE__PROVIDER__USER" not in env
    assert env["DF_VECTOR_DATABASE__PROVIDER__PASSWORD"]


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=False)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_managed_generates_only_missing_username(
    mock_echo, mock_should_use_vector_db, mock_is_custom
):
    mock_echo.choice.return_value = "qdrant"

    active, env = configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        "http://qdrant:6333",
        "",
        "",
        "given-password",
        "",
        "",
        True,
        "qdrant",
    )

    assert active is False
    assert env["DF_VECTOR_DATABASE__PROVIDER__USER"]
    assert "DF_VECTOR_DATABASE__PROVIDER__PASSWORD" not in env


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=False)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_force_provided_type_reaches_choice_call(
    mock_echo: mock.MagicMock, mock_should_use_vector_db: mock.MagicMock, mock_is_custom: mock.MagicMock
):
    mock_echo.choice.side_effect = ["sparse", "qdrant"]

    configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        "http://qdrant:6333",
        "",
        "",
        "",
        "",
        "",
        False,
        "qdrant",
        force_provided_type=True,
    )

    assert mock_echo.choice.call_args_list[1] == mock.call(
        "Choose the type of the vector database",
        from_args="qdrant",
        original_default=DEFAULT_VECTOR_DATABASE_TYPE,
        choices=ALLOWED_VECTOR_DB_TYPES,
        default="qdrant",
        force_provided=True,
    )


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=False)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_managed_force_provided_embedding_reaches_prompt(
    mock_echo: mock.MagicMock, mock_should_use_vector_db: mock.MagicMock, mock_is_custom: mock.MagicMock
):
    mock_echo.choice.side_effect = ["dense", "qdrant"]
    mock_echo.prompt.side_effect = ["my-model", "512"]

    configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        "http://qdrant:6333",
        "",
        "",
        "",
        "my-model",
        "512",
        False,
        "qdrant",
        force_provided_model=True,
        force_provided_size=True,
    )

    model_call, size_call = mock_echo.prompt.call_args_list
    assert model_call == mock.call(
        "Provide the model for embedding",
        from_args="my-model",
        original_default=DEFAULT_VECTOR_DATABASE["embedding"]["model"],
        default="my-model",
        force_provided=True,
    )
    assert size_call == mock.call(
        "Provide the embedding size",
        from_args="512",
        original_default=DEFAULT_VECTOR_DATABASE["embedding"]["size"],
        default="512",
        force_provided=True,
    )


@mock.patch("deepfellow.server.utils.configure.is_custom_vectordb", return_value=True)
@mock.patch("deepfellow.server.utils.configure.should_use_vector_db", return_value=True)
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_vector_db_custom_force_provided_embedding_reaches_prompt(
    mock_echo: mock.MagicMock, mock_should_use_vector_db: mock.MagicMock, mock_is_custom: mock.MagicMock
):
    mock_echo.choice.side_effect = ["dense", "qdrant"]
    mock_echo.prompt_until_valid.return_value = "http://custom-qdrant:6333"
    mock_echo.prompt.side_effect = ["my-model", "512"]

    configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        "http://custom-qdrant:6333",
        "",
        "",
        "",
        "my-model",
        "512",
        False,
        "qdrant",
        force_provided_model=True,
        force_provided_size=True,
    )

    model_call, size_call = mock_echo.prompt.call_args_list
    assert model_call == mock.call(
        "Provide the model for embedding",
        from_args="my-model",
        original_default=DEFAULT_VECTOR_DATABASE["embedding"]["model"],
        default="my-model",
        force_provided=True,
    )
    assert size_call == mock.call(
        "Provide the embedding size",
        from_args="512",
        original_default=DEFAULT_VECTOR_DATABASE["embedding"]["size"],
        default="512",
        force_provided=True,
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_infra_url_uses_prompt_until_valid_with_validate_url(mock_echo):
    """Retrying on an invalid URL is echo.prompt_until_valid's own responsibility (see
    tests/common/test_common_echo.py) - configure_infra only needs to wire validate_url and a
    custom error_message into it, not implement retry itself."""
    mock_echo.prompt_until_valid.side_effect = ["http://infra:8086", "secret-key"]

    configure_infra("secret-key", "not-a-url", None)

    assert mock_echo.prompt_until_valid.call_args_list[0] == mock.call(
        "Provide DeepFellow Infra URL",
        validate_url,
        error_message="Invalid DeepFellow Infra URL. Please try again.",
        from_args="not-a-url",
        original_default=DF_INFRA_URL,
        default="not-a-url",
        force_provided=False,
    )


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_mongo_custom_prompts_all_fields(mock_echo, tmp_directory: Path):
    mock_echo.prompt_until_valid.side_effect = [
        "192.168.1.5:27017",
        "custom-db",
        "custom-user",
        "custom-password",
    ]

    result = configure_mongo(tmp_directory, True, "custom-user", "custom-password")

    assert result == {
        "DF_MONGO_URL": "192.168.1.5:27017",
        "DF_MONGO_USER": "custom-user",
        "DF_MONGO_PASSWORD": "custom-password",
        "DF_MONGO_DB": "custom-db",
    }
    assert mock_echo.prompt_until_valid.call_count == 4
    assert not (tmp_directory / "init-mongo.sh").exists()


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_mongo_default_generates_missing_credentials_and_writes_init_script(mock_echo, tmp_directory: Path):
    result = configure_mongo(tmp_directory, False, "", "")

    assert result["DF_MONGO_URL"] == DF_MONGO_URL
    assert result["DF_MONGO_DB"] == DF_MONGO_DB
    assert result["DF_MONGO_USER"]
    assert result["DF_MONGO_PASSWORD"]
    assert result["DF_MONGO_INITDB_ROOT_USERNAME"]
    assert result["DF_MONGO_INITDB_ROOT_PASSWORD"]
    assert result["DF_MONGO_PORT"] == "27017"
    init_script = tmp_directory / "init-mongo.sh"
    assert init_script.read_text() == MONGO_DB_INIT_SH
    assert (init_script.stat().st_mode & 0o777) == 0o755
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_mongo_default_preserves_provided_user_and_password(mock_echo, tmp_directory: Path):
    result = configure_mongo(tmp_directory, False, "given-user", "given-password")

    assert result["DF_MONGO_USER"] == "given-user"
    assert result["DF_MONGO_PASSWORD"] == "given-password"


@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_mongo_default_reuses_existing_admin_credentials(mock_echo, tmp_directory: Path):
    original_env = {
        "df_mongo_initdb_root_username": "existing-admin",
        "df_mongo_initdb_root_password": "existing-admin-password",
    }

    result = configure_mongo(tmp_directory, False, "", "", original_env=original_env)

    assert result["DF_MONGO_INITDB_ROOT_USERNAME"] == "existing-admin"
    assert result["DF_MONGO_INITDB_ROOT_PASSWORD"] == "existing-admin-password"


@mock.patch.object(Path, "write_text", side_effect=OSError("Permission denied"))
@mock.patch("deepfellow.server.utils.configure.echo")
def test_configure_mongo_default_raises_on_write_error(mock_echo, mock_write_text, tmp_directory: Path):
    with pytest.raises(typer.Exit):
        configure_mongo(tmp_directory, False, "", "")

    assert mock_echo.error.call_count == 1
