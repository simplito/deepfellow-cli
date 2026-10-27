# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Tests for check_license_header.py module."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scripts.check_license_header import (
    app,
    apply_fixes,
    check_file_header,
    extract_header_year,
    find_python_files,
    fix_file_header,
    get_current_year,
    get_license_header,
    parse_gitignore,
    should_exclude,
)

OLD_DFFL_HEADER = (
    "# DeepFellow Software Framework.\n"
    "# Copyright © 2020 Simplito sp. z o.o.\n"
    "#\n"
    "# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).\n"
    "# This software is Licensed under the DeepFellow Free License.\n"
    "#\n"
    "# See the License for the specific language governing permissions and\n"
    "# limitations under the License.\n"
)

# Missing the blank "#" separator line - close to OLD_DFFL_HEADER but not an exact match, so
# OLD_LICENSE_HEADER_PATTERN can't strip it.
MALFORMED_OLD_DFFL_HEADER = (
    "# DeepFellow Software Framework.\n"
    "# Copyright © 2020 Simplito sp. z o.o.\n"
    "# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).\n"
    "# This software is Licensed under the DeepFellow Free License.\n"
    "#\n"
    "# See the License for the specific language governing permissions and\n"
    "# limitations under the License.\n"
)


@pytest.fixture
def current_year() -> int:
    """Current year for tests."""
    return get_current_year()


@pytest.fixture
def license_header(current_year: int) -> str:
    """License header with current year."""
    return get_license_header(current_year)


@pytest.fixture
def valid_content(license_header: str) -> str:
    """Valid Python file content with license header."""
    return f"{license_header}\n\nimport sys\n"


@pytest.fixture
def valid_with_shebang(license_header: str) -> str:
    """Valid Python file with shebang and license header."""
    return f"#!/usr/bin/env python3\n\n{license_header}\n\nimport sys\n"


@pytest.fixture
def valid_with_encoding(license_header: str) -> str:
    """Valid Python file with encoding declaration and license header."""
    return f"# -*- coding: utf-8 -*-\n\n{license_header}\n\nimport sys\n"


@pytest.fixture
def valid_with_both(license_header: str) -> str:
    """Valid Python file with shebang, encoding, and license header."""
    return f"#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\n{license_header}\n\nimport sys\n"


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Sample project structure for testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main")
    (tmp_path / "src" / "utils.py").write_text("# utils")
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "main.cpython-311.pyc").write_text("")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("# test")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("# venv")
    return tmp_path


# --- get_license_header ---


def test_get_license_header_uses_current_year(current_year: int):
    header = get_license_header()
    assert "SPDX-License-Identifier: LicenseRef-DeepFellow-Free" in header
    assert f"SPDX-FileCopyrightText: {current_year}" in header


def test_get_license_header_with_specific_year():
    header = get_license_header(2020)
    assert "SPDX-FileCopyrightText: 2020" in header


# --- extract_header_year ---


def test_extract_header_year_finds_year(current_year: int, license_header: str):
    content = f"{license_header}\nimport sys\n"
    assert extract_header_year(content) == current_year


def test_extract_header_year_finds_old_year():
    header = get_license_header(2020)
    content = f"{header}\nimport sys\n"
    assert extract_header_year(content) == 2020


def test_extract_header_year_no_header():
    content = "import sys\n"
    assert extract_header_year(content) is None


def test_extract_header_year_with_shebang(current_year: int, license_header: str):
    content = f"#!/usr/bin/env python3\n\n{license_header}\nimport sys\n"
    assert extract_header_year(content) == current_year


def test_extract_header_year_tolerates_trailing_whitespace_on_license_line(current_year: int):
    """Trailing whitespace on the license line alone must not make an otherwise-valid header
    unrecognizable (and thus unfixable)."""
    content = (
        "# SPDX-License-Identifier: LicenseRef-DeepFellow-Free  \n"
        f"# SPDX-FileCopyrightText: {current_year} Simplito sp. z o.o.\nimport sys\n"
    )
    assert extract_header_year(content) == current_year


