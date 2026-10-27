# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

from deepfellow.infra.utils.update_spec import DockerTags
from deepfellow.infra.utils.versions import show_versions


@mock.patch("deepfellow.infra.utils.versions.echo")
@mock.patch(
    "deepfellow.infra.utils.versions.fetch_docker_tags",
    return_value=DockerTags(image="hub/doc-chunker-gpu", tags=["v2.4.0", "v2.3.0-volta", "v2.2.0"], default="v2.4.0"),
)
def test_show_versions_marks_installed_newest_and_default(mock_tags: Mock, mock_echo: Mock) -> None:
    show_versions("http://infra:8086", "key", "custom", {"image_version": "v2.2.0"}, model_id="doc_chunker")

    assert mock_echo.info.call_args == mock.call(
        "image: hub/doc-chunker-gpu\n- v2.4.0 (newest, default)\n- v2.3.0-volta\n- v2.2.0 (installed)"
    )


@mock.patch("deepfellow.infra.utils.update_spec.get")
@mock.patch("deepfellow.infra.utils.update_spec.call_infra")
def test_fetch_docker_tags_filters_by_hardware_and_model(mock_call: Mock, mock_get: Mock) -> None:
    from deepfellow.infra.utils.update_spec import fetch_docker_tags

    mock_call.side_effect = lambda request, *args, **kwargs: request()
    mock_get.return_value = {"image": "hub/x", "tags": ["v1.0.0"], "default": "v1.0.0"}

    result = fetch_docker_tags("http://infra:8086", "key", "custom", {"hardware": "GPU"}, "doc_chunker")

    assert result == DockerTags(image="hub/x", tags=["v1.0.0"], default="v1.0.0")
    # Infra matches the hardware value as the install form sends it ("GPU"); lowercased it returns CPU tags.
    assert (
        mock_get.call_args.args[0]
        == "http://infra:8086/admin/services/custom/docker-tags?hardware=GPU&model_id=doc_chunker"
    )


@mock.patch("deepfellow.infra.utils.versions.echo")
@mock.patch(
    "deepfellow.infra.utils.versions.fetch_docker_tags",
    return_value=DockerTags(
        image="hub/sglang",
        tags=["v0.5.19-cu129"],
        needs_cuda={"tag": "v0.5.21-cu130", "required_cuda": "13.0", "host_cuda": "12.9"},
    ),
)
def test_show_versions_warns_about_a_newer_version_that_needs_a_newer_cuda(mock_tags: Mock, mock_echo: Mock) -> None:
    show_versions("http://infra:8086", "key", "sglang", {"image_version": "v0.5.19-cu129"})

    assert mock_echo.warning.call_args == mock.call(
        "v0.5.21-cu130 is newer but needs CUDA 13.0, and the NVIDIA driver on this host supports CUDA 12.9. "
        "Update the NVIDIA driver to be able to use it."
    )
