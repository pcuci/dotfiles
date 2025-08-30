"""
Core logic for the catp snapshot tool.
Handles finding, filtering, collecting, and dumping files.
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

from .config import EXCLUDE_FILE_PATTERNS, GLOB_EXCLUDE_DIRS, GLOB_INCLUDE

log = logging.getLogger(__name__)

def find_git_repo_roots(start_path: Path, max_depth: float) -> list[Path]:
    """Find Git repository roots up to max_depth."""
    repo_roots_found: set[Path] = set()
    queue: list[tuple[Path, int]] = [(start_path.resolve(), 0)]
    visited_dirs: set[Path] = {start_path.resolve()}

    head = 0
    while head < len(queue):
        current_dir, depth = queue[head]
        head += 1

        if (current_dir / ".git").is_dir():
            repo_roots_found.add(current_dir)

        if depth < max_depth:
            try:
                for child in current_dir.iterdir():
                    if child.is_dir() and child.resolve() not in visited_dirs:
                        if child.name in GLOB_EXCLUDE_DIRS:
                            continue
                        visited_dirs.add(child.resolve())
                        queue.append((child.resolve(), depth + 1))
            except OSError as e:
                log.warning(f"⚠️  Cannot scan directory {current_dir}: {e}")

    if not repo_roots_found and (start_path.resolve() / ".git").is_dir():
        repo_roots_found.add(start_path.resolve())

    return sorted(list(repo_roots_found))

def git_files_in_repo(repo_root: Path) -> list[Path]:
    """Return every path Git sees in a specific repo."""
    try:
        cmd = [
            "git", "-C", str(repo_root), "ls-files", "--cached", "--others",
            "--exclude-standard", "-z", "--no-empty-directory",
        ]
        out = subprocess.check_output(cmd, text=True, encoding="utf-8", stderr=subprocess.PIPE)
        return [Path(p) for p in out.split("\0") if p]
    except FileNotFoundError:
        sys.exit("❌ ‘git’ command not found; is Git installed?")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.lower()
        if "not a git repository" in stderr or "not a git dir" in stderr:
            log.warning(f"⚠️  {repo_root} is not a Git repository. Skipping.")
        else:
            log.error(f"❌ git ls-files failed for {repo_root}: {e.stderr.strip()}")
        return []
    except Exception as e:
        log.error(f"❌ Unexpected error listing files for {repo_root}: {e}")
        return []

def matches_any(path: Path, patterns: set[str]) -> bool:
    """Return True if path matches any pattern."""
    return any(path.match(p) for p in patterns if "/" in p or "**" in p) or \
           any(Path(path.name).match(p) for p in patterns if "/" not in p and "**" not in p)

def within_size(path: Path, kb: int) -> bool:
    """Return True if file size is within the limit."""
    try:
        return path.is_file() and path.stat().st_size <= kb * 1024
    except OSError as e:
        log.warning(f"⚠️  Cannot check size of {path}: {e}")
        return False

def strip_ipynb(path: Path) -> str:
    """Return notebook JSON with outputs removed."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
        for cell in nb.get("cells", []):
            if isinstance(cell, dict):
                cell.pop("outputs", None)
                cell.pop("metadata", None)
                cell["execution_count"] = None
        return json.dumps(nb, ensure_ascii=False, indent=1)
    except (json.JSONDecodeError, Exception) as e:
        log.warning(f"# ERROR processing notebook {path}: {e}")
        return path.read_text(encoding="utf-8", errors="replace")

def collect(
    repo_roots: list[Path], size_kb: int, project_root: Path
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, int]]]:
    """Collect files, returning kept and skipped files."""
    kept_files: dict[Path, Path] = {}
    skipped_large: list[tuple[Path, int]] = []
    total_files = 0

    for repo_root in repo_roots:
        log.info(f"ℹ️  Scanning Git repository at {repo_root}...")
        files = git_files_in_repo(repo_root)
        total_files += len(files)

        for p_repo in files:
            p_abs = (repo_root / p_repo).resolve()
            try:
                p_display = p_abs.relative_to(project_root)
            except ValueError:
                p_display = p_abs

            if not p_abs.is_file(): continue
            if any(part in GLOB_EXCLUDE_DIRS for part in p_display.parts): continue
            if matches_any(Path(p_display.name), EXCLUDE_FILE_PATTERNS): continue

            if matches_any(p_display, GLOB_INCLUDE):
                if within_size(p_abs, size_kb):
                    if p_display not in kept_files:
                        kept_files[p_display] = p_abs
                else:
                    try:
                        size = p_abs.stat().st_size // 1024
                    except OSError:
                        size = -1
                    skipped_large.append((p_display, size))

    log.info(f"ℹ️  Found {total_files} files across {len(repo_roots)} repo(s). Kept {len(kept_files)}.")
    return sorted(kept_files.items()), sorted(skipped_large)

def dump(
    files_to_dump: list[tuple[Path, Path]],
    skipped_large: list[tuple[Path, int]],
    out_file: Path,
    echo: bool,
    size_kb: int,
    truncate_ipynb: bool,
) -> None:
    """Write the snapshot to the output file."""
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8") as dst:
            for i, (display_p, absolute_p) in enumerate(files_to_dump):
                posix_path = display_p.as_posix()
                banner = f"{'' if i == 0 else '\n'}📄 FILE {posix_path}:\n"
                if echo:
                    sys.stderr.write(f"\033[93m{banner.strip()}\033[0m\n")

                dst.write(banner)

                try:
                    content = strip_ipynb(absolute_p) if absolute_p.suffix == ".ipynb" and truncate_ipynb else \
                              absolute_p.read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    content = f"# ERROR reading {posix_path}: {exc}\n"
                    log.warning(content.strip())

                content = content.rstrip() + "\n"
                if echo:
                    sys.stderr.write(content)
                dst.write(content)

        if skipped_large:
            footer_lines = [
                "\n" + "=" * 80,
                f"# Skipped {len(skipped_large)} file(s) larger than {size_kb} KB",
                "=" * 80,
                *(f"# - {p.as_posix()} ({sz} KB)" for p, sz in skipped_large),
                "",
            ]
            footer = "\n".join(footer_lines)
            log.info(footer)
            with out_file.open("a", encoding="utf-8") as dst:
                dst.write(footer)

    except OSError as e:
        sys.exit(f"❌ Error writing to output file {out_file}: {e}")