# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Iterator
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.infra.utils.update_spec import (
    DockerTags,
    build_updated_spec,
    confirm_version_change,
    fetch_docker_tags,
    installed_spec,
    resolve_image_version,
)

FIELDS = [{"name": "image_version", "type": "docker-tags"}]


@pytest.fixture(autouse=True)
def mock_echo() -> Iterator[Mock]:
    with mock.patch("deepfellow.infra.utils.update_spec.echo") as echo:
        yield echo


def test_installed_spec_reads_model_settings_from_spec() -> None:
    result = installed_spec({"registration_id": "abc", "spec": {"prefix": "x"}}, "m")

    assert result == {"prefix": "x"}


def test_installed_spec_treats_model_without_spec_as_default_settings() -> None:
    assert installed_spec({"registration_id": "abc", "spec": None}, "m") == {}


def test_installed_spec_reads_service_settings_directly() -> None:
    assert installed_spec({"hardware": "GPU"}, "ollama") == {"hardware": "GPU"}


@pytest.mark.parametrize(
    "installed",
    [{"stage": "downloading", "value": 0.5}, True],
    ids=["install-in-progress", "no-settings"],
)
def test_installed_spec_rejects_entry_that_is_still_installing(installed: Any, mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit):
        installed_spec(installed, "m")

    assert mock_echo.error.call_args == mock.call(
        "'m' is still installing or reports no settings. Try again when it is installed."
    )


def test_build_updated_spec_merges_json_spec_and_image_version() -> None:
    result = build_updated_spec({"a": 1, "image_version": "v1"}, '{"a": 2}', None, "v2")

    assert result == {"a": 2, "image_version": "v2"}


def test_build_updated_spec_keeps_current_without_changes() -> None:
    assert build_updated_spec({"a": 1}, None, None, None) == {"a": 1}


def test_resolve_image_version_prefers_requested_tag() -> None:
    assert resolve_image_version("v1", False, "s", "k", "custom", {}, FIELDS) == "v1"


def test_resolve_image_version_keeps_image_for_other_changes() -> None:
    assert resolve_image_version(None, True, "s", "k", "custom", {}, []) is None


@mock.patch("deepfellow.infra.utils.update_spec.get")
@mock.patch("deepfellow.infra.utils.update_spec.call_infra")
def test_fetch_docker_tags_without_hardware_or_model_sends_no_query(mock_call: Mock, mock_get: Mock) -> None:
    mock_call.side_effect = lambda request, *args, **kwargs: request()
    mock_get.return_value = {"image": "hub/x", "tags": ["1.0.0"]}

    result = fetch_docker_tags("http://infra:8086", "key", "ollama|cpu", None)

    assert result == DockerTags(image="hub/x", tags=["1.0.0"], default=None)
    assert mock_get.call_args.args[0] == "http://infra:8086/admin/services/ollama|cpu/docker-tags"


@pytest.mark.parametrize(
    "data", [{"registry_unavailable": True, "tags": []}, {"tags": []}], ids=["unavailable", "empty"]
)
@mock.patch("deepfellow.infra.utils.update_spec.call_infra")
def test_fetch_docker_tags_fails_when_registry_gives_no_tags(
    mock_call: Mock, data: dict[str, Any], mock_echo: Mock
) -> None:
    mock_call.return_value = data

    with pytest.raises(typer.Exit):
        fetch_docker_tags("http://infra:8086", "key", "ollama", None)

    assert mock_echo.error.call_args == mock.call(
        "Infra cannot list Docker image versions right now. Check its connection to the registry."
    )


def test_confirm_version_change_skips_question_when_tag_is_unchanged(mock_echo: Mock) -> None:
    assert confirm_version_change("m", {"image_version": "v1", "a": 1}, {"image_version": "v1", "a": 2}) is True
    assert mock_echo.confirm.call_count == 0


def test_build_updated_spec_merges_nested_maps_instead_of_replacing_them() -> None:
    current = {"envs": {"API_KEY": "secret", "MODE": "a"}, "headers": {"X": "1"}, "prefix": "p"}

    result = build_updated_spec(current, '{"envs": {"MODE": "b", "NEW": "1"}}', None, None)

    assert result == {"envs": {"API_KEY": "secret", "MODE": "b", "NEW": "1"}, "headers": {"X": "1"}, "prefix": "p"}


def test_build_updated_spec_replaces_non_map_value_with_map() -> None:
    assert build_updated_spec({"envs": "none"}, '{"envs": {"A": "1"}}', None, None) == {"envs": {"A": "1"}}


@pytest.mark.parametrize("requested", [None, "v2.4.0"], ids=["newest", "requested"])
def test_resolve_image_version_fails_without_docker_tags_field(requested: str | None, mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit):
        resolve_image_version(requested, False, "s", "k", "ollama", {}, [{"name": "x", "type": "text"}], "llama3.1:8b")

    assert mock_echo.error.call_args == mock.call(
        "'llama3.1:8b' has no Docker image version setting. Change its settings with --set or --spec."
    )


