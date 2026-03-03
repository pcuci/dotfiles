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

log = logging.getLogger(__name__)

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
    project_top_level_path = Path.cwd()
    repo_name = project_top_level_path.name or "snapshot"
    default_out = Path(tempfile.gettempdir()) / f"{repo_name}-llm.txt"

    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    ap.add_argument(
        "-?", "--help", action="help",
        help="Show this help message and exit.",
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
        "-K", "--max-kb", type=int, default=config.DEFAULT_SIZE_KB, metavar="KB",
        help=f"Maximum file size in kilobytes (default: {config.DEFAULT_SIZE_KB} KB)",
    )
    ap.add_argument(
        "--only",
        nargs="+",
        metavar="PATTERN",
        help="Glob pattern(s) to select files, overriding defaults (e.g., '*.py' '**/*.js').",
    )
    ap.add_argument(
        "-e", "--exclude",
        nargs="+",
        metavar="PATTERN",
        help="Glob pattern(s) to exclude files. Adds to the default blocklist.",
    )
    ap.add_argument(
        "-a", "--allow",
        nargs="+",
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
        "-L", "--list", action="store_true",
        help="List matched files and exit instead of writing a snapshot.",
    )
    ap.add_argument(
        "-l", "--long", action="store_true",
        help="List matched files with size (similar to ls -l but without mtime).",
    )
    ap.add_argument(
        "--mtime", action="store_true",
        help="Include modified time column when using --long.",
    )
    ap.add_argument(
        "-h", "--human", action="store_true",
        help="Human-readable sizes when listing (e.g., 1.2K, 3.4M).",
    )
    sort_group = ap.add_mutually_exclusive_group()
    sort_group.add_argument(
        "--sort", choices=["name", "size", "mtime"], dest="sort",
        help="Sort order when listing files (default: name).",
    )
    sort_group.add_argument(
        "-t", dest="sort", action="store_const", const="mtime",
        help="Sort by modified time (like ls -t).",
    )
    sort_group.add_argument(
        "-S", dest="sort", action="store_const", const="size",
        help="Sort by size (like ls -S).",
    )
    ap.add_argument(
        "-k", "--tokens", action="store_true",
        help="When listing, show approximate token counts per file and total.",
    )
    ap.set_defaults(sort="name")
    ap.add_argument(
        "-r", "--reverse", action="store_true",
        help="Reverse sort order when listing.",
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
    def expand_short_bundles(argv: list[str]) -> list[str]:
        """
        Expand bundled short flags (e.g., -lrh -> -l -r -h) for flags that take no args.
        This keeps the UX closer to `ls` without forking to /bin/ls.
        """
        bundleable = {"l", "h", "r", "t", "S", "L", "k", "K"}
        expanded: list[str] = []
        stop = False
        for arg in argv:
            if stop or not arg.startswith("-") or arg == "-" or arg.startswith("--") or len(arg) <= 2:
                expanded.append(arg)
                if arg == "--":
                    stop = True
                continue
            chars = arg[1:]
            if all(c in bundleable for c in chars):
                expanded.extend([f"-{c}" for c in chars])
            else:
                expanded.append(arg)
        return expanded

    argv = expand_short_bundles(sys.argv[1:])
    return ap.parse_args(argv)

def main() -> int:
    """Main program entry point."""
    try:
        args = parse_args()
        setup_logging(args.quiet, args.verbose)

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
            exclude_patterns=args.exclude,
            allow_patterns=args.allow,
        )

        if not files_to_dump:
            log.error("❌ No files matched the inclusion criteria or size limits.")
            return 1

        if args.list or args.long:
            def size_bytes(p: Path) -> int:
                try:
                    return p.stat().st_size
                except OSError:
                    return -1

            def mtime(p: Path) -> float:
                try:
                    return p.stat().st_mtime
                except OSError:
                    return 0.0

            def fmt_size(bytes_val: int) -> str:
                if bytes_val < 0:
                    return "???"
                if args.human:
                    units = ["B", "K", "M", "G", "T"]
                    size = float(bytes_val)
                    for u in units:
                        if size < 1024 or u == units[-1]:
                            return f"{size:4.1f}{u}"
                        size /= 1024
                return f"{bytes_val:8d}"

            def fmt_mtime(p: Path) -> str:
                try:
                    ts = p.stat().st_mtime
                except OSError:
                    return "---------- --:--"
                from datetime import datetime
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

            def approx_tokens(text: str) -> int:
                # Rough heuristic: ~4 characters per token.
                return (len(text) + 3) // 4 if text else 0

            def file_tokens(p: Path) -> int:
                if not args.tokens:
                    return 0
                try:
                    if p.suffix == ".ipynb" and args.truncate_ipynb:
                        content = core.strip_ipynb(p)
                    else:
                        content = p.read_text(encoding="utf-8", errors="replace")
                    return approx_tokens(content)
                except Exception:
                    return 0

            key_funcs = {
                "name": lambda t: t[0].as_posix(),
                "size": lambda t: size_bytes(t[1]),
                "mtime": lambda t: mtime(t[1]),
            }
            key_func = key_funcs.get(args.sort, key_funcs["name"])
            sorted_files = sorted(files_to_dump, key=key_func, reverse=args.reverse)

            total_tokens = 0

            for display_p, abs_p in sorted_files:
                tokens = file_tokens(abs_p) if args.tokens else 0
                total_tokens += tokens

                if args.long:
                    sz = fmt_size(size_bytes(abs_p))
                    parts = [sz]
                    if args.mtime:
                        parts.append(fmt_mtime(abs_p))
                    if args.tokens:
                        parts.append(f"{tokens:8d}")
                    parts.append(display_p.as_posix())
                    sys.stdout.write(" ".join(parts) + "\n")
                else:
                    line = display_p.as_posix()
                    if args.tokens:
                        line = f"{tokens:8d} {line}"
                    sys.stdout.write(f"{line}\n")

            if skipped_large:
                sys.stdout.write(f"# Skipped {len(skipped_large)} file(s) larger than {args.max_kb} KB\n")
            if args.tokens:
                sys.stdout.write(f"# Estimated tokens (approx): {total_tokens}\n")
            return 0

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
            if not copy_file_to_clipboard(args.out, timeout_s=args.clipboard_timeout):
                # A hard failure from the clipboard module is a fatal error.
                log.error("❌ Clipboard operation failed. The snapshot file is at %s", args.out.resolve())
                return 1

        log.info(f"\n✅ Snapshot complete 🚀 {args.out.resolve()}")
        return 0

    except KeyboardInterrupt:
        print("\n🛑 Operation cancelled by user.", file=sys.stderr)
        return 130
    except Exception as e:
        logging.critical(f"\n💥 An unexpected error occurred: {e}", exc_info=True)
        return 1
