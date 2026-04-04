# .dotfiles (Sovereign Edition)

**Status:** Modernization in Progress (See `ROADMAP.md`)
**Governing Invariant:** `Ethos/Identity`

A portable, sovereign configuration environment and tooling suite.

## 🗺️ Architecture

This repository is organized into three distinct domains, ensuring **Separation of Concerns** (`Ethos/Identity`):

1.  **Configuration State (The "Dotfiles")**
    - Managed via `Dotbot`.
    - Defined in `install.conf.template.yaml`.
    - Targets: `~/.bashrc`, `~/.gitconfig`, `~/.ssh/config`.

2.  **Sovereign Tooling (The "Tools")**
    - **`catp`**: A context-aware snapshot tool for LLM workflows.
    - Located in `tools/catp/`.
    - *See Phase 1 of Roadmap for decoupling plans.*

3.  **Bootstrapping (The "Lift")**
    - Scripts to elevate a fresh machine to a configured state.

4.  **Cursor Multi-Profile (The "Curser")**
    - Runs two Cursor instances with separate logins (work + personal).
    - Shares extensions, keybindings, snippets; isolates accounts and theme.
    - See `bin/curser`, `bin/curser-oauth`, `bin/cursor-uri-handler`.

## Cursor Multi-Profile Setup

Run two Cursor instances side-by-side with different accounts:

| Instance | Login | Theme | Launched via |
| -------- | ----- | ----- | ------------ |
| `cursor` | work (default) | default | system launcher |
| `curser` | personal | Solarized Dark | `curser` command |

### Files

| File | Purpose |
| ---- | ------- |
| `bin/curser` | Launcher: merges settings, symlinks config, starts Cursor with `--user-data-dir` |
| `bin/curser-oauth` | Arms a semaphore so the next OAuth callback routes to curser |
| `bin/cursor-uri-handler` | XDG dispatcher for `cursor://` URIs (replaces Cursor's default) |
| `cursor-uri-handler.desktop` | Registers the dispatcher as the system URI handler |
| `cursor-personal-overrides.json` | JSON overrides merged on top of base settings (e.g. theme) |

### How it works

```text
~/.config/Cursor/          ← default user-data-dir (work account)
~/.cursor/extensions/      ← shared extension storage (both instances)
~/.cursor-profile-personal/ ← curser's user-data-dir (personal account)
~/.cursor/mcp.json         ← shared MCP server config (both instances)
```

1. `curser` merges `~/.config/Cursor/User/settings.json` with
   `cursor-personal-overrides.json` using `jq`, producing a
   standalone `settings.json` inside the personal data dir.
2. Keybindings, snippets, and the extension registry are symlinked
   from the default profile so changes propagate automatically.
3. An `inotifywait` watcher re-merges settings if the base file changes
   while curser is running.

### OAuth routing (when both instances are open)

```text
curser-oauth  →  touches ~/.cursor-oauth-route-to-personal  (flag)
Browser       →  redirects to cursor://...
XDG           →  calls cursor-uri-handler
                  ├── flag present + fresh → route to curser (--open-url)
                  └── no flag             → route to cursor (default)
```

The flag auto-expires after 2 minutes to prevent stale misrouting.

### Dependencies

- `jq` — JSON merging for settings
- `inotify-tools` — optional, for live settings re-merge

## 🚀 Bootstrap

**Prerequisites:**
- Git
- Python 3.10+
- `pipx` (recommended) or `uv`

```bash
git clone https://github.com/pcuci/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
./install
```

## 🛠️ Tooling Usage (`catp`)

`catp` is a tool included in this suite to snapshot codebases for AI context.

```bash
# Install (Current: Phase 1 Pending)
pip install -e tools/catp

# Usage
catp --help
catp . --out context.txt
```

## 📜 License

Ethically sourced under the [Atmosphere License](https://www.open-austin.org/atmosphere-license/).