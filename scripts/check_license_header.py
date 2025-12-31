#!/usr/bin/env python3

# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""License header validation script for Python files."""

from pathlib import Path
from typing import Annotated

import typer

LICENSE_HEADER = """\
# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.
"""

DEFAULT_EXCLUDES = frozenset({".git", ".uv-cache"})

app = typer.Typer(add_completion=False)


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


def normalize_header(text: str) -> str:
    """Normalize header text by stripping trailing whitespace."""
    return "\n".join(line.rstrip() for line in text.strip().split("\n"))


def extract_content_after_preamble(content: str) -> str:
    """Extract file content after optional shebang/encoding lines."""
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

    return "\n".join(lines[start_idx:])


def check_file_header(filepath: Path) -> bool:
    """Check if a file contains the required license header."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    if not content.strip():
        return True

    remaining = extract_content_after_preamble(content)
    expected = normalize_header(LICENSE_HEADER)
    actual_start = normalize_header(remaining[: len(LICENSE_HEADER) + 100])

    return actual_start.startswith(expected)


def fix_file_header(filepath: Path) -> bool:
    """Add license header to a file that's missing it."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    if not content.strip():
        filepath.write_text(LICENSE_HEADER, encoding="utf-8")
        return True

    lines = content.split("\n")
    preamble_lines = []
    start_idx = 0

    # Extract shebang and encoding lines
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#!") or "coding" in stripped[:20]:
            preamble_lines.append(line)
            start_idx = i + 1
        else:
            break

    # Build new content
    rest = "\n".join(lines[start_idx:]).lstrip("\n")
    parts = []

    if preamble_lines:
        parts.append("\n".join(preamble_lines))
        parts.append("")

    parts.append(LICENSE_HEADER.rstrip())

    if rest:
        parts.append("")
        parts.append(rest)

    new_content = "\n".join(parts)
    if not new_content.endswith("\n"):
        new_content += "\n"

    filepath.write_text(new_content, encoding="utf-8")
    return True


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
        typer.Option("--fix", help="Add missing license headers to files"),
    ] = False,
) -> None:
    """Validate license headers in Python files."""
    paths = paths or [Path.cwd()]
    exclude = exclude or []

    excludes = build_excludes(paths, exclude, use_gitignore=not no_gitignore)
    files_to_check = get_files_to_check(paths, files, excludes, recursive=not no_recursive)

    failed = [f for f in files_to_check if not check_file_header(f)]

    if fix and failed:
        for f in failed:
            if fix_file_header(f):
                print(f"Fixed: {f}")
            else:
                print(f"Error: {f}")
        raise typer.Exit(0)

    for f in failed:
        print(f)

    if failed:
        raise typer.Exit(1)

    print("All Python files have the license")


if __name__ == "__main__":
    app()
