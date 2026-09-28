#!/usr/bin/env python3

# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""License header validation script for Python files."""

# ruff: noqa: T201

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

LICENSE_LINE = "# SPDX-License-Identifier: LicenseRef-DeepFellow-Free"
COPYRIGHT_LINE_TEMPLATE = "# SPDX-FileCopyrightText: {year} Simplito sp. z o.o."

LICENSE_HEADER_TEMPLATE = f"{LICENSE_LINE}\n{COPYRIGHT_LINE_TEMPLATE}\n"

LICENSE_LINE_PATTERN = re.compile(rf"^{re.escape(LICENSE_LINE)}[ \t]*$", re.MULTILINE)
COPYRIGHT_LINE_PATTERN = re.compile(r"^# SPDX-FileCopyrightText: (\d{4}) Simplito sp\. z o\.o\.[ \t]*$", re.MULTILINE)

LICENSE_HEADER_PATTERN = re.compile(
    rf"^{re.escape(LICENSE_LINE)}[ \t]*\n"
    r"^# SPDX-FileCopyrightText: (\d{4}) Simplito sp\. z o\.o\.\s*$",
    re.MULTILINE,
)

OLD_LICENSE_HEADER_MARKER_PATTERN = re.compile(r"^# DeepFellow Software Framework\.\s*$", re.MULTILINE)

# Old prose DFFL header, stripped by --fix.
OLD_LICENSE_HEADER_PATTERN = re.compile(
    r"\A(?:"
    r"# DeepFellow Software Framework\.\s*\n"
    r"# Copyright © \d{4} Simplito sp\. z o\.o\.\s*\n"
    r"#\s*\n"
    r"# This file is part of the DeepFellow Software Framework \(https://deepfellow\.ai\)\.\s*\n"
    r"# This software is Licensed under the DeepFellow Free License\.\s*\n"
    r"#\s*\n"
    r"# See the License for the specific language governing permissions and\s*\n"
    r"# limitations under the License\.\s*\n*"
    r")+"
)

DEFAULT_EXCLUDES = frozenset({".git", ".uv-cache"})

app = typer.Typer(add_completion=False)


def get_current_year() -> int:
    """Get the current year."""
    return datetime.now(timezone.utc).year


def get_license_header(year: int | None = None) -> str:
    """Generate license header with the specified or current year."""
    if year is None:
        year = get_current_year()
    return LICENSE_HEADER_TEMPLATE.format(year=year)


def parse_gitignore(path: Path) -> frozenset[str]:
    """Parse .gitignore file and return patterns as a frozenset."""
    gitignore = path / ".gitignore"
    if not gitignore.exists():
        return frozenset()

    patterns = set()
    try:
        for line in gitignore.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Normalize: remove leading/trailing slashes for directory matching
                pattern = line.strip("/")
                if pattern:
                    patterns.add(pattern)
    except OSError:
        return frozenset()

    return frozenset(patterns)


def split_preamble(content: str) -> tuple[str, str]:
    """Split off any leading shebang/encoding lines, returning (preamble, remainder)."""
    lines = content.split("\n")
    start_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#!") or "coding" in stripped[:20]:
            start_idx = i + 1
            if start_idx < len(lines) and not lines[start_idx].strip():
                start_idx += 1
        else:
            break

    return "\n".join(lines[:start_idx]), "\n".join(lines[start_idx:])


def join_preamble(preamble: str, remainder: str) -> str:
    """Reassemble content from a (preamble, remainder) pair produced by split_preamble."""
    if not preamble:
        return remainder
    return f"{preamble}\n{remainder}" if remainder else preamble


def find_license_line(content: str) -> re.Match[str] | None:
    """Find the SPDX-License-Identifier line in the file content, if present."""
    return LICENSE_LINE_PATTERN.search(content)


def find_copyright_line(content: str) -> re.Match[str] | None:
    """Find the SPDX-FileCopyrightText line in the file content, if present."""
    return COPYRIGHT_LINE_PATTERN.search(content)


