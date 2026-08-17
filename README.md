# .dotfiles (Sovereign Edition)

**Status:** Modernization in progress

**Governing Invariant:** `Ethos/Identity`

**Verified snapshot:** 2026-08-17

A personal Linux/WSL configuration repository, bootstrap system, and tooling workspace. It is optimized for the owner's environment; it is not yet a portable, reproducible distribution for arbitrary hosts.

See [`ROADMAP.md`](ROADMAP.md) for the epic-based modernization plan.

## Modernization map

| Epic | Scope | Current priority |
| --- | --- | --- |
| E1 | Operational safety | Remove hidden SSH execution, unsafe repository planning, credential mirroring, and privileged Docker exposure |
| E2 | Reproducible bootstrap | Add preview/recovery and install committed dependency revisions |
| E3 | Declarative toolchain | Establish one owner for runtime and CLI versions |
| E4 | Configuration architecture | Separate portable, personal, work, WSL, editor, and generated state |
| E5 | Independent `catp` product | Fix packaging, distribution, testing, and project-local policy |
| E6 | Continuous assurance | Add CI for shell, packaging, bootstrap, secrets, and documentation drift |

The immediate implementation tranche is E1-led. Feature expansion should not outrun the safety and reproducibility foundations.

## Architecture

The repository currently contains five domains:

1. **Configuration state**
   - Shell, Git, SSH, GPG, Byobu, Starship, Cursor, and helper configuration.
   - Installed primarily through Dotbot.
   - `install.conf.template.yaml` is the source of truth; `install.conf.yaml` is generated and must not be edited.

2. **Bootstrap**
   - `install` loads the home profile by default (or an explicit profile), generates Dotbot configuration, initializes dependencies, replaces selected home-directory files, and runs Dotbot.
   - `win-install` is a legacy WSL-oriented helper and is not currently a supported bootstrap path.

3. **Repository-local tooling**
   - `tools/catp/` contains the current context snapshot implementation.
   - `bin/` contains personal operational helpers with varying portability and safety characteristics.

4. **Editor profiles**
   - `bin/curser`, `bin/curser-oauth`, and `bin/cursor-uri-handler` support a separate personal Cursor login.
   - VS Code recommendations are tracked under `.vscode/`.

5. **Governance projections**
   - `.agents/imports.json` is tracked.
   - Most `.agents/`, `.cursor/agents/`, `.cursor/skills/`, and `.claude/` content is generated or ignored and depends on an external governance checkout.

The `dotbot`, `complete-alias`, and `fzf` directories are upstream Git submodules. Their committed gitlinks are the reviewable pins, although the current installer advances them to remote branch heads during bootstrap; correcting that non-reproducible behavior is a roadmap priority.

## Bootstrap

### Current support

| Path | Status | Notes |
| --- | --- | --- |
| Ubuntu/Linux interactive environment | Personal/operational | Primary environment; still host-coupled |
| WSL | Partial | Several helpers assume WSL, but `win-install` is currently stale |
| macOS | Unverified | No supported installation contract |
| Native Windows | Unsupported | `win-install` is Bash and should not be interpreted as native Windows support |

### Prerequisites used by the current installer

- Bash, Git, and Python
- `envsubst` (normally provided by `gettext`)
- `curl`
- Dotbot's Python requirements
- `xdg-mime` and optionally `update-desktop-database` for Cursor URI registration
- `gpgconf` for GPG-agent reload

The configured shell also integrates optional tools including FZF, Starship, jq, inotify-tools, direnv, NVM/Node, Go, GVM, Bun, pnpm, Rust, Homebrew, Pulumi, and cloud/Kubernetes CLIs. The installer does not provision all of them.

### Safety and reproducibility warning

The current `install` command:

- deletes regular (non-symlink) versions of `~/.bashrc`, `~/.profile`, `~/.bash_logout`, and `~/.ssh/config` without creating backups;
- runs `git submodule update --remote`, so installed dependency revisions can differ from the repository's committed pins;
- executes remote Starship installation code through `curl | sh` when Starship is not already installed.

Review the script and back up existing configuration before running it. A preflight, backup, and dry-run workflow is planned.

### Profile-aware invocation

```bash
mkdir -p ~/code
git clone --recurse-submodules https://github.com/pcuci/dotfiles.git ~/code/dotfiles
ln -s ~/code/dotfiles ~/.dotfiles
cd ~/code/dotfiles
./install
```

