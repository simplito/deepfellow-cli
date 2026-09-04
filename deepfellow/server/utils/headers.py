# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared header helpers for project-scoped server API calls."""


def project_headers(project_id: str, organization_id: str | None = None) -> dict[str, str]:
    """Return the headers required to scope a request to a project (and optionally an organization)."""
    headers = {"OpenAI-Project": project_id}
    if organization_id is not None:
        headers["OpenAI-Organization"] = organization_id
    return headers
