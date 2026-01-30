"""
Core logic for the catp snapshot tool.
Handles finding, filtering, collecting, and dumping files.
"""
import fnmatch
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

from .config import EXCLUDE_FILE_PATTERNS, GLOB_EXCLUDE_DIRS, GLOB_INCLUDE

log = logging.getLogger(__name__)


def matches_path(path: Path, patterns: set[str]) -> bool:
    """
    Return True if path matches any glob pattern.
    - Patterns with '/' or '**' are matched against the full path.
    - Simple patterns are matched against any component of the path.
    """
    path_str = path.as_posix()
    path_parts = path.parts
    for p in patterns:
        if "/" in p or "**" in p:
            if path.match(p) or fnmatch.fnmatch(path_str, p):
                return True
        else:
            if any(fnmatch.fnmatch(part, p) for part in path_parts):
                return True
    return False


def should_exclude_subtree(rel_path: Path, exclude_patterns: set[str]) -> bool:
    """
    Check if a directory should be pruned from traversal.
    Returns True if any exclude pattern denotes this as a subtree to skip.
    """
    path_str = rel_path.as_posix()
    for p in exclude_patterns:
        # Check if pattern matches this directory or any prefix
        if p.endswith("/**"):
            prefix = p[:-3]  # Remove /**
            if path_str == prefix or path_str.startswith(prefix + "/"):
                return True
        if fnmatch.fnmatch(path_str, p) or fnmatch.fnmatch(path_str + "/", p):
            return True
    return False


def find_git_repo_roots(
    start_path: Path,
    max_depth: float,
    only_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> list[Path]:
    """
    Find Git repository roots up to max_depth.
    
    Applies unified filtering:
    - If only_patterns provided, repo must match at least one
    - If exclude_patterns provided, repo is dropped if any match
    - Excluded subtrees are not descended into (performance optimization)
    """
    repo_roots_found: set[Path] = set()
    queue: list[tuple[Path, int]] = [(start_path.resolve(), 0)]
    visited_dirs: set[Path] = {start_path.resolve()}

    only_set = set(only_patterns) if only_patterns else None
    exclude_set = set(exclude_patterns) if exclude_patterns else set()

    head = 0
    while head < len(queue):
        current_dir, depth = queue[head]
        head += 1

        # Calculate relative path for filtering
        try:
            rel_path = current_dir.relative_to(start_path)
        except ValueError:
            rel_path = Path(".")

        # Check if this is a repo
        if (current_dir / ".git").is_dir():
            # Apply unified filters to repo path
            if rel_path != Path("."):
                # Check exclude first
                if matches_path(rel_path, exclude_set):
                    log.debug(f"[{rel_path}] REPO SKIP: Matches exclude pattern.")
                    continue
                # Check only (if provided)
                if only_set and not matches_path(rel_path, only_set):
                    log.debug(f"[{rel_path}] REPO SKIP: Does not match --only pattern.")
                    continue
            repo_roots_found.add(current_dir)

        if depth < max_depth:
            try:
                for child in sorted(current_dir.iterdir()):
                    if child.is_dir() and child.resolve() not in visited_dirs:
                        if child.name in GLOB_EXCLUDE_DIRS:
                            continue
                        
                        # Calculate child's relative path
                        try:
                            child_rel = child.relative_to(start_path)
                        except ValueError:
                            child_rel = Path(child.name)
                        
                        # Pruning: don't descend into excluded subtrees
                        if should_exclude_subtree(child_rel, exclude_set):
                            log.debug(f"[{child_rel}] PRUNE: Subtree excluded, not descending.")
                            continue
                        
                        visited_dirs.add(child.resolve())
                        queue.append((child.resolve(), depth + 1))
            except OSError as e:
                log.warning(f"⚠️  Cannot scan directory {current_dir}: {e}")

    # Handle case where start_path itself is a repo
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

# Alias for backward compatibility in file filtering
matches_any = matches_path

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
    repo_roots: List[Path],
    size_kb: int,
    project_root: Path,
    paths: Optional[List[Path]] = None,
    only_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    allow_patterns: Optional[List[str]] = None,
) -> Tuple[List[Tuple[Path, Path]], List[Tuple[Path, int]]]:
    """Collect files, returning kept and skipped files."""
    kept_files: dict[Path, Path] = {}
    skipped_large: list[tuple[Path, int]] = []
    
    active_exclude_patterns = set(EXCLUDE_FILE_PATTERNS)
    if allow_patterns:
        log.debug(f"Disabling default excludes: {allow_patterns}")
        active_exclude_patterns.difference_update(allow_patterns)

    if exclude_patterns:
        log.debug(f"Adding user excludes: {exclude_patterns}")
        active_exclude_patterns.update(exclude_patterns)

    include_patterns = set(only_patterns) if only_patterns else set(GLOB_INCLUDE)
    scoped_paths = [p.resolve() for p in paths] if paths else []
    
    all_git_files = []
    for repo_root in repo_roots:
        log.info(f"ℹ️  Scanning Git repository at {repo_root}...")
        for p_repo in git_files_in_repo(repo_root):
            p_abs = (repo_root / p_repo).resolve()
            try:
                p_display = p_abs.relative_to(project_root)
            except ValueError:
                p_display = p_abs
            all_git_files.append((p_abs, p_display))
            
    total_files = len(all_git_files)
    
    for p_abs, p_display in all_git_files:
        if not p_abs.is_file():
            continue

        if any(part in GLOB_EXCLUDE_DIRS for part in p_display.parts):
            log.debug(f"[{p_display}] SKIP: In excluded directory.")
            continue
        if matches_any(p_display, active_exclude_patterns):
            log.debug(f"[{p_display}] SKIP: Matches exclude pattern.")
            continue

        if scoped_paths and not any(p_abs.is_relative_to(sp) for sp in scoped_paths):
            log.debug(f"[{p_display}] SKIP: Not in specified paths.")
            continue
        
        if not matches_any(p_display, include_patterns):
            log.debug(f"[{p_display}] SKIP: Does not match include pattern.")
            continue

        log.debug(f"[{p_display}] KEEP: Matched include patterns and passed all filters.")
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