The profile defaults to `home`, the only current bootstrap profile. An explicit profile may be supplied for a future or machine-specific configuration, but its `.env.<profile>` file must exist:

- `.env` optionally supplies shared defaults.
- `.env.<profile>` is required and supplies profile-specific values; `.env.home` is the current profile.
- `.gitconfig.<profile>` is selected when present; otherwise `.gitconfig.default` is used.
- Repository inputs are resolved relative to the checkout, so `install` can also be launched from another working directory.
- Starship is installed when missing and uses its built-in default prompt; the repository intentionally does not link a custom `starship.toml` or require a Nerd Font.

`~/code/dotfiles` is the canonical checkout. The `~/.dotfiles` compatibility symlink preserves paths used by Dotbot and shell configuration.

## Cursor multi-profile setup

Run two Cursor instances side by side with different accounts:

| Instance | Login | Theme | Launched via |
| --- | --- | --- | --- |
| `cursor` | work/default | base settings | system launcher |
| `curser` | personal | personal overrides | `curser` command |

### Managed files

| File | Purpose |
| --- | --- |
| `bin/curser` | Merges settings, links shared configuration, and starts Cursor with a personal `--user-data-dir` |
| `bin/curser-oauth` | Arms a short-lived flag so the next OAuth callback routes to `curser` |
| `bin/cursor-uri-handler` | XDG dispatcher for `cursor://` URIs |
| `cursor-uri-handler.desktop` | Registers the dispatcher as the system URI handler |
| `cursor-personal-overrides.json` | JSON merged over base settings on each personal launch |

```text
~/.config/Cursor/           default user data (work account)
~/.cursor/extensions/       shared extension storage
~/.cursor-profile-personal/ personal user data and account state
~/.cursor/mcp.json          global MCP server configuration
```

MCP/plugin OAuth tokens remain in each profile's `User/globalStorage/state.vscdb`; they are account-specific and are not shared through `mcp.json`.

Dependencies:

- `jq` for settings merging
- `inotifywait` from `inotify-tools` for optional live re-merging
- Linux XDG desktop utilities for URI registration

The current desktop entry contains an owner-specific absolute path, and the launcher links some Cursor internal state. Treat this integration as Linux- and Cursor-version-specific until those assumptions are removed under E4.

## `catp`

`catp` creates Git-aware repository manifests, file manifests, and full snapshots for LLM workflows.

Current repository-local usage:

```bash
cd ~/code/dotfiles
./bin/catp --help
./bin/catp --zoom repos --depth 2
./bin/catp --zoom contents --out context.txt
```

Independent package installation is **not currently supported**. The package metadata exists, but its setuptools discovery finds no installable package in the present layout, and no verified PyPI distribution exists. The root launcher works by adding this repository's `tools/` directory to `sys.path`. E5 owns completion of this product boundary.

See [`tools/catp/README.md`](tools/catp/README.md) for the implemented CLI and current limitations.

## Operational risk boundaries

Some helpers are personal operational scripts rather than supported, safe-by-default products:

- `bin/repo-sync.py` mutates branches and tags while constructing what appears to be a preview and can queue force pushes.
- SSH host configuration contains `LocalCommand` hooks that can pull and execute dotfiles installation during connection setup.
- `ssh_sync` mirrors SSH material with deletion and symlink following.
- `bin/dockerd-start` exposes a privileged, non-TLS Docker daemon; removal is planned.

Do not adopt these workflows on a new host without reviewing and redesigning their safety contracts. E1 tracks their removal or hardening; E2 tracks installer recovery and reproducibility.

## Governance regeneration

Governance capabilities are declared in `.agents/imports.json` and materialized from an external governance checkout. Generated symlinks are machine-layout-dependent. Use the governance project's onboarding/regeneration workflow after cloning this repository; the exact external path is not owned by this repository and should be documented by that project. E4 owns clarification of these tracked/generated/external boundaries.

## License

The repository root [`LICENSE`](LICENSE) currently contains **The Cosmic Coexistence License (CCxL), version 0.0.1**.

`tools/catp/pyproject.toml` still declares MIT, which conflicts with the repository license. Package publication is blocked until the intended `catp` license is explicitly decided and all metadata is aligned.
