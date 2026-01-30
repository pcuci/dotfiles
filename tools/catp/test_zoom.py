"""
Tests for catp --zoom functionality and unified filtering.

Justification: Praxis/Wisdom - Evidence-based verification of core functionality.
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from .config import ZoomLevel
from .core import (
    _build_repo_tree,
    dump_contents,
    dump_files,
    dump_repos,
    find_git_repo_roots,
    matches_path,
    should_exclude_subtree,
)


class TestZoomLevel:
    """Tests for ZoomLevel enum."""

    def test_zoom_level_values(self):
        """Verify zoom level values match CLI expectations."""
        assert ZoomLevel.REPOS.value == "repos"
        assert ZoomLevel.FILES.value == "files"
        assert ZoomLevel.CONTENTS.value == "contents"

    def test_zoom_level_from_string(self):
        """Verify zoom levels can be created from strings."""
        assert ZoomLevel("repos") == ZoomLevel.REPOS
        assert ZoomLevel("files") == ZoomLevel.FILES
        assert ZoomLevel("contents") == ZoomLevel.CONTENTS


class TestMatchesPath:
    """Tests for unified path matching."""

    def test_simple_extension_pattern(self):
        """Simple patterns match any component."""
        assert matches_path(Path("src/main.py"), {"*.py"})
        assert matches_path(Path("deep/nested/file.ts"), {"*.ts"})
        assert not matches_path(Path("src/main.py"), {"*.js"})

    def test_path_pattern_with_slash(self):
        """Patterns with '/' match full path."""
        assert matches_path(Path("clients/acme/infra"), {"clients/**"})
        assert matches_path(Path("clients/acme/infra/main.tf"), {"clients/acme/**"})
        assert not matches_path(Path("platform/catp"), {"clients/**"})

    def test_double_star_pattern(self):
        """Double-star patterns match recursively."""
        assert matches_path(Path("a/b/c/d.py"), {"**/*.py"})
        assert matches_path(Path("tests/unit/test_foo.py"), {"tests/**"})

    def test_directory_name_pattern(self):
        """Directory name patterns match components."""
        assert matches_path(Path("src/node_modules/pkg"), {"node_modules"})
        assert matches_path(Path("deep/vendor/lib"), {"vendor"})


class TestShouldExcludeSubtree:
    """Tests for subtree pruning."""

    def test_subtree_pattern(self):
        """Patterns ending with /** trigger pruning."""
        assert should_exclude_subtree(Path("clients"), {"clients/**"})
        assert should_exclude_subtree(Path("clients/acme"), {"clients/**"})
        assert not should_exclude_subtree(Path("platform"), {"clients/**"})

    def test_exact_match(self):
        """Exact directory matches are pruned."""
        assert should_exclude_subtree(Path("vendor"), {"vendor"})
        assert should_exclude_subtree(Path("node_modules"), {"node_modules"})


class TestFindGitRepoRoots:
    """Tests for repository discovery with filtering."""

    def test_find_single_repo(self, tmp_path):
        """Find a single repo at root."""
        (tmp_path / ".git").mkdir()
        repos = find_git_repo_roots(tmp_path, max_depth=0)
        assert len(repos) == 1
        assert repos[0] == tmp_path

    def test_find_nested_repos(self, tmp_path):
        """Find nested repos with depth."""
        (tmp_path / ".git").mkdir()
        nested = tmp_path / "sub" / "repo"
        nested.mkdir(parents=True)
        (nested / ".git").mkdir()

        repos = find_git_repo_roots(tmp_path, max_depth=3)
        assert len(repos) == 2
        assert tmp_path in repos
        assert nested in repos

    def test_exclude_filters_repos(self, tmp_path):
        """--exclude filters out repos."""
        (tmp_path / ".git").mkdir()
        excluded = tmp_path / "vendor" / "lib"
        excluded.mkdir(parents=True)
        (excluded / ".git").mkdir()

        repos = find_git_repo_roots(
            tmp_path, max_depth=3, exclude_patterns=["vendor/**"]
        )
        assert len(repos) == 1
        assert tmp_path in repos
        assert excluded not in repos

    def test_only_filters_repos(self, tmp_path):
        """--only filters repos to match patterns."""
        (tmp_path / ".git").mkdir()
        wanted = tmp_path / "clients" / "acme"
        wanted.mkdir(parents=True)
        (wanted / ".git").mkdir()
        unwanted = tmp_path / "platform" / "tools"
        unwanted.mkdir(parents=True)
        (unwanted / ".git").mkdir()

        repos = find_git_repo_roots(
            tmp_path, max_depth=3, only_patterns=["clients/**"]
        )
        # Root repo is always included if it matches
        # Here we filter to only clients/**
        assert wanted in repos
        assert unwanted not in repos

    def test_subtree_pruning(self, tmp_path):
        """Excluded subtrees are not descended into."""
        (tmp_path / ".git").mkdir()
        deep = tmp_path / "excluded" / "deep" / "repo"
        deep.mkdir(parents=True)
        (deep / ".git").mkdir()

        # Without exclude, we'd find both
        repos_all = find_git_repo_roots(tmp_path, max_depth=5)
        assert len(repos_all) == 2

        # With exclude, subtree is pruned
        repos_filtered = find_git_repo_roots(
            tmp_path, max_depth=5, exclude_patterns=["excluded/**"]
        )
        assert len(repos_filtered) == 1
        assert tmp_path in repos_filtered


class TestBuildRepoTree:
    """Tests for repository tree rendering."""

    def test_single_repo_at_root(self, tmp_path):
        """Single repo at root renders correctly."""
        lines, count = _build_repo_tree([tmp_path], tmp_path)
        assert count == 1
        assert "✓ repo" in lines[0]

    def test_nested_repos_tree(self, tmp_path):
        """Nested repos render as tree."""
        repo1 = tmp_path / "platform" / "catp"
        repo2 = tmp_path / "clients" / "acme"
        repo1.mkdir(parents=True)
        repo2.mkdir(parents=True)

        lines, count = _build_repo_tree([repo1, repo2], tmp_path)
        assert count == 2
        tree_text = "\n".join(lines)
        assert "platform" in tree_text
        assert "clients" in tree_text
        assert "catp" in tree_text
        assert "acme" in tree_text


class TestDumpRepos:
    """Tests for --zoom=repos output."""

    def test_dump_repos_creates_file(self, tmp_path):
        """dump_repos creates output file with correct format."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        out_file = tmp_path / "output.txt"

        dump_repos(
            repo_roots=[project_root],
            out_file=out_file,
            echo=False,
            project_root=project_root,
            depth=0,
        )

        content = out_file.read_text()
        assert "START project" in content
        assert "📦 REPOSITORIES" in content
        assert "END" in content
        assert "Found: 1 repository" in content


class TestDumpFiles:
    """Tests for --zoom=files output."""

    def test_dump_files_creates_file(self, tmp_path):
        """dump_files creates output file with correct format."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        out_file = tmp_path / "output.txt"

        files = [
            (Path("src/main.py"), project_root / "src" / "main.py"),
            (Path("tests/test_main.py"), project_root / "tests" / "test_main.py"),
        ]

        dump_files(
            files_to_dump=files,
            out_file=out_file,
            echo=False,
            project_root=project_root,
        )

        content = out_file.read_text()
        assert "START project" in content
        assert "📄 FILES (count=2)" in content
        assert "src/main.py" in content
        assert "tests/test_main.py" in content
        assert "END" in content


class TestDumpContents:
    """Tests for --zoom=contents output."""

    def test_dump_contents_creates_file(self, tmp_path):
        """dump_contents creates output file with file contents."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        src_dir = project_root / "src"
        src_dir.mkdir()

        # Create a test file
        test_file = src_dir / "main.py"
        test_file.write_text("print('hello')\n")

        out_file = tmp_path / "output.txt"
        files = [(Path("src/main.py"), test_file)]

        dump_contents(
            files_to_dump=files,
            skipped_large=[],
            out_file=out_file,
            echo=False,
            size_kb=400,
            truncate_ipynb=True,
            project_root=project_root,
        )

        content = out_file.read_text()
        assert "START project" in content
        assert "📄 FILE src/main.py:" in content
        assert "print('hello')" in content
        assert "END" in content

    def test_dump_contents_skipped_large_footer(self, tmp_path):
        """dump_contents includes skipped files footer."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        out_file = tmp_path / "output.txt"

        dump_contents(
            files_to_dump=[],
            skipped_large=[(Path("large.bin"), 1024)],
            out_file=out_file,
            echo=False,
            size_kb=400,
            truncate_ipynb=True,
            project_root=project_root,
        )

        content = out_file.read_text()
        assert "Skipped 1 file(s)" in content
        assert "large.bin" in content


class TestOnlyOrSemantics:
    """Tests for --only OR semantics (critical: repeated --only must accumulate)."""

    def test_multiple_only_patterns_are_or(self, tmp_path):
        """Multiple --only patterns use OR logic."""
        # Create repos: backend, backend-base, frontend (no root repo)
        # This simulates: cd /workspace && catp --only "backend*" --only frontend
        backend = tmp_path / "backend"
        backend.mkdir()
        (backend / ".git").mkdir()
        backend_base = tmp_path / "backend-base"
        backend_base.mkdir()
        (backend_base / ".git").mkdir()
        frontend = tmp_path / "frontend"
        frontend.mkdir()
        (frontend / ".git").mkdir()
        # Also add an unrelated repo that should NOT match
        unrelated = tmp_path / "unrelated"
        unrelated.mkdir()
        (unrelated / ".git").mkdir()

        # --only "backend*" --only "frontend" should match backend, backend-base, frontend
        repos = find_git_repo_roots(
            tmp_path,
            max_depth=1,
            only_patterns=["backend*", "frontend"],
        )

        # Should find exactly 3 repos (backend, backend-base, frontend), NOT unrelated
        repo_names = {r.name for r in repos}
        assert "backend" in repo_names
        assert "backend-base" in repo_names
        assert "frontend" in repo_names
        assert "unrelated" not in repo_names
        assert len(repos) == 3

    def test_only_patterns_combined_with_exclude(self, tmp_path):
        """--only OR with --exclude still works (exclude is subtractive)."""
        backend = tmp_path / "backend"
        backend.mkdir()
        (backend / ".git").mkdir()
        backend_base = tmp_path / "backend-base"
        backend_base.mkdir()
        (backend_base / ".git").mkdir()
        frontend = tmp_path / "frontend"
        frontend.mkdir()
        (frontend / ".git").mkdir()

        # --only "backend*" --only "frontend" --exclude "backend-base"
        repos = find_git_repo_roots(
            tmp_path,
            max_depth=1,
            only_patterns=["backend*", "frontend"],
            exclude_patterns=["backend-base"],
        )

        repo_names = {r.name for r in repos}
        assert "backend" in repo_names
        assert "frontend" in repo_names
        assert "backend-base" not in repo_names
        assert len(repos) == 2

    def test_cli_accumulates_only_patterns(self):
        """Verify argparse accumulates repeated --only flags."""
        from .cli import parse_args
        import sys
        
        # Simulate: catp --only "backend*" --only frontend
        old_argv = sys.argv
        try:
            sys.argv = ["catp", "--only", "backend*", "--only", "frontend"]
            args = parse_args()
            assert "backend*" in args.only
            assert "frontend" in args.only
            assert len(args.only) == 2
        finally:
            sys.argv = old_argv


class TestExcludeOrSemantics:
    """Tests for --exclude OR semantics (critical: repeated --exclude must accumulate)."""

    def test_multiple_exclude_patterns_are_or(self, tmp_path):
        """Multiple --exclude patterns use OR logic."""
        # Create repos: backend, backend-base, frontend, other
        for name in ["backend", "backend-base", "frontend", "other"]:
            repo = tmp_path / name
            repo.mkdir()
            (repo / ".git").mkdir()

        # --exclude "backend*" --exclude "frontend" should remove backend, backend-base, frontend
        repos = find_git_repo_roots(
            tmp_path,
            max_depth=1,
            exclude_patterns=["backend*", "frontend"],
        )

        # Should find only "other"
        repo_names = {r.name for r in repos}
        assert "other" in repo_names
        assert "backend" not in repo_names
        assert "backend-base" not in repo_names
        assert "frontend" not in repo_names
        assert len(repos) == 1

    def test_exclude_with_glob_pattern(self, tmp_path):
        """Glob patterns in --exclude work correctly."""
        for name in ["api-service", "api-gateway", "web-app", "cli-tool"]:
            repo = tmp_path / name
            repo.mkdir()
            (repo / ".git").mkdir()

        # --exclude "api-*" should remove api-service, api-gateway
        repos = find_git_repo_roots(
            tmp_path,
            max_depth=1,
            exclude_patterns=["api-*"],
        )

        repo_names = {r.name for r in repos}
        assert "web-app" in repo_names
        assert "cli-tool" in repo_names
        assert "api-service" not in repo_names
        assert "api-gateway" not in repo_names
        assert len(repos) == 2

    def test_cli_accumulates_exclude_patterns(self):
        """Verify argparse accumulates repeated --exclude flags."""
        from .cli import parse_args
        import sys
        
        old_argv = sys.argv
        try:
            sys.argv = ["catp", "--exclude", "backend*", "--exclude", "frontend"]
            args = parse_args()
            assert "backend*" in args.exclude
            assert "frontend" in args.exclude
            assert len(args.exclude) == 2
        finally:
            sys.argv = old_argv

    def test_exclude_prunes_subtree_traversal(self, tmp_path):
        """Excluded directories should not be descended into (performance)."""
        # Create: excluded/deep/nested/repo
        deep = tmp_path / "excluded" / "deep" / "nested"
        deep.mkdir(parents=True)
        (deep / ".git").mkdir()
        
        # Create: kept/repo  
        kept = tmp_path / "kept"
        kept.mkdir()
        (kept / ".git").mkdir()

        # --exclude "excluded/**" should prune the entire subtree
        repos = find_git_repo_roots(
            tmp_path,
            max_depth=5,
            exclude_patterns=["excluded/**"],
        )

        repo_names = {r.name for r in repos}
        assert "kept" in repo_names
        assert "nested" not in repo_names
        assert len(repos) == 1

    def test_exclude_exact_match(self, tmp_path):
        """Exact directory names can be excluded."""
        for name in ["vendor", "node_modules", "src"]:
            repo = tmp_path / name
            repo.mkdir()
            (repo / ".git").mkdir()

        repos = find_git_repo_roots(
            tmp_path,
            max_depth=1,
            exclude_patterns=["vendor", "node_modules"],
        )

        repo_names = {r.name for r in repos}
        assert "src" in repo_names
        assert "vendor" not in repo_names
        assert "node_modules" not in repo_names
        assert len(repos) == 1


class TestOutputNaming:
    """Tests for default output file naming."""

    def test_repos_output_suffix(self):
        """--zoom=repos uses -repos.txt suffix."""
        from .cli import get_default_output_path

        path = get_default_output_path("myproject", ZoomLevel.REPOS)
        assert path.name == "myproject-repos.txt"

    def test_files_output_suffix(self):
        """--zoom=files uses -files.txt suffix."""
        from .cli import get_default_output_path

        path = get_default_output_path("myproject", ZoomLevel.FILES)
        assert path.name == "myproject-files.txt"

    def test_contents_output_suffix(self):
        """--zoom=contents uses -llm.txt suffix."""
        from .cli import get_default_output_path

        path = get_default_output_path("myproject", ZoomLevel.CONTENTS)
        assert path.name == "myproject-llm.txt"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