def _write_preamble(dst, project_root: Path, echo: bool) -> None:
    """Write the START preamble to output."""
    project_name = project_root.name
    project_path = project_root.as_posix()
    preamble = f"START {project_name} ({project_path})\n{'=' * 80}\n\n"
    dst.write(preamble)
    if echo:
        sys.stderr.write(f"\033[92m{preamble}\033[0m")


def _write_end_marker(dst, project_root: Path, echo: bool) -> None:
    """Write the END marker to output."""
    end_marker = f"\n{'=' * 80}\nEND {project_root.as_posix()}\n"
    dst.write(end_marker)
    if echo:
        sys.stderr.write(f"\033[92m{end_marker}\033[0m")


def _build_repo_tree(
    repo_roots: list[Path],
    project_root: Path,
) -> tuple[list[str], int]:
    """
    Build a tree representation of discovered repositories.
    Returns (tree_lines, repo_count).
    """
    # Build directory structure
    tree: dict = {}
    for repo in repo_roots:
        try:
            rel = repo.relative_to(project_root)
        except ValueError:
            rel = repo
        parts = rel.parts if rel != Path(".") else (".",)
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
        current["__is_repo__"] = True

    def render_tree(node: dict, prefix: str = "", is_last: bool = True) -> list[str]:
        """Recursively render the tree structure."""
        lines = []
        items = [(k, v) for k, v in sorted(node.items()) if k != "__is_repo__"]
        for i, (name, subtree) in enumerate(items):
            is_last_item = (i == len(items) - 1)
            connector = "└─ " if is_last_item else "├─ "
            is_repo = subtree.get("__is_repo__", False)
            marker = "✓ repo" if is_repo else ""
            
            # Check if this is a directory (has children other than __is_repo__)
            has_children = any(k != "__is_repo__" for k in subtree.keys())
            suffix = "/" if has_children or (not is_repo and not has_children) else ""
            if is_repo and not has_children:
                suffix = "/"
            
            line = f"{prefix}{connector}{name}{suffix}"
            if marker:
                line = f"{line.ljust(40)} {marker}"
            lines.append(line)
            
            if has_children:
                extension = "   " if is_last_item else "│  "
                lines.extend(render_tree(subtree, prefix + extension, is_last_item))
        return lines

    # Special case: single repo at root
    if len(repo_roots) == 1 and repo_roots[0] == project_root:
        return [".                                        ✓ repo"], 1

    tree_lines = ["."]
    tree_lines.extend(render_tree(tree))
    return tree_lines, len(repo_roots)