@mock.patch("deepfellow.infra.utils.update_spec.fetch_docker_tags")
def test_resolve_image_version_picks_newest_within_installed_variant(mock_tags: Mock) -> None:
    mock_tags.return_value = DockerTags(
        image="hub/sglang", tags=["v0.5.3-cu126", "v0.5.2-cu128", "v0.5.1-cu128"], installed="v0.5.1-cu128"
    )

    result = resolve_image_version(None, False, "s", "k", "sglang", {"image_version": "v0.5.1-cu128"}, FIELDS)

    assert result == "v0.5.2-cu128"


@mock.patch("deepfellow.infra.utils.update_spec.fetch_docker_tags")
def test_resolve_image_version_fails_when_installed_variant_has_no_release(mock_tags: Mock, mock_echo: Mock) -> None:
    mock_tags.return_value = DockerTags(image="hub/x", tags=["v1.0.0-cu128"])

    with pytest.raises(typer.Exit):
        resolve_image_version(None, False, "s", "k", "sglang", {}, FIELDS)

    assert mock_echo.error.call_args == mock.call(
        "Infra lists no release version matching the installed one of 'sglang'. "
        "Choose one with --image-version; `versions` lists the tags."
    )


@mock.patch("deepfellow.infra.utils.update_spec.get")
@mock.patch("deepfellow.infra.utils.update_spec.call_infra")
def test_fetch_docker_tags_sends_stored_false_hardware(mock_call: Mock, mock_get: Mock) -> None:
    mock_call.side_effect = lambda request, *args, **kwargs: request()
    mock_get.return_value = {"image": "hub/x", "tags": ["v1.0.0"]}

    fetch_docker_tags("http://infra:8086", "key", "vllm", {"hardware": False})

    assert mock_get.call_args.args[0] == "http://infra:8086/admin/services/vllm/docker-tags?hardware=False"


@mock.patch("deepfellow.infra.utils.update_spec.get")
@mock.patch("deepfellow.infra.utils.update_spec.call_infra")
def test_fetch_docker_tags_quotes_ids_consistently(mock_call: Mock, mock_get: Mock) -> None:
    mock_call.side_effect = lambda request, *args, **kwargs: request()
    mock_get.return_value = {"image": "hub/x", "tags": ["v1.0.0"]}

    fetch_docker_tags("http://infra:8086", "key", "ollama|cpu", None, "org/model:8b")

    assert (
        mock_get.call_args.args[0]
        == "http://infra:8086/admin/services/ollama|cpu/docker-tags?model_id=org%2Fmodel%3A8b"
    )


@mock.patch("deepfellow.infra.utils.update_spec.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.update_spec.state", yes=False)
def test_confirm_version_change_asks_with_old_and_new_tag(
    mock_state: Mock, mock_interactive: Mock, mock_echo: Mock
) -> None:
    mock_echo.confirm.return_value = True

    result = confirm_version_change("doc_chunker", {"image_version": "v2.2.0"}, {"image_version": "v2.4.0"})

    assert result is True
    assert mock_echo.confirm.call_args == mock.call("Update 'doc_chunker' from v2.2.0 to v2.4.0?", default=True)


@mock.patch("deepfellow.infra.utils.update_spec.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.update_spec.state", yes=False)
def test_confirm_version_change_returns_false_when_user_declines(
    mock_state: Mock, mock_interactive: Mock, mock_echo: Mock
) -> None:
    mock_echo.confirm.return_value = False

    assert confirm_version_change("m", {"image_version": "v1.0.0"}, {"image_version": "v1.1.0"}) is False


@mock.patch("deepfellow.infra.utils.update_spec.state", yes=True)
def test_confirm_version_change_skips_question_with_yes(mock_state: Mock, mock_echo: Mock) -> None:
    assert confirm_version_change("m", {"image_version": "v1.0.0"}, {"image_version": "v1.1.0"}) is True
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.infra.utils.update_spec.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.update_spec.state", yes=False)
def test_confirm_version_change_exits_when_non_interactive_without_yes(
    mock_state: Mock, mock_interactive: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit):
        confirm_version_change("m", {"image_version": "v1.0.0"}, {"image_version": "v1.1.0"})

    assert mock_echo.confirm.call_count == 0
    assert mock_echo.error.call_args == mock.call(
        "The update changes the image version. Pass --yes to apply it without asking."
    )