def extract_header_year(content: str) -> int | None:
    """Extract the year from the license header if present, requiring the two lines adjacent."""
    match = LICENSE_HEADER_PATTERN.search(content)
    return int(match.group(1)) if match else None


def has_stale_old_header(content: str) -> bool:
    """Check whether an old-header comment line remains anywhere in the file."""
    return OLD_LICENSE_HEADER_MARKER_PATTERN.search(content) is not None


def has_duplicate_header(content: str) -> bool:
    """Check whether the license or copyright line appears more than once in the file."""
    return len(LICENSE_LINE_PATTERN.findall(content)) > 1 or len(COPYRIGHT_LINE_PATTERN.findall(content)) > 1


def strip_old_header(content: str) -> str:
    """Remove a leading old-style prose DFFL header (and any accidental repeats of it)."""
    preamble, remainder = split_preamble(content)
    remainder = OLD_LICENSE_HEADER_PATTERN.sub("", remainder, count=1)
    return join_preamble(preamble, remainder)


def write_text(filepath: Path, content: str) -> bool:
    """Write content to filepath, returning False (instead of raising) on an OS-level failure."""
    try:
        filepath.write_text(content, encoding="utf-8")
    except OSError:
        return False
    return True


def insert_header_lines(content: str, header_lines: list[str]) -> str:
    """Insert header_lines after any shebang/encoding preamble, ahead of the rest of the content."""
    lines = content.split("\n")
    preamble_lines = []
    start_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#!") or "coding" in stripped[:20]:
            preamble_lines.append(line)
            start_idx = i + 1
        else:
            break

    rest = "\n".join(lines[start_idx:]).lstrip("\n")
    parts = []

    if preamble_lines:
        parts.append("\n".join(preamble_lines))
        parts.append("")

    parts.append("\n".join(header_lines))

    if rest:
        parts.append("")
        parts.append(rest)

    new_content = "\n".join(parts)
    if not new_content.endswith("\n"):
        new_content += "\n"

    return new_content


