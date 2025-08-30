"""
Clipboard utilities for copying snapshot content.
Supports Windows, WSL, macOS, and Linux (wl-copy/xclip).
"""
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

def is_wsl() -> bool:
    """Return True if running inside Windows Subsystem for Linux."""
    return "microsoft" in platform.uname().release.lower() or "WSL_DISTRO_NAME" in os.environ

def copy_to_clipboard(file_path: Path) -> bool:
    """Try to put file content on the system clipboard. Return True on success."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        log.warning(f"⚠️  Cannot read file {file_path} for clipboard: {e}")
        return False

    os_name = platform.system()
    tool: list[str] | None = None

    # This more robust PowerShell command explicitly creates a UTF-8 stream reader.
    ps_command = (
        "$content = (New-Object System.IO.StreamReader([System.Console]::OpenStandardInput(), "
        "[System.Text.Encoding]::UTF8)).ReadToEnd(); Set-Clipboard -Value $content"
    )

    if os_name == "Windows" or (os_name == "Linux" and is_wsl()):
        if shutil.which("powershell.exe"):
            tool = ["powershell.exe", "-NoProfile", "-Command", ps_command]
        elif shutil.which("clip.exe"):
            log.warning("⚠️  PowerShell not found. Falling back to clip.exe, which may corrupt emojis.")
            tool = ["clip.exe"]
    elif os_name == "Darwin":
        if shutil.which("pbcopy"):
            tool = ["pbcopy"]
    elif os_name == "Linux":
        if shutil.which("wl-copy"):
            tool = ["wl-copy"]
        elif shutil.which("xclip"):
            tool = ["xclip", "-selection", "clipboard"]

    if not tool:
        log.info(f"ℹ️  No clipboard tool found for {os_name} (WSL={is_wsl()}).")
        return False

    tool_name = Path(tool[0]).name
    try:
        result = subprocess.run(
            tool, input=content, text=True, capture_output=True,
            encoding="utf-8", check=False,
        )
        if result.returncode == 0:
            log.info(f"📋 Snapshot copied to clipboard via {tool_name}.")
            return True
        else:
            log.warning(f"⚠️  {tool_name} failed (code {result.returncode}).")
            if result.stderr: log.warning(f"   Error: {result.stderr.strip()}")
            if result.stdout: log.info(f"   Output: {result.stdout.strip()}")
            return False
    except FileNotFoundError:
        log.warning(f"⚠️  Clipboard tool '{tool_name}' not found.")
        return False
    except Exception as e:
        log.warning(f"⚠️  Clipboard error with {tool_name}: {e}")
        return False
