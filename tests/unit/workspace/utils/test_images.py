# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.workspace.utils.images import choose_mongo_image, image_tag, image_version


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("mongo:8.2.12@sha256:abc", "8.2.12"),
        ("hub.simplito.com/deepfellow/deepfellow-workspace:v0.7.1", "v0.7.1"),
        ("registry:5000/df/workspace", None),
        ("mongo@sha256:abc", None),
    ],
)
def test_image_tag_ignores_digest_and_registry_port(image: str, expected: str | None):
    result = image_tag(image)

    assert result == expected


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("mongo:8.2.12@sha256:abc", (8, 2, 12)),
        ("hub.simplito.com/deepfellow/deepfellow-workspace:v0.7.1", (0, 7, 1)),
        ("mongo:latest", None),
        ("mongo", None),
    ],
)
def test_image_version_parses_tag(image: str, expected: tuple[int, ...] | None):
    result = image_version(image)

    assert result == expected


@mock.patch("deepfellow.workspace.utils.images.echo")
def test_choose_mongo_image_same_major_takes_new_without_question(mock_echo: Mock):
    result = choose_mongo_image("mongo:8.2.12@sha256:a", "mongo:8.2.14@sha256:b")

    assert result == "mongo:8.2.14@sha256:b"
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.workspace.utils.images.echo")
def test_choose_mongo_image_major_change_declined_keeps_old(mock_echo: Mock):
    mock_echo.confirm.return_value = False

    result = choose_mongo_image("mongo:8.2.12", "mongo:9.0.1")

    assert result == "mongo:8.2.12"
    assert "back up" in str(mock_echo.warning.call_args.args[0])


@mock.patch("deepfellow.workspace.utils.images.echo")
def test_choose_mongo_image_major_change_accepted_takes_new(mock_echo: Mock):
    mock_echo.confirm.return_value = True

    result = choose_mongo_image("mongo:8.2.12", "mongo:9.0.1")

    assert result == "mongo:9.0.1"


@mock.patch("deepfellow.workspace.utils.images.echo")
def test_choose_mongo_image_unreadable_tag_asks(mock_echo: Mock):
    mock_echo.confirm.return_value = False

    result = choose_mongo_image("mongo:latest", "mongo:8.2.12")

    assert result == "mongo:latest"
    assert mock_echo.confirm.call_count == 1


@mock.patch("deepfellow.workspace.utils.images.echo")
def test_choose_mongo_image_asks_despite_yes(mock_echo: Mock):
    mock_echo.confirm.return_value = False

    choose_mongo_image("mongo:8.2.12", "mongo:9.0.1")

    assert mock_echo.confirm.call_args == mock.call(
        "Change the Mongo image to mongo:9.0.1?", default=False, ignore_yes=True
    )


@mock.patch("deepfellow.workspace.utils.images.echo")
def test_choose_mongo_image_same_image_asks_nothing(mock_echo: Mock):
    result = choose_mongo_image("mongo:latest", "mongo:latest")

    assert result == "mongo:latest"
    assert mock_echo.confirm.call_count == 0