def check_file_header(filepath: Path) -> bool:
    """Check if a file contains the required license header.

    Returns:
        True if a well-formed header is present, regardless of the year's value.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    if not content.strip():
        return True

    if has_stale_old_header(content) or has_duplicate_header(content):
        return False

    return extract_header_year(content) is not None


def fix_file_header(filepath: Path) -> bool:
    """Remove a stale DFFL header if present, then add the SPDX header."""
    try:
        original_content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    content = strip_old_header(original_content)

    if has_stale_old_header(content) or has_duplicate_header(content):
        return False

    current_year = get_current_year()

    if not content.strip():
        return write_text(filepath, get_license_header(current_year))

    if LICENSE_HEADER_PATTERN.search(content):
        return True if content == original_content else write_text(filepath, content)

    license_match = find_license_line(content)
    copyright_match = find_copyright_line(content)

    if license_match and not copyright_match:
        pos = license_match.end()
        copyright_line = COPYRIGHT_LINE_TEMPLATE.format(year=current_year)
        new_content = content[:pos] + "\n" + copyright_line + content[pos:]
        return write_text(filepath, new_content)

    if copyright_match and not license_match:
        pos = copyright_match.start()
        new_content = content[:pos] + LICENSE_LINE + "\n" + content[pos:]
        return write_text(filepath, new_content)

    if license_match and copyright_match:
        # Present but not adjacent - ambiguous, don't guess.
        return False

    header_lines = [LICENSE_LINE, COPYRIGHT_LINE_TEMPLATE.format(year=current_year)]
    return write_text(filepath, insert_header_lines(content, header_lines))


def should_exclude(path: Path, excludes: frozenset[str]) -> bool:
    """Check if a path should be excluded from validation."""
    parts = path.parts
    name = path.name

    for pattern in excludes:
        # Exact name match (e.g., __pycache__, .venv)
        if pattern in parts or name == pattern:
            return True
        # Wildcard prefix (e.g., *.egg-info, *.pyc)
        if pattern.startswith("*"):
            suffix = pattern[1:]
            if name.endswith(suffix) or any(p.endswith(suffix) for p in parts):
                return True
        # Wildcard suffix (e.g., test_*)
        if pattern.endswith("*") and name.startswith(pattern[:-1]):
            return True

    return False


def find_python_files(
    paths: list[Path],
    excludes: frozenset[str],
    recursive: bool = True,
) -> list[Path]:
    """Find all Python files in the given paths."""
    python_files = []

    for path in paths:
        if path.is_file():
            if path.suffix == ".py" and not should_exclude(path, excludes):
                python_files.append(path)
        elif path.is_dir():
            glob_func = path.rglob if recursive else path.glob
            for py_file in glob_func("*.py"):
                if not should_exclude(py_file, excludes):
                    python_files.append(py_file)

    return sorted(set(python_files))


def build_excludes(
    paths: list[Path],
    extra_excludes: list[str],
    use_gitignore: bool,
) -> frozenset[str]:
    """Build the set of exclusion patterns from defaults, gitignore, and CLI args."""
    excludes = set(DEFAULT_EXCLUDES)

    if use_gitignore:
        gitignore_dirs = {p if p.is_dir() else p.parent for p in paths}
        for directory in gitignore_dirs:
            excludes.update(parse_gitignore(directory))
        excludes.update(parse_gitignore(Path.cwd()))

    excludes.update(extra_excludes)
    return frozenset(excludes)


def get_files_to_check(
    paths: list[Path],
    files: list[Path] | None,
    excludes: frozenset[str],
    recursive: bool,
) -> list[Path]:
    """Determine which files to check based on arguments."""
    if files:
        return [f for f in files if f.suffix == ".py" and not should_exclude(f, excludes)]
    return find_python_files(paths, excludes, recursive=recursive)


def classify_files(
    files_to_check: list[Path],
) -> list[Path]:
    """Return the files missing a valid license header."""
    return [f for f in files_to_check if not check_file_header(f)]


def apply_fixes(files: list[Path]) -> bool:
    """Apply fixes to all files, print results, and report whether every fix succeeded."""
    all_fixed = True
    for f in files:
        if fix_file_header(f):
            print(f"Fixed: {f}")
        else:
            print(f"Error: {f}")
            all_fixed = False
    return all_fixed


def report_issues(
    missing_header: list[Path],
    verbose: bool,
) -> None:
    """Report validation issues to stdout."""
    if not missing_header:
        return

    if verbose:
        for f in missing_header:
            print(f)
    else:
        print(f"Missing license header in {len(missing_header)} files")
        print("Use --verbose to see individual files")
        print("Use --fix to automatically repair")


@app.command()
def main(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(help="Paths to check"),
    ] = None,
    files: Annotated[
        list[Path] | None,
        typer.Option("--files", help="Specific files to check"),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Additional patterns to exclude"),
    ] = None,
    no_recursive: Annotated[
        bool,
        typer.Option("--no-recursive", help="Do not search subdirectories"),
    ] = False,
    no_gitignore: Annotated[
        bool,
        typer.Option("--no-gitignore", help="Do not read patterns from .gitignore"),
    ] = False,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Add missing license headers"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show individual file paths"),
    ] = False,
) -> None:
    """Validate license headers in Python files."""
    paths = paths or [Path.cwd()]
    exclude = exclude or []

    excludes = build_excludes(paths, exclude, use_gitignore=not no_gitignore)
    files_to_check = get_files_to_check(paths, files, excludes, recursive=not no_recursive)
    missing_header = classify_files(files_to_check)

    if fix and missing_header:
        if apply_fixes(missing_header):
            raise typer.Exit(0)
        raise typer.Exit(1)

    report_issues(missing_header, verbose)

    if missing_header:
        raise typer.Exit(1)

    print("All Python files have valid license headers")


if __name__ == "__main__":
    app()
