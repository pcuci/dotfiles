#!/usr/bin/env python3
"""
snapshot.py – dump a concise but information-rich snapshot of the current Git
repository (or repositories in a project) for LLM context.

• Includes:  Python, JS/TS/Vue, C# source, manifests, configs, docs, tests, CI files
• Excludes:  build artifacts, binaries, huge files (user-configurable limit)
• Outputs:   <tmp>/<repo>-llm.txt  (or --out path)
• Clipboard: copies result to the system clipboard **only if -c/--clipboard is supplied**
"""

from __future__ import annotations
import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import os

# --- File Inclusion/Exclusion Configuration ---

GLOB_INCLUDE = [
    "*.go",
    "go.mod",
    "go.sum",
    "Gopkg.toml",
    "Gopkg.lock",
    "Makefile",
    "*.tmpl",
    "*.gohtml",
    "*.proto",
    "*.swagger.json",
    "*.openapi.yaml",
    "*.py",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "poetry.lock",
    "requirements*.txt",
    "tox.ini",
    "migrations/**/*.py",
    "*.css",
    "*.scss",
    "*.sass",
    "*.js",
    "*.jsx",
    "*.ts",
    "*.tsx",
    "*.vue",
    "*.hcl",
    "package.json",
    "*.yml",
    "*.yaml",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig*.json",
    "vite.config.*",
    "nuxt.config.*",
    ".eslintrc*",
    ".prettierrc*",
    ".babelrc*",
    "*.cs",
    "*.csproj",
    "*.sln",
    "*.cshtml",
    "*.razor",
    "*.flow",
    "appsettings*.json",
    "*.config",
    "**/launchSettings.json",
    ".dockerignore",
    "*Dockerfile*",
    "docker-compose*.yml",
    "Procfile",
    ".pre-commit-config.yaml",
    ".github/**/*.yml",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
    "README*.md",
    "CHANGELOG*.md",
    "CONTRIBUTING*.md",
    "docs/**/*.{md,mdx}",
    "tests/**/*.{py,js,ts,cs}",
    "*.ipynb",
    "schema/**/*.json",
]

GLOB_EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "__pycache__",
    "bin",
    "obj",
    ".vs",
    ".vscode",
    "vendor",
}

EXCLUDE_FILE_PATTERNS = {
    "*.min.*",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.otf",
    "*.eot",
    "*.pdf",
    "*.doc",
    "*.docx",
    "*.xls",
    "*.xlsx",
    "*.zip",
    "*.tar*",
    "*.gz",
    "*.bz2",
    "*.rar",
    "*.7z",
    "*.nupkg",
    "*.snupkg",
    "*.dll",
    "*.pdb",
    "*.exe",
    "*.so",
    "*.dylib",
    "*.a",
    "*.o",
    "*lock.json",
    "pnpm-lock.yaml",
    "project.assets.json",
}

DEFAULT_SIZE_KB = 400
NOTEBOOK_TRUNCATE = True
SKIPPED_LARGE: list[tuple[Path, int]] = []


def find_git_repo_roots(start_path: Path, max_depth: int) -> list[Path]:
    """Find Git repository roots up to max_depth."""
    repo_roots_found: set[Path] = set()
    # queue stores (path_to_scan, current_depth)
    queue: list[tuple[Path, int]] = [(start_path.resolve(), 0)]
    visited_dirs: set[Path] = {start_path.resolve()}

    head = 0
    while head < len(queue):
        current_dir, depth = queue[head]
        head += 1

        if (current_dir / ".git").is_dir():
            repo_roots_found.add(current_dir)
            # Don't search deeper within an already identified git repo
            # unless max_depth allows exploration beyond its root for *other* nested repos.
            # This simple check is usually sufficient as submodules are typically not nested repos
            # themselves in a way that find_git_repo_roots would re-discover them deeper.
            # If a repo is found, we assume `git ls-files` from its root will handle its contents.

        if depth < max_depth:
            try:
                for child in current_dir.iterdir():
                    if child.is_dir() and child.resolve() not in visited_dirs:
                        if child.name in GLOB_EXCLUDE_DIRS:
                            continue
                        visited_dirs.add(child.resolve())
                        queue.append((child.resolve(), depth + 1))
            except OSError as e:
                print(f"⚠️  Cannot scan directory {current_dir}: {e}", file=sys.stderr)

    # If the start_path itself wasn't a repo but we didn't find any,
    # and depth is 0, try to see if start_path is a repo.
    # This handles the case where depth=0 but start_path is a repo root.
    if (
        not repo_roots_found
        and max_depth == 0
        and (start_path.resolve() / ".git").is_dir()
    ):
        repo_roots_found.add(start_path.resolve())

    return sorted(list(repo_roots_found))


