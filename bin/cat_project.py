#!/usr/bin/env python3
"""
snapshot.py – dump a concise but information‑rich snapshot of the current Git
repository for LLM context.

• Includes:  Python, JS/TS/Vue source, manifests, configs, docs, tests, CI files
• Excludes:  build artefacts, binaries, huge files (user‑configurable limit)
• Outputs:   <tmp>/<repo>-llm.txt (or custom --out path)
"""

from __future__ import annotations
import argparse
import subprocess
import sys
import json
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
    """Return every path Git sees (tracked or untracked & un‑ignored)."""
    out = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        text=True,
    )
    return [Path(p) for p in out.split("\0") if p]


def matches_any(path: Path, globs: list[str]) -> bool:
    """Check if the path matches any pattern in the provided glob list."""
    return any(path.match(g) for g in globs)


def within_size(path: Path, kb: int) -> bool:
    """Check if the file size is within the specified kilobyte limit."""
    return path.stat().st_size <= kb * 1024


def strip_ipynb(path: Path) -> str:
    """Return notebook JSON with outputs removed."""
    with path.open(encoding="utf-8") as f:
        nb = json.load(f)
    for cell in nb.get("cells", []):
        cell.pop("outputs", None)
        cell["execution_count"] = None
    return json.dumps(nb, ensure_ascii=False, indent=1)


def collect(size_kb: int) -> list[Path]:
    """
    Collect files that match inclusion rules and are within size constraints.

    Args:
        size_kb (int): Maximum size in kilobytes for included files.

    Returns:
        list[Path]: List of files to include in the snapshot.
    """
    keep: list[Path] = []
    for p in git_files():
        if any(part in GLOB_EXCLUDE_DIRS for part in p.parts):
            continue
        if matches_any(p, EXCLUDE_FILE_PATTERNS):
            continue
        if matches_any(p, GLOB_INCLUDE):
            if within_size(p, size_kb):
                keep.append(p)
            else:
                SKIPPED_LARGE.append((p, p.stat().st_size // 1024))
    return keep


def dump(paths: list[Path], out_file: Path, echo: bool, size_kb: int) -> None:
    """
    Write selected file contents into a single snapshot file.

    Args:
        paths (list[Path]): Files to include in the snapshot.
        out_file (Path): Output path for the snapshot.
        echo (bool): Whether to also print contents to stdout.
        size_kb (int): Size threshold for skipped files.
    """
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as dst:
        for p in sorted(paths):
            rel = p.as_posix()
            banner = f"\n{'=' * 80}\n# {rel}\n{'=' * 80}\n"
            if echo:
                print(banner, end="")
            dst.write(banner)

            try:
                if p.suffix == ".ipynb" and NOTEBOOK_TRUNCATE:
                    content = strip_ipynb(p)
                else:
                    content = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                content = f"# ERROR reading {rel}: {exc}\n"

            if echo:
                print(content)
            dst.write(content + "\n")

    if SKIPPED_LARGE:
        footer_lines = [
            f"\n{'=' * 80}",
            f"# Skipped (>{size_kb} KB)",
            f"{'=' * 80}",
            *(f"{p} — {sz} KB" for p, sz in SKIPPED_LARGE),
            "",
        ]
        footer = "\n".join(footer_lines)
        if echo:
            print(footer, end="")
        with out_file.open("a", encoding="utf-8") as dst:
            dst.write(footer)


def main() -> None:
    """Parse CLI arguments and run the snapshot collection/dump process."""
    ap = argparse.ArgumentParser(
        description="Create llm.txt snapshot of this Git repo for LLM context."
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(tempfile.gettempdir()) / f"{Path.cwd().name}-llm.txt",
        help="Output file path (default: /tmp/<repo>-llm.txt)",
    )
    ap.add_argument(
        "--max-kb",
        type=int,
        default=DEFAULT_SIZE_KB,
        metavar="N",
        help=f"Skip files larger than N KB (default {DEFAULT_SIZE_KB})",
    )
    ap.add_argument("--quiet", action="store_true", help="Suppress echo to stdout.")
    args = ap.parse_args()

    paths = collect(args.max_kb)
    if not paths:
        sys.exit("No files matched inclusion rules.")

    dump(paths, args.out, echo=not args.quiet, size_kb=args.max_kb)
    print(f"\n✅ Snapshot written → {args.out}\ncatp && cat {args.out} | clip.exe")


if __name__ == "__main__":
    main()