def dump_repos(
    repo_roots: list[Path],
    out_file: Path,
    echo: bool,
    project_root: Path,
    depth: int,
) -> None:
    """Write the repository tree manifest (--zoom=repos)."""
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8") as dst:
            _write_preamble(dst, project_root, echo)

            header = f"📦 REPOSITORIES (depth={depth})\n\n"
            dst.write(header)
            if echo:
                sys.stderr.write(f"\033[93m{header}\033[0m")

            tree_lines, count = _build_repo_tree(repo_roots, project_root)
            tree_output = "\n".join(tree_lines) + "\n"
            dst.write(tree_output)
            if echo:
                sys.stderr.write(tree_output)

            summary = f"\nFound: {count} repositor{'y' if count == 1 else 'ies'}\n"
            dst.write(summary)
            if echo:
                sys.stderr.write(f"\033[92m{summary}\033[0m")

            _write_end_marker(dst, project_root, echo)

    except OSError as e:
        sys.exit(f"❌ Error writing to output file {out_file}: {e}")


def dump_files(
    files_to_dump: list[tuple[Path, Path]],
    out_file: Path,
    echo: bool,
    project_root: Path,
) -> None:
    """Write the file list manifest (--zoom=files)."""
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8") as dst:
            _write_preamble(dst, project_root, echo)

            header = f"📄 FILES (count={len(files_to_dump)})\n"
            dst.write(header)
            if echo:
                sys.stderr.write(f"\033[93m{header}\033[0m")

            for display_p, _ in files_to_dump:
                line = f"{display_p.as_posix()}\n"
                dst.write(line)
                if echo:
                    sys.stderr.write(line)

            _write_end_marker(dst, project_root, echo)

    except OSError as e:
        sys.exit(f"❌ Error writing to output file {out_file}: {e}")


def dump_contents(
    files_to_dump: list[tuple[Path, Path]],
    skipped_large: list[tuple[Path, int]],
    out_file: Path,
    echo: bool,
    size_kb: int,
    truncate_ipynb: bool,
    project_root: Path,
) -> None:
    """Write the full snapshot with file contents (--zoom=contents)."""
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8") as dst:
            _write_preamble(dst, project_root, echo)

            for i, (display_p, absolute_p) in enumerate(files_to_dump):
                posix_path = display_p.as_posix()
                sep = "" if i == 0 else "\n"
                banner = f"{sep}📄 FILE {posix_path}:\n"
                if echo:
                    sys.stderr.write(f"\033[93m{banner.strip()}\033[0m\n")

                dst.write(banner)

                try:
                    content = strip_ipynb(absolute_p) if absolute_p.suffix == ".ipynb" and truncate_ipynb else \
                              absolute_p.read_text(encoding="utf-8", errors="replace")
                except Exception as exc:
                    content = f"# ERROR reading {posix_path}: {exc}\n"
                    log.warning(content.strip())

                if content:
                    content = content.rstrip() + "\n"

                if echo:
                    sys.stderr.write(content)
                dst.write(content)

            _write_end_marker(dst, project_root, echo)

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


# Backward compatibility alias
dump = dump_contents