def git_files_in_repo(repo_root: Path) -> list[Path]:
    """Return every path Git sees in a specific repo (tracked + untracked, not ignored)."""
    try:
        # Run git command from the root of the repository
        out = subprocess.check_output(
            [
                "git",
                "-C",
                str(repo_root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--no-empty-directory",
            ],
            text=True,
            encoding="utf-8",
            stderr=subprocess.PIPE,
        )
        # Paths returned by git ls-files are relative to the repo_root
        return [Path(p) for p in out.split("\0") if p]
    except FileNotFoundError:
        # This error is global, so exit. Individual repo errors are handled below.
        sys.exit("❌ ‘git’ command not found; is Git installed?")
    except subprocess.CalledProcessError as e:
        # If 'not a git repository' error occurs for a specific repo_root,
        # it might be due to submodule issues or incorrect detection.
        # We print a warning and return an empty list for this repo.
        stderr_lower = e.stderr.lower()
        if "not a git repository" in stderr_lower or "not a git dir" in stderr_lower:
            print(
                f"⚠️  {repo_root} is not a Git repository or error occurred: {e.stderr.strip()}. Skipping.",
                file=sys.stderr,
            )
        else:
            print(
                f"❌ git ls-files failed for {repo_root}: {e.stderr.strip()}",
                file=sys.stderr,
            )
        return []  # Allow script to continue with other repos
    except Exception as e:
        print(
            f"❌ Unexpected error listing files for {repo_root}: {e}", file=sys.stderr
        )
        return []


def matches_any(path: Path, patterns: list[str] | set[str]) -> bool:
    """Return True if path matches any pattern (full or basename wildcard)."""
    # Check patterns that might include directory components first
    if any(path.match(p) for p in patterns if "/" in p or "**" in p):
        return True
    # Then check patterns that are filename-only
    if any(
        Path(path.name).match(p) for p in patterns if "/" not in p and "**" not in p
    ):
        return True
    return False


def within_size(path: Path, kb: int) -> bool:
    """Return True if file size is within given kilobyte limit."""
    try:
        if not path.is_file():  # path here should be absolute
            return False
        return path.stat().st_size <= kb * 1024
    except OSError as e:
        print(f"⚠️  Cannot check size of {path}: {e}", file=sys.stderr)
        return False


def strip_ipynb(path: Path) -> str:  # path here should be absolute
    """Return notebook JSON with outputs removed."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
        cells = nb.get("cells")
        if isinstance(cells, list):
            for cell in cells:
                if isinstance(cell, dict):
                    cell.pop("outputs", None)
                    cell.pop("metadata", None)
                    if "execution_count" in cell:
                        cell["execution_count"] = None
        return json.dumps(nb, ensure_ascii=False, indent=1)
    except json.JSONDecodeError as e:
        return f"# ERROR decoding notebook JSON {path}: {e}\n" + path.read_text(
            encoding="utf-8", errors="replace"
        )
    except Exception as e:
        return f"# ERROR processing notebook {path}: {e}\n" + path.read_text(
            encoding="utf-8", errors="replace"
        )


def collect(
    repo_roots_to_scan: list[Path], size_kb: int, project_top_level_path: Path
) -> list[tuple[Path, Path]]:
    """Collect files matching inclusion rules and size limit from specified repo roots.
    Returns a list of (display_path, absolute_path) tuples.
    display_path is relative to project_top_level_path.
    absolute_path is the full path to the file.
    """
    kept_files: dict[Path, Path] = (
        {}
    )  # {display_path: absolute_path} to ensure uniqueness
    SKIPPED_LARGE.clear()
    total_git_files_count = 0

    for repo_root in repo_roots_to_scan:
        print(f"ℹ️  Scanning Git repository at {repo_root}...", file=sys.stderr)
        files_in_this_repo = git_files_in_repo(repo_root)
        total_git_files_count += len(files_in_this_repo)

        for p_relative_to_repo in files_in_this_repo:
            absolute_p = (repo_root / p_relative_to_repo).resolve()
            try:
                # display_p is relative to the overall project_top_level_path
                display_p = absolute_p.relative_to(project_top_level_path)
            except (
                ValueError
            ):  # Should not happen if repo_root is under project_top_level_path
                display_p = absolute_p

            if not absolute_p.is_file():
                continue

            # Use display_p for filtering based on patterns and directory names
            # These patterns are typically defined relative to a project structure
            if any(
                part in GLOB_EXCLUDE_DIRS for part in display_p.parts[:-1]
            ):  # Check parent dirs
                continue
            if (
                display_p.name in GLOB_EXCLUDE_DIRS
            ):  # Check file name itself if it's a dir name pattern
                continue
            if matches_any(
                Path(display_p.name), EXCLUDE_FILE_PATTERNS
            ):  # Match filename patterns
                continue

            if matches_any(display_p, GLOB_INCLUDE):
                if within_size(absolute_p, size_kb):
                    if display_p not in kept_files:  # Ensure unique display paths
                        kept_files[display_p] = absolute_p
                else:
                    try:
                        size = absolute_p.stat().st_size // 1024
                    except OSError:
                        size = -1
                    SKIPPED_LARGE.append(
                        (display_p, size)
                    )  # Store display_path for skipped

    print(
        f"ℹ️  Found {total_git_files_count} files across {len(repo_roots_to_scan)} Git repo(s). Kept {len(kept_files)} files.",
        file=sys.stderr,
    )
    # Sort by display_path for consistent output
    return sorted(kept_files.items())


def dump(
    files_to_dump: list[tuple[Path, Path]], out_file: Path, echo: bool, size_kb: int
) -> None:
    """Write the snapshot of collected files into a single output file.
    files_to_dump is a list of (display_path, absolute_path) tuples.
    """
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8") as dst:
            for i, (display_p, absolute_p) in enumerate(
                files_to_dump
            ):  # Iterate sorted items
                posix_path_str = display_p.as_posix()
                color_start = "\033[93m" if echo else ""
                color_end = "\033[0m" if echo else ""
                banner = f"{'' if i == 0 else '\n'}📄 FILE {color_start}{posix_path_str}{color_end}:\n"

                if echo:
                    print(banner, end="", file=sys.stderr if echo else sys.stdout)

                dst.write(f"📄 FILE {posix_path_str}:\n")

                try:
                    if absolute_p.suffix == ".ipynb" and NOTEBOOK_TRUNCATE:
                        content = strip_ipynb(absolute_p)
                    else:
                        content = absolute_p.read_text(
                            encoding="utf-8", errors="replace"
                        )
                except Exception as exc:
                    error_msg = (
                        f"# ERROR reading {posix_path_str} (from {absolute_p}): {exc}\n"
                    )
                    if echo:
                        print(error_msg, end="", file=sys.stderr)
                    content = error_msg

                content = content.rstrip() + "\n"
                if echo:
                    print(content, end="")
                dst.write(content)

        if SKIPPED_LARGE:
            # Sort SKIPPED_LARGE by path before printing/writing
            sorted_skipped_large = sorted(SKIPPED_LARGE, key=lambda item: item[0])
            footer_lines = [
                "\n" + "=" * 80,
                f"# Skipped {len(sorted_skipped_large)} file(s) larger than {size_kb} KB",
                "=" * 80,
                *(f"# - {p.as_posix()} ({sz} KB)" for p, sz in sorted_skipped_large),
                "",
            ]
            footer = "\n".join(footer_lines)
            if echo:
                print(footer, end="", file=sys.stderr if echo else sys.stdout)
            with out_file.open("a", encoding="utf-8") as dst:
                dst.write(footer)

    except OSError as e:
        sys.exit(f"❌ Error writing to output file {out_file}: {e}")
    except Exception as e:
        sys.exit(f"❌ Unexpected error during file dumping: {e}")


def is_wsl() -> bool:
    """Return True if running inside Windows Subsystem for Linux."""
    return (
        "microsoft" in platform.uname().release.lower()
        or "WSL_DISTRO_NAME" in os.environ
    )


def copy_to_clipboard(file_path: Path) -> bool:
    """Try to put file content on the system clipboard. Return True on success."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"⚠️  Cannot read file {file_path} for clipboard: {e}", file=sys.stderr)
        return False

    os_name = platform.system()
    tool: list[str] | None = None

    if os_name == "Windows" or (os_name == "Linux" and is_wsl()):
        if shutil.which("clip.exe"):
            tool = ["clip.exe"]
    elif os_name == "Darwin":
        if shutil.which("pbcopy"):
            tool = ["pbcopy"]
    elif os_name == "Linux":
        if shutil.which("wl-copy"):
            tool = ["wl-copy"]
        elif shutil.which("xclip"):
            tool = ["xclip", "-selection", "clipboard"]

    if not tool:
        print(
            f"ℹ️  No clipboard tool found for {os_name} (WSL={is_wsl()}). Cannot copy.",
            file=sys.stderr,
        )
        return False

    tool_name = Path(tool[0]).name
    try:
        result = subprocess.run(
            tool,
            input=content,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode == 0:
            print(f"📋 Snapshot copied to clipboard via {tool_name}.", file=sys.stderr)
            return True
        else:
            print(
                f"⚠️  Clipboard copy via {tool_name} failed (exit code {result.returncode}).",
                file=sys.stderr,
            )
            if result.stderr:
                print(f"   Error: {result.stderr.strip()}", file=sys.stderr)
            if result.stdout:
                print(f"   Output: {result.stdout.strip()}", file=sys.stderr)
            return False
    except FileNotFoundError:
        print(f"⚠️  Clipboard tool '{tool_name}' not found.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"⚠️  Clipboard error running {tool_name}: {e}", file=sys.stderr)
        return False


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    project_top_level_path = Path.cwd()
    repo_name = project_top_level_path.name or "snapshot"
    default_out = Path(tempfile.gettempdir()) / f"{repo_name}-llm.txt"

    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "-o",
        "--out",
        type=Path,
        default=default_out,
        help=f"Output file path (default: {default_out})",
    )
    ap.add_argument(
        "-k",
        "--max-kb",
        type=int,
        default=DEFAULT_SIZE_KB,
        metavar="KB",
        help=f"Maximum file size in kilobytes (default: {DEFAULT_SIZE_KB} KB)",
    )
    ap.add_argument(
        "--no-ipynb-truncate",
        action="store_false",
        dest="truncate_ipynb",
        help="Include Jupyter notebook outputs instead of stripping them.",
    )
    ap.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress echoing of file contents to standard output.",
    )
    ap.add_argument(
        "-c",
        "--clipboard",
        action="store_true",
        help="Copy the final snapshot content to the system clipboard.",
    )
    ap.add_argument(
        "-d",
        "--depth",
        type=int,
        default=0,
        metavar="N",
        help="Scan for Git repositories in subdirectories up to N levels deep "
        "(0 for current directory only, 1 for current and direct children, etc.). "
        "A value of -1 means infinite depth.",
    )
    return ap.parse_args()


def main() -> None:
    """Main program entry point."""
    args = parse_args()

    global NOTEBOOK_TRUNCATE
    NOTEBOOK_TRUNCATE = args.truncate_ipynb

    progress_stream = sys.stderr
    project_top_level_path = Path.cwd().resolve()

    max_depth_scan = args.depth
    if args.depth == -1:  # Special value for "infinite" depth
        max_depth_scan = float("inf")

    print(
        f"🔍 Searching for Git repositories (max depth: {args.depth})...",
        file=progress_stream,
    )
    try:
        repo_roots = find_git_repo_roots(project_top_level_path, max_depth_scan)
    except Exception as e:
        sys.exit(f"❌ Failed during Git repository search: {e}")

    if not repo_roots:
        # Check if the current directory itself is a Git repo if depth was 0 and find_git_repo_roots didn't add it
        # (find_git_repo_roots already handles this, but as a fallback)
        if (
            project_top_level_path / ".git"
        ).is_dir() and project_top_level_path not in repo_roots:
            repo_roots = [project_top_level_path]
        else:
            sys.exit(
                f"❌ No Git repositories found within the specified depth starting from {project_top_level_path}."
            )

    print(
        f"ℹ️  Identified {len(repo_roots)} Git repository root(s) to scan.",
        file=progress_stream,
    )

    print(f"🔍 Collecting files (max size: {args.max_kb} KB)...", file=progress_stream)
    try:
        # `collect` now needs the list of repo roots and the top-level project path
        files_to_dump = collect(repo_roots, args.max_kb, project_top_level_path)
    except Exception as e:
        sys.exit(f"❌ Failed during file collection: {e}")

    if not files_to_dump:
        sys.exit(
            "❌ No files matched the inclusion criteria or size limits across the identified repositories."
        )

    print(
        f"📝 Writing snapshot of {len(files_to_dump)} files to {args.out}...",
        file=progress_stream,
    )
    try:
        dump(files_to_dump, args.out, echo=not args.quiet, size_kb=args.max_kb)
    except Exception as e:
        sys.exit(f"❌ Failed during file dumping: {e}")

    if args.clipboard:
        if not copy_to_clipboard(args.out):
            print(
                f"⚠️  Could not copy to clipboard. The snapshot is saved at {args.out.resolve()}",
                file=progress_stream,
            )

    print(f"\n✅ Snapshot complete → {args.out.resolve()}", file=progress_stream)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🚫 Operation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        print(f"\n💥 An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
