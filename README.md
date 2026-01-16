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