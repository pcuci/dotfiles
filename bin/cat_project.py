#!/usr/bin/env python3
"""
snapshot.py – dump a concise but information-rich snapshot of the current Git
repository for LLM context.

• Includes:  Python, JS/TS/Vue source, manifests, configs, docs, tests, CI files
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

GLOB_INCLUDE = [
    "*.py",
    "*.js",
    "*.jsx",
    "*.ts",
    "*.tsx",
    "*.vue",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "requirements*.txt",
    "tsconfig*.json",
    "vite.config.*",
    "nuxt.config.*",
    ".eslintrc*",
    ".prettierrc*",
    ".babelrc*",
    ".dockerignore",
    "Dockerfile*",
    "docker-compose*.yml",
    "Procfile",
    ".pre-commit-config.yaml",
    "tox.ini",
    ".github/**/*.yml",
    ".gitlab-ci.yml",
    "README*.md",
    "CHANGELOG*.md",
    "CONTRIBUTING*.md",
    "docs/**/*.{md,mdx}",
    "tests/**/*.{py,js,ts}",
    "*.ipynb",
    "schema/**/*.json",
    "migrations/**/*.py",
]
GLOB_EXCLUDE_DIRS = {".git", "node_modules", "dist", "build", ".venv", "__pycache__"}
EXCLUDE_FILE_PATTERNS = {
    "*.min.*",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.lock.json",
    "*.zip",
    "*.tar*",
    "*.so",
    "*.dylib",
    "*.exe",
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
    return any(path.match(p) for p in patterns) or any(
        Path(path.name).match(p) for p in patterns if "*" in p and "/" not in p
    )


def within_size(path: Path, kb: int) -> bool:
    """Return True if file size is within given kilobyte limit."""
    try:
        return path.stat().st_size <= kb * 1024
    except OSError:
        return False


def strip_ipynb(path: Path) -> str:
    """Return notebook JSON with outputs removed."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
        for cell in nb.get("cells", []):
            if isinstance(cell, dict):
                cell.pop("outputs", None)
                if "execution_count" in cell:
                    cell["execution_count"] = None
        return json.dumps(nb, ensure_ascii=False, indent=1)
    except Exception as e:
        return f"# ERROR processing notebook {path}: {e}\n" + path.read_text(
            encoding="utf-8", errors="replace"
        )


def collect(size_kb: int) -> list[Path]:
    """Collect files matching inclusion rules and size limit."""
    keep: list[Path] = []
    SKIPPED_LARGE.clear()
    for p in git_files():
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
                SKIPPED_LARGE.append((p, p.stat().st_size // 1024))
    return keep


def dump(paths: list[Path], out_file: Path, echo: bool, size_kb: int) -> None:
    """Write the snapshot of collected files into a single output file."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as dst:
        for i, p in enumerate(sorted(paths)):
            banner = (
                ("" if i == 0 else "\n")
                + "📄 FILE \033[93m"
                + p.as_posix()
                + "\033[0m:\n"
            )
            if echo:
                print(banner, end="")
            dst.write(banner)

            try:
                if p.suffix == ".ipynb" and NOTEBOOK_TRUNCATE:
                    content = strip_ipynb(p)
                else:
                    content = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                content = f"# ERROR reading {p.as_posix()}: {exc}\n"

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
            print(footer, end="")
        out_file.write_text(
            out_file.read_text(encoding="utf-8") + footer, encoding="utf-8"
        )


def is_wsl() -> bool:
    """Return True if running inside Windows Subsystem for Linux."""
    try:
        return "microsoft" in platform.uname().release.lower()
    except Exception:
        return False


def copy_to_clipboard(file_path: Path) -> bool:
    """Try to put file content on the system clipboard. Return True on success."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"⚠️  Cannot read file for clipboard: {e}", file=sys.stderr)
        return False

    os_name = platform.system()
    tool: list[str] | None = None

    if os_name == "Windows" and shutil.which("clip.exe"):
        tool = ["clip.exe"]
    elif os_name == "Darwin" and shutil.which("pbcopy"):
        tool = ["pbcopy"]
    elif os_name == "Linux":
        if is_wsl() and shutil.which("clip.exe"):
            tool = ["clip.exe"]
        elif shutil.which("wl-copy"):
            tool = ["wl-copy"]
        elif shutil.which("xclip"):
            tool = ["xclip", "-selection", "clipboard"]

    if not tool:
        print(f"ℹ️  No clipboard tool found for {os_name}.", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            tool, input=content, text=True, capture_output=True, encoding="utf-8"
        )
        if result.returncode == 0:
            print(f"📋 Snapshot copied to clipboard via {Path(tool[0]).name}.")
            return True
        print(f"⚠️  Clipboard copy failed (exit {result.returncode}).", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return False
    except Exception as e:
        print(f"⚠️  Clipboard error: {e}", file=sys.stderr)
        return False


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    default_out = Path(tempfile.gettempdir()) / f"{Path.cwd().name}-llm.txt"
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "-o",
        "--out",
        type=Path,
        default=default_out,
        help=f"Output file (default: {default_out})",
    )
    ap.add_argument(
        "-k",
        "--max-kb",
        type=int,
        default=DEFAULT_SIZE_KB,
        metavar="KB",
        help=f"Skip files > KB kilobytes (default {DEFAULT_SIZE_KB})",
    )
    ap.add_argument(
        "--no-ipynb-truncate",
        action="store_false",
        dest="truncate_ipynb",
        help="Keep Jupyter outputs instead of stripping them.",
    )
    ap.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Do not echo file contents to stdout.",
    )
    ap.add_argument(
        "-c",
        "--clipboard",
        action="store_true",
        help="Copy the snapshot to the system clipboard.",
    )
    return ap.parse_args()


def main() -> None:
    """Main program entry point."""
    args = parse_args()
    global NOTEBOOK_TRUNCATE
    NOTEBOOK_TRUNCATE = args.truncate_ipynb

    print(f"🔍 Collecting files (≤{args.max_kb} KB)…")
    paths = collect(args.max_kb)
    if not paths:
        sys.exit("❌ No files matched the inclusion rules or size limits.")

    print(f"📝 Writing snapshot ({len(paths)} files)…")
    dump(paths, args.out, echo=not args.quiet, size_kb=args.max_kb)

    if args.clipboard:
        copy_to_clipboard(args.out)

    print(f"\n✅ Snapshot complete → {args.out.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
