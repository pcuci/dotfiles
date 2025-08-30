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
from .clipboard import copy_to_clipboard

log = logging.getLogger(__name__)

def setup_logging(quiet: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)
    logging.getLogger("shutil").setLevel(logging.WARNING)

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
        "paths",
        nargs="*",
        type=Path,
        help="Paths to include (e.g., src/ tests/). If empty, scans the current directory.",
    )
    ap.add_argument(
        "-o", "--out", type=Path, default=default_out,
        help=f"Output file path (default: {default_out})",
    )
    ap.add_argument(
        "-k", "--max-kb", type=int, default=config.DEFAULT_SIZE_KB, metavar="KB",
        help=f"Maximum file size in kilobytes (default: {config.DEFAULT_SIZE_KB} KB)",
    )
    ap.add_argument(
        "--only",
        nargs="+",
        metavar="PATTERN",
        help="Glob pattern(s) to select files, overriding defaults (e.g., '*.py' '**/*.js').",
    )
    ap.add_argument(
        "--no-ipynb-truncate", action="store_false", dest="truncate_ipynb",
        help="Include Jupyter notebook outputs instead of stripping them.",
    )
    ap.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress all informational output (echos to stderr).",
    )
    ap.add_argument(
        "-c", "--clipboard", action="store_true",
        help="Copy the final snapshot content to the system clipboard.",
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
        setup_logging(args.quiet)

        project_top_level_path = Path.cwd().resolve()
        max_depth_scan = float("inf") if args.depth == -1 else args.depth

        log.info(f"🔍 Searching for Git repositories (max depth: {args.depth})...")
        repo_roots = core.find_git_repo_roots(project_top_level_path, max_depth_scan)

        if not repo_roots:
            log.error(f"❌ No Git repositories found within depth {args.depth} from {project_top_level_path}.")
            return 1

        log.info(f"ℹ️  Identified {len(repo_roots)} Git repository root(s) to scan.")
        log.info(f"🔍  Collecting files (max size: {args.max_kb} KB)...")

        files_to_dump, skipped_large = core.collect(
            repo_roots=repo_roots,
            size_kb=args.max_kb,
            project_root=project_top_level_path,
            paths=args.paths,
            only_patterns=args.only,
        )

        if not files_to_dump:
            log.error("❌ No files matched the inclusion criteria or size limits.")
            return 1

        log.info(f"✍️ Writing snapshot of {len(files_to_dump)} files to {args.out}...")
        core.dump(
            files_to_dump=files_to_dump,
            skipped_large=skipped_large,
            out_file=args.out,
            echo=not args.quiet,
            size_kb=args.max_kb,
            truncate_ipynb=args.truncate_ipynb,
        )

        if args.clipboard:
            if not copy_to_clipboard(args.out):
                log.warning(f"⚠️  Could not copy to clipboard. The snapshot is at {args.out.resolve()}")

        log.info(f"\n✅ Snapshot complete 🚀 {args.out.resolve()}")
        return 0

    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user.", file=sys.stderr)
        return 130
    except Exception as e:
        logging.critical(f"\n💥 An unexpected error occurred: {e}", exc_info=True)
        return 1