def test_extract_header_year_rejects_blank_line_between_lines():
    """A blank line between the two lines means they aren't a genuine adjacent header."""
    content = (
        "# SPDX-License-Identifier: LicenseRef-DeepFellow-Free\n\n"
        "# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.\nimport sys\n"
    )
    assert extract_header_year(content) is None


# --- parse_gitignore ---


def test_parse_gitignore_parses_patterns(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("__pycache__\n.venv\n*.pyc\nbuild/\n")

    patterns = parse_gitignore(tmp_path)

    assert patterns == frozenset({"__pycache__", ".venv", "*.pyc", "build"})


def test_parse_gitignore_ignores_comments(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# This is a comment\n__pycache__\n# Another comment\n.venv\n")

    patterns = parse_gitignore(tmp_path)

    assert patterns == frozenset({"__pycache__", ".venv"})


def test_parse_gitignore_ignores_empty_lines(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("__pycache__\n\n\n.venv\n")

    patterns = parse_gitignore(tmp_path)

    assert patterns == frozenset({"__pycache__", ".venv"})


def test_parse_gitignore_strips_slashes(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("/build/\n/dist\nvenv/\n")

    patterns = parse_gitignore(tmp_path)

    assert patterns == frozenset({"build", "dist", "venv"})


def test_parse_gitignore_returns_empty_if_no_gitignore(tmp_path: Path):
    assert parse_gitignore(tmp_path) == frozenset()


def test_parse_gitignore_handles_complex_gitignore(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("""
# Python
__pycache__/
*.py[cod]
*.egg-info/

# Environments
.venv/
venv/

# IDE
.idea/
.vscode/
""")

    patterns = parse_gitignore(tmp_path)

    assert "__pycache__" in patterns
    assert "*.py[cod]" in patterns
    assert "*.egg-info" in patterns
    assert ".venv" in patterns


# --- should_exclude ---


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        (Path("src/__pycache__/module.pyc"), "__pycache__", True),
        (Path("project/.venv/lib/site.py"), ".venv", True),
        (Path("pkg.egg-info/PKG-INFO"), "*.egg-info", True),
        (Path("src/mymodule/main.py"), "__pycache__", False),
        (Path("tests/test_main.py"), ".venv", False),
        (Path("src/cache.pyc"), "*.pyc", True),
        (Path("tests/test_utils.py"), "test_*", True),
    ],
)
def test_should_exclude_patterns(path: Path, pattern: str, expected: bool):
    assert should_exclude(path, frozenset({pattern})) is expected


def test_should_exclude_multiple_excludes():
    path = Path("src/__pycache__/cached.pyc")
    assert should_exclude(path, frozenset({"__pycache__", ".venv"})) is True


def test_should_exclude_no_excludes():
    assert should_exclude(Path("src/main.py"), frozenset()) is False


# --- check_file_header ---


def test_check_file_header_valid(tmp_path: Path, valid_content: str):
    file = tmp_path / "valid.py"
    file.write_text(valid_content)
    assert check_file_header(file) is True


def test_check_file_header_valid_with_shebang(tmp_path: Path, valid_with_shebang: str):
    file = tmp_path / "with_shebang.py"
    file.write_text(valid_with_shebang)
    assert check_file_header(file) is True


def test_check_file_header_valid_with_encoding(tmp_path: Path, valid_with_encoding: str):
    file = tmp_path / "with_encoding.py"
    file.write_text(valid_with_encoding)
    assert check_file_header(file) is True


def test_check_file_header_valid_with_shebang_and_encoding(tmp_path: Path, valid_with_both: str):
    file = tmp_path / "with_both.py"
    file.write_text(valid_with_both)
    assert check_file_header(file) is True


def test_check_file_header_invalid_no_header(tmp_path: Path):
    file = tmp_path / "no_header.py"
    file.write_text("import sys\n")
    assert check_file_header(file) is False


def test_check_file_header_invalid_wrong_header(tmp_path: Path):
    file = tmp_path / "wrong_header.py"
    file.write_text("# MIT License\nimport sys\n")
    assert check_file_header(file) is False


def test_check_file_header_valid_old_year(tmp_path: Path):
    """A header with an outdated (non-current) year is still valid - the year need not be current."""
    old_header = get_license_header(2020)
    file = tmp_path / "old_year.py"
    file.write_text(f"{old_header}\nimport sys\n")
    assert check_file_header(file) is True


def test_check_file_header_invalid_old_dffl_header(tmp_path: Path):
    """A file still carrying the old prose DFFL header is not considered valid."""
    file = tmp_path / "old_dffl.py"
    file.write_text(f"{OLD_DFFL_HEADER}\nimport sys\n")
    assert check_file_header(file) is False


def test_check_file_header_invalid_malformed_old_dffl_header(tmp_path: Path):
    """A file whose old header deviates from the exact expected shape is still not valid."""
    file = tmp_path / "malformed_old_dffl.py"
    file.write_text(f"{MALFORMED_OLD_DFFL_HEADER}\nimport sys\n")
    assert check_file_header(file) is False


def test_check_file_header_license_line_only(tmp_path: Path):
    """A file with the license line but no copyright line is not valid."""
    file = tmp_path / "license_only.py"
    file.write_text("# SPDX-License-Identifier: LicenseRef-DeepFellow-Free\nimport sys\n")
    assert check_file_header(file) is False


def test_check_file_header_copyright_line_only(tmp_path: Path, current_year: int):
    """A file with the copyright line but no license line is not valid."""
    file = tmp_path / "copyright_only.py"
    file.write_text(f"# SPDX-FileCopyrightText: {current_year} Simplito sp. z o.o.\nimport sys\n")
    assert check_file_header(file) is False


def test_check_file_header_invalid_duplicate_header(tmp_path: Path, valid_content: str):
    """Two back-to-back complete headers (e.g. left behind by a botched fix) must not be valid."""
    file = tmp_path / "duplicate.py"
    file.write_text(f"{valid_content}{valid_content}")
    assert check_file_header(file) is False


def test_check_file_header_invalid_reversed_line_order(tmp_path: Path, current_year: int):
    """The copyright line appearing before the license line is not a valid adjacent header."""
    file = tmp_path / "reversed.py"
    file.write_text(
        f"# SPDX-FileCopyrightText: {current_year} Simplito sp. z o.o.\n"
        "# SPDX-License-Identifier: LicenseRef-DeepFellow-Free\nimport sys\n"
    )
    assert check_file_header(file) is False


def test_check_file_header_empty_file(tmp_path: Path):
    file = tmp_path / "empty.py"
    file.write_text("")
    assert check_file_header(file) is True


def test_check_file_header_whitespace_only(tmp_path: Path):
    file = tmp_path / "whitespace.py"
    file.write_text("   \n\n")
    assert check_file_header(file) is True


def test_check_file_header_nonexistent_file(tmp_path: Path):
    assert check_file_header(tmp_path / "nonexistent.py") is False


# --- fix_file_header ---


def test_fix_file_header_without_header(tmp_path: Path, current_year: int):
    file = tmp_path / "no_header.py"
    file.write_text("import sys\n\ndef main():\n    pass\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert f"SPDX-FileCopyrightText: {current_year}" in content
    assert "import sys" in content


def test_fix_file_header_with_shebang(tmp_path: Path, current_year: int):
    file = tmp_path / "with_shebang.py"
    file.write_text("#!/usr/bin/env python3\n\nimport sys\n")

    fix_file_header(file)

    assert check_file_header(file) is True
    content = file.read_text()
    assert content.startswith("#!/usr/bin/env python3\n")
    assert f"SPDX-FileCopyrightText: {current_year}" in content
    assert "import sys" in content
    # No spurious extra blank line between the shebang and the header.
    assert content == (
        "#!/usr/bin/env python3\n\n# SPDX-License-Identifier: LicenseRef-DeepFellow-Free\n"
        f"# SPDX-FileCopyrightText: {current_year} Simplito sp. z o.o.\n\nimport sys\n"
    )


def test_fix_file_header_with_encoding(tmp_path: Path, current_year: int):
    file = tmp_path / "with_encoding.py"
    file.write_text("# -*- coding: utf-8 -*-\n\nimport sys\n")

    fix_file_header(file)

    assert check_file_header(file) is True
    content = file.read_text()
    assert content.startswith("# -*- coding: utf-8 -*-\n")
    assert f"SPDX-FileCopyrightText: {current_year}" in content


def test_fix_file_header_with_shebang_and_encoding(tmp_path: Path, current_year: int):
    file = tmp_path / "with_both.py"
    file.write_text("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\nimport sys\n")

    fix_file_header(file)

    assert check_file_header(file) is True
    content = file.read_text()
    assert content.startswith("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n")
    assert f"SPDX-FileCopyrightText: {current_year}" in content


def test_fix_file_header_empty_file(tmp_path: Path, current_year: int):
    file = tmp_path / "empty.py"
    file.write_text("")

    fix_file_header(file)

    content = file.read_text()
    assert f"SPDX-FileCopyrightText: {current_year}" in content


def test_fix_file_header_leaves_existing_year_untouched(tmp_path: Path):
    """Fix should leave an already-valid header's year alone, even if it's not the current year."""
    old_header = get_license_header(2020)
    file = tmp_path / "old_year.py"
    file.write_text(f"{old_header}\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert "SPDX-FileCopyrightText: 2020" in content
    assert "import sys" in content


def test_fix_file_header_migrates_old_dffl_header(tmp_path: Path, current_year: int):
    """Fix should strip the old prose DFFL header and add the SPDX header instead."""
    file = tmp_path / "old_dffl.py"
    file.write_text(f"{OLD_DFFL_HEADER}\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert "SPDX-License-Identifier: LicenseRef-DeepFellow-Free" in content
    assert f"SPDX-FileCopyrightText: {current_year}" in content
    assert "DeepFellow Software Framework" not in content
    assert "import sys" in content


def test_fix_file_header_migrates_old_dffl_header_with_shebang(tmp_path: Path, current_year: int):
    """Fix should migrate the old header even when a shebang precedes it."""
    file = tmp_path / "old_dffl_shebang.py"
    file.write_text(f"#!/usr/bin/env python3\n\n{OLD_DFFL_HEADER}\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert content.startswith("#!/usr/bin/env python3\n")
    assert "SPDX-License-Identifier: LicenseRef-DeepFellow-Free" in content
    assert f"SPDX-FileCopyrightText: {current_year}" in content
    assert "DeepFellow Software Framework" not in content
    assert "import sys" in content


def test_fix_file_header_migrates_doubled_old_dffl_header(tmp_path: Path, current_year: int):
    """A file carrying two back-to-back copies of the old header (a real repo bug found in
    server/__init__.py) should have both copies stripped, not just the first."""
    file = tmp_path / "doubled_old_dffl.py"
    file.write_text(f"{OLD_DFFL_HEADER}\n{OLD_DFFL_HEADER}\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert content.count("SPDX-License-Identifier") == 1
    assert f"SPDX-FileCopyrightText: {current_year}" in content
    assert "DeepFellow Software Framework" not in content
    assert "import sys" in content


def test_fix_file_header_strips_old_header_preceding_already_valid_new_header(tmp_path: Path, current_year: int):
    """A file carrying a stale old header ahead of an already-valid SPDX header must have the old
    one stripped and the strip actually persisted to disk, not just reported as fixed - the file
    is not yet valid on disk until the old header is gone."""
    valid_header = get_license_header(current_year)
    file = tmp_path / "old_dffl_plus_valid.py"
    file.write_text(f"{OLD_DFFL_HEADER}\n{valid_header}\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert "DeepFellow Software Framework" not in content
    assert content.count("SPDX-License-Identifier") == 1
    assert "import sys" in content


def test_fix_file_header_malformed_old_dffl_header_bails_out(tmp_path: Path):
    """Fix should refuse to touch a file whose old header doesn't match the expected shape,
    rather than risk stacking a new header on top of the stale text."""
    file = tmp_path / "malformed_old_dffl.py"
    original = f"{MALFORMED_OLD_DFFL_HEADER}\nimport sys\n"
    file.write_text(original)

    result = fix_file_header(file)

    assert result is False
    assert file.read_text() == original


def test_fix_file_header_stale_old_header_past_many_leading_lines_bails_out(tmp_path: Path):
    """A stale old header that isn't immediately after the preamble (e.g. buried under a lot of
    ordinary leading content) can't be safely auto-migrated, but must still be detected as
    invalid - never silently accepted as valid - regardless of how far from the top it sits."""
    leading_comments = "".join(f"# leading comment {i}\n" for i in range(30))
    file = tmp_path / "old_dffl_deep.py"
    original = f"{leading_comments}{OLD_DFFL_HEADER}\nimport sys\n"
    file.write_text(original)

    result = fix_file_header(file)

    assert result is False
    assert file.read_text() == original
    assert check_file_header(file) is False


def test_fix_file_header_duplicate_header_bails_out(tmp_path: Path, valid_content: str):
    """Fix should refuse to touch a file that already has two complete headers, rather than
    guess which one is authoritative."""
    file = tmp_path / "duplicate.py"
    original = f"{valid_content}{valid_content}"
    file.write_text(original)

    result = fix_file_header(file)

    assert result is False
    assert file.read_text() == original


def test_fix_file_header_reversed_line_order_bails_out(tmp_path: Path, current_year: int):
    """Fix must not report success for a file where both lines exist but aren't the adjacent
    pair check_file_header requires - claiming success there would never converge."""
    file = tmp_path / "reversed.py"
    original = (
        f"# SPDX-FileCopyrightText: {current_year} Simplito sp. z o.o.\n"
        "# SPDX-License-Identifier: LicenseRef-DeepFellow-Free\nimport sys\n"
    )
    file.write_text(original)

    result = fix_file_header(file)

    assert result is False
    assert file.read_text() == original
    assert check_file_header(file) is False


def test_fix_file_header_adds_missing_copyright_line(tmp_path: Path, current_year: int):
    """A file with only the license line should get the copyright line added, not a whole
    second header."""
    file = tmp_path / "license_only.py"
    file.write_text("# SPDX-License-Identifier: LicenseRef-DeepFellow-Free\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert content.count("SPDX-License-Identifier") == 1
    assert f"SPDX-FileCopyrightText: {current_year}" in content
    assert "import sys" in content


def test_fix_file_header_adds_missing_copyright_line_with_blank_line_after(tmp_path: Path, current_year: int):
    """A blank line between the license line and the code must not make the inserted copyright
    line land after that blank line instead of directly beneath the license line."""
    file = tmp_path / "license_only_blank.py"
    file.write_text("# SPDX-License-Identifier: LicenseRef-DeepFellow-Free\n\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert content.count("SPDX-License-Identifier") == 1
    assert f"SPDX-FileCopyrightText: {current_year}" in content
    assert "import sys" in content


def test_fix_file_header_adds_missing_license_line(tmp_path: Path, current_year: int):
    """A file with only the copyright line should get the license line added, not a whole
    second header."""
    file = tmp_path / "copyright_only.py"
    file.write_text(f"# SPDX-FileCopyrightText: {current_year} Simplito sp. z o.o.\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert content.count("SPDX-FileCopyrightText") == 1
    assert "import sys" in content


def test_fix_file_header_adds_missing_license_line_keeps_existing_year(tmp_path: Path):
    """A copyright-only file with an old year should just gain the missing license line - the
    existing year is left untouched, since check_file_header no longer requires it to be current."""
    file = tmp_path / "copyright_only_stale.py"
    file.write_text("# SPDX-FileCopyrightText: 2020 Simplito sp. z o.o.\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    assert check_file_header(file) is True
    content = file.read_text()
    assert content.count("SPDX-FileCopyrightText") == 1
    assert "SPDX-FileCopyrightText: 2020" in content
    assert "import sys" in content


def test_fix_file_header_ignores_quoted_lookalike_lines(tmp_path: Path):
    """A quoted copy of the SPDX lines elsewhere in the file (e.g. in a string literal) must not
    be corrupted by a fix that targets the real header via position, not substring matching."""
    file = tmp_path / "quoted_lookalike.py"
    quoted = 'TEMPLATE = "# SPDX-License-Identifier: LicenseRef-DeepFellow-Free"\n'
    file.write_text(f"{quoted}# SPDX-FileCopyrightText: 2020 Simplito sp. z o.o.\nimport sys\n")

    result = fix_file_header(file)

    assert result is True
    content = file.read_text()
    assert quoted in content
    assert "# SPDX-FileCopyrightText: 2020 Simplito sp. z o.o." in content


def test_fix_file_header_returns_false_on_write_failure(tmp_path: Path):
    """A write failure should be reported as False, not raise."""
    file = tmp_path / "no_header.py"
    file.write_text("import sys\n")

    with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
        assert fix_file_header(file) is False


def test_fix_file_header_preserves_code(tmp_path: Path):
    file = tmp_path / "code.py"
    file.write_text("import sys\n\ndef main():\n    print('hello')\n")

    fix_file_header(file)

    content = file.read_text()
    assert "import sys" in content
    assert "def main():" in content
    assert "print('hello')" in content


def test_fix_file_header_nonexistent_file(tmp_path: Path):
    assert fix_file_header(tmp_path / "nonexistent.py") is False


def test_fix_file_header_idempotent(tmp_path: Path, valid_content: str, current_year: int):
    file = tmp_path / "already_valid.py"
    file.write_text(valid_content)

    assert check_file_header(file) is True

    fix_file_header(file)

    assert check_file_header(file) is True
    assert f"SPDX-FileCopyrightText: {current_year}" in file.read_text()


def test_fix_file_header_already_valid_header_is_exact_noop(tmp_path: Path, valid_content: str):
    """Fix must report success and leave an already-valid file byte-for-byte untouched, rather
    than bailing out with False just because both SPDX lines are already present."""
    file = tmp_path / "already_valid.py"
    file.write_text(valid_content)

    result = fix_file_header(file)

    assert result is True
    assert file.read_text() == valid_content


def test_fix_file_header_already_valid_header_never_writes(tmp_path: Path, valid_content: str):
    """The already-valid no-op path must be a true no-op - it must not even attempt a write,
    not just happen to write back identical bytes."""
    file = tmp_path / "already_valid.py"
    file.write_text(valid_content)

    with patch("pathlib.Path.write_text") as mock_write_text:
        result = fix_file_header(file)

    assert result is True
    mock_write_text.assert_not_called()


def test_fix_file_header_returns_false_on_write_failure_after_stripping_old_header(tmp_path: Path, current_year: int):
    """A write failure while persisting the stripped-old-header result must be reported as False,
    the same as any other write-failure path in fix_file_header."""
    valid_header = get_license_header(current_year)
    file = tmp_path / "old_dffl_plus_valid.py"
    file.write_text(f"{OLD_DFFL_HEADER}\n{valid_header}\nimport sys\n")

    with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
        assert fix_file_header(file) is False


# --- apply_fixes ---


def test_apply_fixes_returns_true_when_all_succeed(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file = tmp_path / "no_header.py"
    file.write_text("import sys\n")

    result = apply_fixes([file])

    assert result is True
    assert f"Fixed: {file}" in capsys.readouterr().out


def test_apply_fixes_returns_false_when_any_bail_out(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    good_file = tmp_path / "no_header.py"
    good_file.write_text("import sys\n")
    bad_file = tmp_path / "malformed_old_dffl.py"
    bad_file.write_text(f"{MALFORMED_OLD_DFFL_HEADER}\nimport sys\n")

    result = apply_fixes([good_file, bad_file])

    assert result is False
    out = capsys.readouterr().out
    assert f"Fixed: {good_file}" in out
    assert f"Error: {bad_file}" in out


# --- main (--fix exit codes) ---


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_main_fix_exits_zero_when_all_fixes_succeed(runner: CliRunner, tmp_path: Path):
    file = tmp_path / "no_header.py"
    file.write_text("import sys\n")

    result = runner.invoke(app, [str(tmp_path), "--fix", "--no-gitignore"])

    assert result.exit_code == 0
    assert check_file_header(file) is True


def test_main_fix_exits_one_when_a_fix_bails_out(runner: CliRunner, tmp_path: Path):
    bad_file = tmp_path / "malformed_old_dffl.py"
    bad_file.write_text(f"{MALFORMED_OLD_DFFL_HEADER}\nimport sys\n")

    result = runner.invoke(app, [str(tmp_path), "--fix", "--no-gitignore"])

    assert result.exit_code == 1


# --- find_python_files ---


def test_find_python_files_finds_all(project_dir: Path):
    excludes = frozenset({"__pycache__", ".venv"})
    files = find_python_files([project_dir], excludes)
    assert {f.name for f in files} == {"main.py", "utils.py", "test_main.py"}


def test_find_python_files_excludes_pycache(project_dir: Path):
    excludes = frozenset({"__pycache__"})
    files = find_python_files([project_dir], excludes)
    assert not any("__pycache__" in str(f) for f in files)


def test_find_python_files_excludes_venv(project_dir: Path):
    excludes = frozenset({".venv"})
    files = find_python_files([project_dir], excludes)
    assert not any(".venv" in str(f) for f in files)


def test_find_python_files_non_recursive(project_dir: Path):
    (project_dir / "root.py").write_text("# root")
    files = find_python_files([project_dir], frozenset(), recursive=False)
    assert len(files) == 1
    assert files[0].name == "root.py"


def test_find_python_files_specific_file(project_dir: Path):
    target = project_dir / "src" / "main.py"
    files = find_python_files([target], frozenset())
    assert files == [target]


def test_find_python_files_empty_directory(tmp_path: Path):
    assert find_python_files([tmp_path], frozenset()) == []


def test_find_python_files_respects_gitignore(project_dir: Path):
    gitignore = project_dir / ".gitignore"
    gitignore.write_text("__pycache__\n.venv\n")

    excludes = parse_gitignore(project_dir)
    files = find_python_files([project_dir], excludes)

    assert {f.name for f in files} == {"main.py", "utils.py", "test_main.py"}


# --- Year validation edge cases ---


def test_check_file_header_valid_regardless_of_current_year(tmp_path: Path):
    """Test that the check's validity doesn't depend on get_current_year at all."""
    header_2024 = get_license_header(2024)
    file = tmp_path / "test.py"
    file.write_text(f"{header_2024}\nimport sys\n")

    with patch("scripts.check_license_header.get_current_year", return_value=2024):
        assert check_file_header(file) is True
        assert extract_header_year(file.read_text()) == 2024

    # Same result without the mock, whatever the real current year is - the header's year is
    # never compared against it.
    assert check_file_header(file) is True
    assert extract_header_year(file.read_text()) == 2024


def test_fix_file_header_ignores_mocked_current_year_for_existing_header(tmp_path: Path):
    """An already-valid header's year must stay put regardless of what get_current_year returns -
    fix_file_header only consults the current year for headers it's newly writing."""
    header_2020 = get_license_header(2020)
    file = tmp_path / "old.py"
    file.write_text(f"{header_2020}\nimport sys\n")

    with patch("scripts.check_license_header.get_current_year", return_value=2030):
        fix_file_header(file)
        content = file.read_text()
        assert "SPDX-FileCopyrightText: 2020" in content
        assert "SPDX-FileCopyrightText: 2030" not in content
