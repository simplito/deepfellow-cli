# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Generators."""

import secrets
import string


def generate_password(length: int = 16) -> str:
    """Generate password."""
    # Define the characters to choose from
    alphabet = string.ascii_letters + string.digits

    # Generate a random password using secrets
    password = "".join(secrets.choice(alphabet) for i in range(length))
    return password  # noqa: RET504
