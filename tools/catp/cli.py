#!/usr/bin/env python3
"""
Command-Line Interface for the catp snapshot tool.
Handles argument parsing and orchestrates the application flow.
"""
import argparse
import logging
import sys
import tempfile
from pathlib import Path

from . import config, core
from .clipboard import copy_file_to_clipboard
from .config import ZoomLevel

log = logging.getLogger(__name__)


def get_default_output_path(repo_name: str, zoom: ZoomLevel) -> Path:
    """Get the default output path based on zoom level."""
    suffix_map = {
        ZoomLevel.REPOS: "-repos.txt",
        ZoomLevel.FILES: "-files.txt",
        ZoomLevel.CONTENTS: "-llm.txt",
    }
    return Path(tempfile.gettempdir()) / f"{repo_name}{suffix_map[zoom]}"


def setup_logging(quiet: bool, verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.INFO
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)
    logging.getLogger("shutil").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Paths to include (e.g., src/ tests/). If empty, scans the current directory.",
    )
    ap.add_argument(
        "-z", "--zoom",
        type=str,
        choices=[z.value for z in ZoomLevel],
        default=ZoomLevel.CONTENTS.value,
        help="Resolution level: repos (tree), files (list), contents (full snapshot, default).",
    )
    ap.add_argument(
        "-o", "--out", type=Path, default=None,
        help="Output file path (default: /tmp/<project>-{repos,files,llm}.txt based on zoom).",
    )
    ap.add_argument(
        "-k", "--max-kb", type=int, default=config.DEFAULT_SIZE_KB, metavar="KB",
        help=f"Maximum file size in kilobytes (default: {config.DEFAULT_SIZE_KB} KB)",
    )
    ap.add_argument(
        "--only",
        action="extend",
        nargs="+",
        default=[],
        metavar="PATTERN",
        help="Glob pattern(s) to include (OR logic). Repeatable: --only 'backend*' --only frontend",
    )
    ap.add_argument(
        "-e", "--exclude",
        action="extend",
        nargs="+",
        default=[],
        metavar="PATTERN",
        help="Glob pattern(s) to exclude (OR logic). Repeatable. Adds to the default blocklist.",
    )
    ap.add_argument(
        "-a", "--allow",
        action="extend",
        nargs="+",
        default=[],
        metavar="PATTERN",
        help="Disables a default exclusion pattern. Must be paired with an inclusion flag like --only.",
    )
    ap.add_argument(
        "--no-ipynb-truncate", action="store_false", dest="truncate_ipynb",
        help="Include Jupyter notebook outputs instead of stripping them.",
    )
    verbosity = ap.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress all informational output (echos to stderr).",
    )
    verbosity.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable detailed logging of file filtering decisions.",
    )
    ap.add_argument(
        "-c", "--clipboard", action="store_true",
        help="Copy the final snapshot content to the system clipboard.",
    )
    ap.add_argument(
        "--clipboard-timeout", type=float, default=10.0, metavar="SECONDS",
        help="Timeout for clipboard copy operations (default: 10.0s).",
    )
    ap.add_argument(
        "-d", "--depth", type=int, default=0, metavar="N",
        help="Scan for Git repositories up to N levels deep (-1 for infinite).",
    )
    return ap.parse_args()

def main() -> int:
    """Main program entry point."""
    try:
        args = parse_args()
        setup_logging(args.quiet, args.verbose)

        project_top_level_path = Path.cwd().resolve()
        max_depth_scan = float("inf") if args.depth == -1 else args.depth
        zoom = ZoomLevel(args.zoom)

        # Resolve output path based on zoom level if not explicitly provided
        if args.out is None:
            repo_name = project_top_level_path.name or "snapshot"
            out_file = get_default_output_path(repo_name, zoom)
        else:
            out_file = args.out

        log.info(f"🔍 Searching for Git repositories (max depth: {args.depth})...")
        repo_roots = core.find_git_repo_roots(
            start_path=project_top_level_path,
            max_depth=max_depth_scan,
            only_patterns=args.only,
            exclude_patterns=args.exclude,
        )

        if not repo_roots:
            log.error(f"❌ No Git repositories found within depth {args.depth} from {project_top_level_path}.")
            return 1

        log.info(f"ℹ️  Identified {len(repo_roots)} Git repository root(s) to scan.")

        # --- ZOOM: repos ---
        if zoom == ZoomLevel.REPOS:
            log.info(f"✍️ Writing repository manifest to {out_file}...")
            core.dump_repos(
                repo_roots=repo_roots,
                out_file=out_file,
                echo=not args.quiet,
                project_root=project_top_level_path,
                depth=args.depth,
            )

        # --- ZOOM: files ---
        elif zoom == ZoomLevel.FILES:
            log.info(f"🔍  Collecting files (max size: {args.max_kb} KB)...")
            files_to_dump, _ = core.collect(
                repo_roots=repo_roots,
                size_kb=args.max_kb,
                project_root=project_top_level_path,
                paths=args.paths,
                only_patterns=args.only,
                exclude_patterns=args.exclude,
                allow_patterns=args.allow,
            )

            if not files_to_dump:
                log.error("❌ No files matched the inclusion criteria or size limits.")
                return 1

            log.info(f"✍️ Writing file manifest ({len(files_to_dump)} files) to {out_file}...")
            core.dump_files(
                files_to_dump=files_to_dump,
                out_file=out_file,
                echo=not args.quiet,
                project_root=project_top_level_path,
            )

        # --- ZOOM: contents (default) ---
        else:
            log.info(f"🔍  Collecting files (max size: {args.max_kb} KB)...")
            files_to_dump, skipped_large = core.collect(
                repo_roots=repo_roots,
                size_kb=args.max_kb,
                project_root=project_top_level_path,
                paths=args.paths,
                only_patterns=args.only,
                exclude_patterns=args.exclude,
                allow_patterns=args.allow,
            )

            if not files_to_dump:
                log.error("❌ No files matched the inclusion criteria or size limits.")
                return 1

            log.info(f"✍️ Writing snapshot of {len(files_to_dump)} files to {out_file}...")
            core.dump_contents(
                files_to_dump=files_to_dump,
                skipped_large=skipped_large,
                out_file=out_file,
                echo=not args.quiet,
                size_kb=args.max_kb,
                truncate_ipynb=args.truncate_ipynb,
                project_root=project_top_level_path,
            )

        # Clipboard works at all zoom levels
        if args.clipboard:
            if not copy_file_to_clipboard(out_file, timeout_s=args.clipboard_timeout):
                log.error("❌ Clipboard operation failed. The snapshot file is at %s", out_file.resolve())
                return 1

        log.info(f"\n✅ Snapshot complete 🚀 {out_file.resolve()}")
        return 0

    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user.", file=sys.stderr)
        return 130
    except Exception as e:
        logging.critical(f"\n💥 An unexpected error occurred: {e}", exc_info=True)
        return 1
