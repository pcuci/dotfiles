#!/usr/bin/env python3
"""
repo-sync.py – re-implements the CI “sync” stage locally
==========================================================
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

# --------------------------------------------------------------------------- #
# Helper utilities                                                            #
# --------------------------------------------------------------------------- #
def run(cmd: List[str], *, check: bool = True, capture: bool = False, cwd: Path | None = None) -> str:
    """Run a git (or shell) command and return stdout (stripped)."""
    if capture:
        return subprocess.check_output(cmd, text=True, cwd=cwd).strip()
    subprocess.run(cmd, check=check, cwd=cwd, text=True)
    return ""

def git(*args: str, capture: bool = False) -> str:
    return run(["git", *args], capture=capture)

def inside_repo() -> bool:
    try:
        git("rev-parse", "--is-inside-work-tree")
        return True
    except subprocess.CalledProcessError:
        return False

def branch_list(refspace: str) -> List[str]:
    fmt = "%(refname:strip=3)"
    out = git("for-each-ref", "--format", fmt, refspace, capture=True)
    return [b for b in out.splitlines() if b and b != "HEAD"]

def has_upstream(branch: str) -> bool:
    try:
        git("show-ref", "--quiet", f"refs/remotes/github/{branch}")
        return True
    except subprocess.CalledProcessError:
        return False

def branch_changed(branch: str) -> bool:
    try:
        git("log", f"origin/{branch}..HEAD", "--oneline", capture=True)
        return True
    except subprocess.CalledProcessError:
        return False

# --------------------------------------------------------------------------- #
# Core sync logic                                                             #
# --------------------------------------------------------------------------- #
class Plan:
    def __init__(self) -> None:
        self.push_cmds: List[str] = []

    def enqueue(self, cmd: str) -> None:
        self.push_cmds.append(cmd)

    def empty(self) -> bool:
        return not self.push_cmds

    # printing                                                                  #
    def show(self) -> None:
        if self.empty():
            print("🎉  Everything already in sync – no pushes required.")
            return
        print("\n🚀  The following commands would be executed:")
        for c in self.push_cmds:
            print(f"   {c}")

    # execution                                                                 #
    def apply(self) -> None:
        if self.empty():
            print("Nothing to do.")
            return
        for c in self.push_cmds:
            print(f"▶  {c}")
            run(c.split())

# --------------------------------------------------------------------------- #
def build_plan() -> Plan:
    plan = Plan()
    print("📡  Fetching remotes and tags...")
    git("fetch", "origin", "--tags")
    git("fetch", "github")

    for branch in branch_list("refs/remotes/origin"):
        print(f"\n===  🛰️  {branch}  ===")
        git("checkout", "-B", branch, f"origin/{branch}")

        if not has_upstream(branch):
            print(f"🔕  github/{branch} not found — skipping")
            continue

        print("🔀  Rebasing...")
        base = git("merge-base", branch, f"github/{branch}", capture=True)
        try:
            git("rebase", "--onto", f"github/{branch}", base, branch)
        except subprocess.CalledProcessError:
            print(f"❌  Rebase conflict on {branch} – aborting plan.")
            sys.exit(2)

        # tag handling
        last_tag = ""
        try:
            last_tag = git("describe", "--tags", "--abbrev=0", f"origin/{branch}", capture=True)
        except subprocess.CalledProcessError:
            pass  # no tag

        tag_moved = False
        if last_tag:
            old_sha = git("rev-list", "-n", "1", last_tag, capture=True)
            try:
                git("merge-base", "--is-ancestor", old_sha, "HEAD")
                print(f"✅  Tag {last_tag} still reachable")
            except subprocess.CalledProcessError:
                print(f"🪄  Tag {last_tag} moved")
                base_sha = git("merge-base", "HEAD", f"github/{branch}", capture=True)
                git("tag", "-f", last_tag, base_sha)
                tag_moved = True

        if branch_changed(branch):
            plan.enqueue(f"git push origin {branch} --force-with-lease")
            plan.enqueue(f"git push github {branch} --force")

        if tag_moved:
            plan.enqueue(f"git push origin {last_tag} --force -o ci.skip")

    return plan

# --------------------------------------------------------------------------- #
def main() -> None:
    if not inside_repo():
        print("❌  sync-repo.py must be run inside a Git repository.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Preview / apply Git sync operations.")
    parser.add_argument("-f", "--skip-preview", action="store_true",
                        help="Skip preview and run immediately.")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Auto-approve after preview (like Pulumi -y).")
    args = parser.parse_args()

    plan = build_plan()

    # Decide execution flow
    if args.skip_preview:
        print("⚠️  --skip-preview supplied – running without showing plan.")
        plan.apply()
        return

    # Regular preview
    print("\n================  PLAN  ================")
    plan.show()
    print("========================================\n")

    if plan.empty():
        return  # all good

    if args.yes:
        print("👍  --yes supplied – applying automatically.\n")
        plan.apply()
        return

    # interactive prompt
    reply = input("Proceed with these actions? [y/N] ").strip().lower()
    if reply in {"y", "yes"}:
        plan.apply()
    else:
        print("ℹ️  Cancelled – nothing changed.")

# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()