@pytest.mark.parametrize(
    ("old", "new", "warning"),
    [
        ("v2.3.0-volta", "v2.4.0", "v2.4.0 is a different variant than v2.3.0-volta (-volta -> plain)"),
        ("v2.5.0-rc1", "v2.4.0", "v2.4.0 is a different variant than v2.5.0-rc1 (-rc1 -> plain)"),
        ("v2.5.0", "v2.4.0", "v2.4.0 is older than v2.5.0"),
    ],
    ids=["variant-dropped", "prerelease-to-release", "downgrade"],
)
@mock.patch("deepfellow.infra.utils.update_spec.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.update_spec.state", yes=False)
def test_confirm_version_change_warns_and_defaults_to_no(
    mock_state: Mock, mock_interactive: Mock, mock_echo: Mock, old: str, new: str, warning: str
) -> None:
    confirm_version_change("m", {"image_version": old}, {"image_version": new})

    assert mock_echo.warning.call_args == mock.call(warning)
    assert mock_echo.confirm.call_args.kwargs == {"default": False}


def test_docker_tags_newest_ignores_variants_without_installed_tag() -> None:
    tags = DockerTags(image="x", tags=["v2.4.0-volta", "v2.3.0", "v2.2.0"])

    assert tags.newest == "v2.3.0"


@pytest.mark.parametrize("old", [None, "latest"], ids=["bundled", "non-release"])
@mock.patch("deepfellow.infra.utils.update_spec.is_interactive", return_value=True)
@mock.patch("deepfellow.infra.utils.update_spec.state", yes=False)
def test_confirm_version_change_does_not_warn_when_old_tag_is_not_a_release(
    mock_state: Mock, mock_interactive: Mock, mock_echo: Mock, old: str | None
) -> None:
    confirm_version_change("m", {"image_version": old}, {"image_version": "v1.0.0"})

    assert mock_echo.warning.call_count == 0


NEEDS_CUDA = {"tag": "v0.5.21-cu130", "required_cuda": "13.0", "host_cuda": "12.9"}


@mock.patch("deepfellow.infra.utils.update_spec.get")
@mock.patch("deepfellow.infra.utils.update_spec.call_infra")
def test_fetch_docker_tags_sends_installed_tag_and_reads_what_infra_picked(mock_call: Mock, mock_get: Mock) -> None:
    mock_call.side_effect = lambda request, *args, **kwargs: request()
    mock_get.return_value = {
        "image": "hub/x",
        "tags": ["0.13.0-rocm", "0.12.3-rocm"],
        "default": "0.12.0",
        "newest": "0.13.0-rocm",
        "newest_needs_cuda": NEEDS_CUDA,
    }

    result = fetch_docker_tags("http://infra:8086", "key", "ollama", {"image_version": "0.12.3-rocm"})

    assert mock_get.call_args.args[0] == "http://infra:8086/admin/services/ollama/docker-tags?current=0.12.3-rocm"
    assert result.newest == "0.13.0-rocm"
    assert result.needs_cuda == NEEDS_CUDA


def test_docker_tags_newest_comes_from_infra_for_tags_the_cli_cannot_parse() -> None:
    tags = DockerTags(
        image="x",
        tags=["server-vulkan-b11580", "server-vulkan-b10902"],
        installed="server-vulkan-b5966",
        infra_newest="server-vulkan-b11580",
        infra_picks_newest=True,
    )

    assert tags.newest == "server-vulkan-b11580"


def test_docker_tags_without_a_newest_from_infra_has_none_even_if_the_cli_could_guess() -> None:
    tags = DockerTags(image="x", tags=["v2.4.0"], infra_newest=None, infra_picks_newest=True)

    assert tags.newest is None


def test_docker_tags_cuda_warning_names_the_tag_and_both_cuda_versions() -> None:
    tags = DockerTags(image="x", tags=["v1.0.0"], needs_cuda=NEEDS_CUDA)

    assert tags.cuda_warning == (
        "v0.5.21-cu130 is newer but needs CUDA 13.0, and the NVIDIA driver on this host supports CUDA 12.9. "
        "Update the NVIDIA driver to be able to use it."
    )
    assert DockerTags(image="x", tags=["v1.0.0"]).cuda_warning is None


@mock.patch("deepfellow.infra.utils.update_spec.fetch_docker_tags")
def test_resolve_image_version_warns_when_a_newer_version_needs_a_newer_cuda(mock_tags: Mock, mock_echo: Mock) -> None:
    mock_tags.return_value = DockerTags(
        image="hub/sglang",
        tags=["v0.5.21-cu130", "v0.5.19-cu129"],
        installed="v0.5.19-cu129",
        infra_newest="v0.5.19-cu129",
        infra_picks_newest=True,
        needs_cuda=NEEDS_CUDA,
    )

    result = resolve_image_version(None, False, "s", "k", "sglang", {"image_version": "v0.5.19-cu129"}, FIELDS)

    assert result == "v0.5.19-cu129"
    assert mock_echo.warning.call_args == mock.call(mock_tags.return_value.cuda_warning)
