# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from deepfellow.server.utils.headers import project_headers


def test_project_headers_returns_project_header_only_when_no_organization_given() -> None:
    result = project_headers("project-id")

    assert result == {"OpenAI-Project": "project-id"}


def test_project_headers_includes_organization_header_when_given() -> None:
    result = project_headers("project-id", "org-id")

    assert result == {"OpenAI-Project": "project-id", "OpenAI-Organization": "org-id"}
