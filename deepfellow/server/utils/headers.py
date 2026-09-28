# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Shared header helpers for project-scoped server API calls."""


def project_headers(project_id: str, organization_id: str | None = None) -> dict[str, str]:
    """Return the headers required to scope a request to a project (and optionally an organization)."""
    headers = {"OpenAI-Project": project_id}
    if organization_id is not None:
        headers["OpenAI-Organization"] = organization_id
    return headers
