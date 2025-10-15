"""
clipboard.py — cross-platform clipboard helper with rich diagnostics.

Public API (backwards-compatible):
- copy_to_clipboard(file_path: Path) -> bool          # legacy name (wrapper)
- copy_file_to_clipboard(file_path: Path, ...) -> bool
- copy_text_to_clipboard(text: str, ...) -> bool

Supports:
- Windows / WSL (clip.exe, PowerShell Set-Clipboard)
- macOS (pbcopy)
- Linux Wayland (wl-copy)
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
from typing import List, Tuple

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

def fix_display_env() -> None:
    """
    Best-effort local X11 defaults when DISPLAY is bogus (Linux native only).
    Skips on WSL (use Windows clipboard) and when Wayland is present.
    """
    if platform.system() != "Linux" or is_wsl():
        return
    if os.environ.get("WAYLAND_DISPLAY"):
        return

    disp = os.environ.get("DISPLAY", "")
    if (not disp) or disp.startswith("127."):
        os.environ["DISPLAY"] = ":0"
        log.debug("Set DISPLAY=:0 (auto-fix)")

    os.environ.setdefault("XAUTHORITY", str(Path.home() / ".Xauthority"))

    # Try to allow local user once; ignore errors.
    if shutil.which("xhost") and os.environ.get("DISPLAY", "").startswith(":"):
        try:
            user = os.environ.get("USER") or os.environ.get("LOGNAME", "")
            if user:
                subprocess.run(
                    ["xhost", f"+SI:localuser:{user}"],
                    check=False, capture_output=True, text=True, timeout=3
                )
        except Exception as e:
            log.debug("xhost probe failed: %s", e)

def can_use_xclip() -> Tuple[bool, str]:
    disp = os.environ.get("DISPLAY", "")
    if not disp:
        return False, "DISPLAY is empty"
    if disp.startswith("127."):
        return False, f"DISPLAY looks wrong: {disp}"
    if disp.startswith(":"):
        # Validate socket for :0, :1, ...
        idx = disp.split(":", 1)[1]
        idx = idx.split(".", 1)[0]  # :0.0 -> 0
        sock = f"/tmp/.X11-unix/X{idx}"
        if not os.path.exists(sock):
            return False, f"X socket missing: {sock}"
    return True, "DISPLAY looks usable"

def which(name: str) -> str | None:
    p = shutil.which(name)
    log.debug("which(%s) -> %s", name, p)
    return p

# ------------ Execution helpers ------------

def run_tool(cmd: List[str], content: str, timeout_s: float) -> bool:
    """Run a clipboard command with stdin content and timeout; log results."""
    name = Path(cmd[0]).name
    log.debug("Running %s (timeout=%.1fs) with env: %s", cmd, timeout_s, env_summary())
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
        log.warning("⚠️  Not found: %s", name)
        return False
    except Exception as e:
        log.warning("⚠️  %s error: %s", name, e)
        return False

    if p.returncode == 0:
        log.info("📋 Copied via %s.", name)
        return True

    stderr = (p.stderr or "").strip()
    if stderr:
        log.warning("⚠️  %s failed (exit %s). stderr: %s", name, p.returncode, stderr)
    else:
        log.warning("⚠️  %s failed (exit %s).", name, p.returncode)
    return False

def run_xclip_background(content: str) -> bool:
    """
    Non-blocking xclip: keep data for one paste and return immediately.
    Requires a sane DISPLAY/XAUTHORITY; we verify before spawning.
    """
    ok, why = can_use_xclip()
    log.debug("xclip guard: ok=%s, why=%s", ok, why)
    if not ok:
        log.warning("xclip skipped: %s", why)
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
    except FileNotFoundError:
        log.warning("⚠️  Not found: xclip")
        return False
    except Exception as e:
        log.warning("⚠️  xclip spawn failed: %s", e)
        return False

# ------------ OSC52 fallback ------------

def osc52_copy(text: str) -> bool:
    """
    Copy using OSC52 escape sequence (terminal clipboard).
    Works in many terminals and tmux (if set-clipboard on).
    """
    try:
        data = base64.b64encode(text.encode("utf-8")).decode("ascii")
        seq = f"\033]52;c;{data}\a"
        # Write to controlling TTY so it reaches the terminal even under tmux
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
    """
    Copy arbitrary text to the system clipboard (or terminal clipboard).
    Returns True on success.
    """
    os_name = platform.system()
    wsl = is_wsl()
    log.debug("copy_text_to_clipboard start: OS=%s WSL=%s env: %s", os_name, wsl, env_summary())

    # Windows native or WSL using Windows interop
    if os_name == "Windows" or (os_name == "Linux" and wsl):
        # Prefer clip.exe (fast), then PowerShell Set-Clipboard (robust)
        clip = which("clip.exe")
        if clip and run_tool([clip], text, timeout_s):
            return True
        ps = which("powershell.exe")
        if ps:
            ps_command = (
                "$c=(New-Object System.IO.StreamReader([Console]::OpenStandardInput(),"
                "[Text.Encoding]::UTF8)).ReadToEnd();"
                "Set-Clipboard -Value $c"
            )
            if run_tool([ps, "-NoProfile", "-Command", ps_command], text, timeout_s):
                return True
        # Fall through; may still try OSC52 if enabled.

    # macOS
    if os_name == "Darwin":
        pbc = which("pbcopy")
        if pbc and run_tool([pbc], text, timeout_s):
            return True

    # Linux Wayland first
    wl = which("wl-copy")
    if wl and os.environ.get("WAYLAND_DISPLAY"):
        if run_tool([wl], text, timeout_s):
            return True

    # Linux X11 path (heal env, then xsel, then xclip background)
    if os_name == "Linux" and not os.environ.get("WAYLAND_DISPLAY"):
        fix_display_env()

        xsel = which("xsel")
        if xsel and run_tool([xsel, "--clipboard", "--input"], text, timeout_s):
            return True

        xclip = which("xclip")
        if xclip and run_xclip_background(text):
            return True

    # OSC52 terminal escape as last resort
    if enable_osc52 and osc52_copy(text):
        return True

    log.warning("⚠️  All clipboard strategies failed. Env: %s", env_summary())
    return False

def copy_file_to_clipboard(file_path: Path, *, timeout_s: float = 10.0, enable_osc52: bool = True) -> bool:
    """
    Read UTF-8 text from file and copy to clipboard.
    Returns True on success.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        log.debug("Read %d chars from %s", len(content), file_path)
    except Exception as e:
        log.warning("⚠️  Cannot read %s: %s", file_path, e)
        return False

    return copy_text_to_clipboard(content, timeout_s=timeout_s, enable_osc52=enable_osc52)

# ---- Legacy name (backwards compatibility) ----

def copy_to_clipboard(file_path: Path) -> bool:
    """
    Legacy wrapper kept for compatibility with older imports.
    Equivalent to copy_file_to_clipboard(file_path).
    """
    return copy_file_to_clipboard(file_path)

# ------------ CLI (optional) ------------

if __name__ == "__main__":
    import argparse, sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
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
