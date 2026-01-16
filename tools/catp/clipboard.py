"""
clipboard.py — cross-platform clipboard helper with rich diagnostics.

Public API (backwards-compatible):
- copy_to_clipboard(file_path: Path) -> bool          # legacy name (wrapper)
- copy_file_to_clipboard(file_path: Path, ...) -> bool
- copy_text_to_clipboard(text: str, ...) -> bool

Supports:
- Windows / WSL (clip.exe, PowerShell Set-Clipboard)
- macOS (pbcopy)
- Linux Wayland (wl-copy --paste-once)
- Linux X11 (xsel preferred, xclip non-blocking with -loops 1)
- OSC52 terminal escape as last-resort (tmux/SSH-friendly)
"""

from __future__ import annotations
import base64
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List

log = logging.getLogger(__name__)

# ------------ Platform detection & environment helpers ------------

def is_wsl() -> bool:
    """True if running inside Windows Subsystem for Linux."""
    try:
        rel = platform.uname().release.lower()
    except Exception:
        rel = ""
    return "microsoft" in rel or "wsl" in rel or "WSL_DISTRO_NAME" in os.environ

def env_summary() -> str:
    keys = ["XDG_SESSION_TYPE", "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "SSH_CONNECTION", "WSL_DISTRO_NAME"]
    return "; ".join(f"{k}={os.environ.get(k, '')}" for k in keys)

def which(name: str) -> str | None:
    p = shutil.which(name)
    log.debug("which(%s) -> %s", name, p)
    return p

# ------------ Execution helpers ------------

def run_tool_with_file_input(cmd: list[str], file_path: Path, timeout_s: float) -> bool:
    """Run a clipboard command with stdin from a file; log results."""
    name = Path(cmd[0]).name
    log.debug("Running %s with stdin from %s (timeout=%.1fs)", cmd, file_path, timeout_s)
    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as f_in:
            p = subprocess.run(
                cmd,
                stdin=f_in,
                text=True,
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
    except subprocess.TimeoutExpired:
        log.warning("⚠️  %s timed out after %.1fs with input from %s.", name, timeout_s, file_path)
        return False
    except FileNotFoundError:
        log.debug("Not found: %s", name)
        return False
    except Exception as e:
        log.warning("⚠️  %s error with input from %s: %s", name, file_path, e)
        return False

    stderr = (p.stderr or "").strip()
    if p.returncode == 0:
        log.info("📋 Copied via %s from %s. Stderr: '%s'", name, file_path.name, stderr)
        return True

    if stderr:
        log.warning("⚠️  %s failed (exit %s). stderr: %s", name, p.returncode, stderr)
    else:
        log.warning("⚠️  %s failed (exit %s).", name, p.returncode)
    return False

def run_tool(cmd: List[str], content: str, timeout_s: float) -> bool:
    """Run a clipboard command with stdin content; for in-memory fallbacks."""
    name = Path(cmd[0]).name
    log.debug("Running %s with in-memory content (timeout=%.1fs)", cmd, timeout_s)
    try:
        p = subprocess.run(
            cmd,
            input=content,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log.warning("⚠️  %s timed out after %.1fs.", name, timeout_s)
        return False
    except FileNotFoundError:
        log.debug("Not found: %s", name)
        return False
    except Exception as e:
        log.warning("⚠️  %s error: %s", name, e)
        return False

    stderr = (p.stderr or "").strip()
    if p.returncode == 0:
        log.info("📋 Copied via %s (in-memory). Stderr: '%s'", name, stderr)
        return True

    if stderr:
        log.warning("⚠️  %s failed (exit %s). stderr: %s", name, p.returncode, stderr)
    else:
        log.warning("⚠️  %s failed (exit %s).", name, p.returncode)
    return False

def run_xclip_background(content: str) -> bool:
    """Non-blocking xclip requires in-memory content."""
    if not which("xclip"):
        log.debug("Not found: xclip")
        return False
    try:
        p = subprocess.Popen(
            ["xclip", "-selection", "clipboard", "-i", "-quiet", "-loops", "1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        assert p.stdin is not None
        p.stdin.write(content)
        p.stdin.close()
        log.info("📋 xclip started in background (exits after first paste).")
        return True
    except Exception as e:
        log.warning("⚠️  xclip spawn failed: %s", e)
        return False

def osc52_copy(text: str) -> bool:
    """OSC52 escape sequence requires in-memory content."""
    try:
        data = base64.b64encode(text.encode("utf-8")).decode("ascii")
        seq = f"\033]52;c;{data}\a"
        with open("/dev/tty", "w", encoding="utf-8", errors="ignore") as tty:
            tty.write(seq)
            tty.flush()
        log.info("📋 Copied via OSC52 (terminal clipboard).")
        return True
    except Exception as e:
        log.debug("OSC52 failed: %s", e)
        return False

# ------------ Public API ------------

def copy_text_to_clipboard(text: str, *, timeout_s: float = 10.0, enable_osc52: bool = True) -> bool:
    """Copy arbitrary text to the clipboard using in-memory methods."""
    os_name = platform.system()
    wsl = is_wsl()
    log.debug("copy_text_to_clipboard start: OS=%s WSL=%s env: %s", os_name, wsl, env_summary())

    if os_name == "Windows" or (os_name == "Linux" and wsl):
        if which("clip.exe") and run_tool(["clip.exe"], text, timeout_s):
            return True
        if which("powershell.exe"):
            ps_cmd = "Set-Clipboard -Value $input"
            if run_tool(["powershell.exe", "-NoProfile", "-Command", ps_cmd], text, timeout_s):
                return True

    if os_name == "Darwin":
        if which("pbcopy") and run_tool(["pbcopy"], text, timeout_s):
            return True

    if os.environ.get("WAYLAND_DISPLAY"):
        wl = which("wl-copy")
        if not wl:
            log.error("❌ Wayland session detected, but 'wl-copy' is not installed.")
            return False
        if run_tool([wl, "--paste-once"], text, timeout_s):
            return True

    if os_name == "Linux" and not os.environ.get("WAYLAND_DISPLAY"):
        if which("xsel") and run_tool(["xsel", "--clipboard", "--input"], text, timeout_s):
            return True
        if run_xclip_background(text):
            return True

    if enable_osc52 and osc52_copy(text):
        return True

    log.warning("⚠️  All in-memory clipboard strategies failed.")
    return False

def copy_file_to_clipboard(file_path: Path, *, timeout_s: float = 10.0, enable_osc52: bool = True) -> bool:
    """
    Copy a file to the clipboard, preferring efficient file-based piping.
    Falls back to in-memory methods if needed.
    """
    os_name = platform.system()
    log.debug("copy_file_to_clipboard start: attempting efficient file-pipe for %s", file_path)

    if os.environ.get("WAYLAND_DISPLAY"):
        wl = which("wl-copy")
        if not wl:
            log.error("❌ Wayland session detected, but 'wl-copy' is not installed.")
            log.error("   Please install it via your package manager (e.g., 'sudo apt install wl-clipboard').")
            return False
        if run_tool_with_file_input([wl, "--paste-once"], file_path, timeout_s):
            return True

    # --- Strategy 1: Fast, file-based piping for other native tools ---
    if os_name == "Windows" or is_wsl():
        if which("clip.exe") and run_tool_with_file_input(["clip.exe"], file_path, timeout_s):
            return True

    if os_name == "Darwin":
        if which("pbcopy") and run_tool_with_file_input(["pbcopy"], file_path, timeout_s):
            return True

    if os_name == "Linux" and not os.environ.get("WAYLAND_DISPLAY"):
        if which("xsel") and run_tool_with_file_input(["xsel", "--clipboard", "--input"], file_path, timeout_s):
            return True

    # --- Strategy 2: Fallback to in-memory for remaining tools ---
    log.debug("File-based copy failed or not applicable, falling back to in-memory.")
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        log.warning("⚠️  Cannot read %s for fallback copy: %s", file_path, e)
        return False
    
    return copy_text_to_clipboard(content, timeout_s=timeout_s, enable_osc52=enable_osc52)

# ---- Legacy name (backwards compatibility) ----
def copy_to_clipboard(file_path: Path) -> bool:
    """Legacy wrapper kept for compatibility with older imports."""
    return copy_file_to_clipboard(file_path)

# ------------ CLI (optional) ------------
if __name__ == "__main__":
    import argparse, sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Copy text or a file's contents to the clipboard.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("-t", "--text", help="Raw text to copy")
    g.add_argument("-f", "--file", type=Path, help="Path to a UTF-8 text file to copy")
    ap.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    ap.add_argument("--no-osc52", action="store_true", help="Disable OSC52 fallback")
    ap.add_argument("--timeout", type=float, default=10.0, help="Per-tool timeout seconds")
    args = ap.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    ok = False
    if args.text is not None:
        ok = copy_text_to_clipboard(args.text, timeout_s=args.timeout, enable_osc52=not args.no_osc52)
    elif args.file is not None:
        ok = copy_file_to_clipboard(args.file, timeout_s=args.timeout, enable_osc52=not args.no_osc52)

    if not ok:
        log.error("Failed to copy to clipboard.")
        sys.exit(1)
