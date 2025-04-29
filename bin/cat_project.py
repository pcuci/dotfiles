#!/usr/bin/env python3
"""
snapshot.py – dump a concise but information-rich snapshot of the current Git
repository for LLM context.

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
    "*.py",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "poetry.lock",
    "requirements*.txt",
    "tox.ini",
    "migrations/**/*.py",
    "*.js",
    "*.jsx",
    "*.ts",
    "*.tsx",
    "*.vue",
    "package.json",
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
    "appsettings*.json",
    "*.config",
    "**/launchSettings.json",
    ".dockerignore",
    "Dockerfile*",
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
    "*.lock.json",
    "project.assets.json",
}

DEFAULT_SIZE_KB = 400
NOTEBOOK_TRUNCATE = True
SKIPPED_LARGE: list[tuple[Path, int]] = []


def git_files() -> list[Path]:
    """Return every path Git sees (tracked + untracked, not ignored)."""
    try:
        out = subprocess.check_output(
            [
                "git",
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
        return [Path(p) for p in out.split("\0") if p]
    except FileNotFoundError:
        sys.exit("❌ ‘git’ command not found; is Git installed?")
    except subprocess.CalledProcessError as e:
        if "not a git repository" in e.stderr.lower():
            sys.exit("❌ This directory is not a Git repository.")
        sys.exit(f"❌ git ls-files failed: {e.stderr.strip()}")
    except Exception as e:
        sys.exit(f"❌ Unexpected error listing files: {e}")


def matches_any(path: Path, patterns: list[str] | set[str]) -> bool:
    """Return True if path matches any pattern (full or basename wildcard)."""
    if any(path.match(p) for p in patterns if "/" in p or "**" in p):
        return True
    if any(
        Path(path.name).match(p) for p in patterns if "/" not in p and "**" not in p
    ):
        return True
    return False


def within_size(path: Path, kb: int) -> bool:
    """Return True if file size is within given kilobyte limit."""
    try:
        if not path.is_file():
            return False
        return path.stat().st_size <= kb * 1024
    except OSError as e:
        print(f"⚠️  Cannot check size of {path}: {e}", file=sys.stderr)
        return False


def strip_ipynb(path: Path) -> str:
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


def collect(size_kb: int) -> list[Path]:
    """Collect files matching inclusion rules and size limit."""
    keep: list[Path] = []
    SKIPPED_LARGE.clear()
    git_paths = git_files()
    print(f"ℹ️  Found {len(git_paths)} files tracked by Git.")

    for p in git_paths:
        if not p.is_file():
            continue
        if any(part in GLOB_EXCLUDE_DIRS for part in p.parts):
            continue
        if matches_any(Path(p.name), EXCLUDE_FILE_PATTERNS):
            continue
        if matches_any(p, GLOB_INCLUDE):
            if within_size(p, size_kb):
                keep.append(p)
            else:
                try:
                    size = p.stat().st_size // 1024
                except OSError:
                    size = -1
                SKIPPED_LARGE.append((p, size))
    return keep


def dump(paths: list[Path], out_file: Path, echo: bool, size_kb: int) -> None:
    """Write the snapshot of collected files into a single output file."""
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8") as dst:
            for i, p in enumerate(sorted(paths)):
                posix_path = p.as_posix()
                color_start = "\033[93m" if echo else ""
                color_end = "\033[0m" if echo else ""
                banner = f"{'' if i == 0 else '\n'}📄 FILE {color_start}{posix_path}{color_end}:\n"

                if echo:
                    print(banner, end="", file=sys.stderr if echo else sys.stdout)

                dst.write(f"📄 FILE {posix_path}:\n")

                try:
                    if p.suffix == ".ipynb" and NOTEBOOK_TRUNCATE:
                        content = strip_ipynb(p)
                    else:
                        content = p.read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    error_msg = f"# ERROR reading {posix_path}: {exc}\n"
                    if echo:
                        print(error_msg, end="", file=sys.stderr)
                    content = error_msg

                content = content.rstrip() + "\n"
                if echo:
                    print(content, end="")
                dst.write(content)

        if SKIPPED_LARGE:
            footer_lines = [
                "\n" + "=" * 80,
                f"# Skipped {len(SKIPPED_LARGE)} file(s) larger than {size_kb} KB",
                "=" * 80,
                *(f"# - {p.as_posix()} ({sz} KB)" for p, sz in sorted(SKIPPED_LARGE)),
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
    repo_name = Path.cwd().name or "snapshot"
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
    return ap.parse_args()


def main() -> None:
    """Main program entry point."""
    args = parse_args()

    global NOTEBOOK_TRUNCATE
    NOTEBOOK_TRUNCATE = args.truncate_ipynb

    progress_stream = sys.stderr

    print(f"🔍 Collecting files (max size: {args.max_kb} KB)...", file=progress_stream)
    try:
        paths = collect(args.max_kb)
    except Exception as e:
        sys.exit(f"❌ Failed during file collection: {e}")

    if not paths:
        sys.exit("❌ No files matched the inclusion criteria or size limits.")

    print(
        f"📝 Writing snapshot of {len(paths)} files to {args.out}...",
        file=progress_stream,
    )
    try:
        dump(paths, args.out, echo=not args.quiet, size_kb=args.max_kb)
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
