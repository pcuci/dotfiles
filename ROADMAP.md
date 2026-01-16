# Dotfiles & Tooling Strategic Roadmap

**Status:** Active
**Governing Invariant:** `Ethos/Purpose` (Teleology)
**Last Updated:** 2026-01-15 (Phase 1 Completed)

This document defines the trajectory of the `.dotfiles` repository. Every action below is bound by a specific Eudaimonia Invariant to ensure architectural integrity.

---

## 📅 Phase 1: The Fracture Plane (Decoupling) ✅ **COMPLETED**

**Goal:** Isolate the custom `catp` tooling from the configuration state.
**Primary Invariant:** `Ethos/Identity` (Separation of Concerns) — *The identity of the environment (dotfiles) must be distinct from the identity of the tools (software).*

- [x] **Isolate Source:** Move `projects/cat_project` to `tools/catp`.
    - *Why:* **`Logos/Prudence` (Right-Sizing)** — Reduces the "blast radius" of the dotfiles repo; tool development shouldn't pollute config history.
- [x] **Standardize Entry:** Create a `pyproject.toml` for `catp`.
    - *Why:* **`Logos/Clarity` (Standard Conventions)** — Replaces implicit directory structures with explicit, standard Python packaging metadata.
- [x] **Bootstrap Independence:** Update install logic to use `pipx` or `uv tool install`.
    - *Why:* **`Praxis/Wisdom` (Sustainability)** — Decouples tool dependencies from the system Python, preventing "dependency hell."
- [x] **Documentation:** Create `tools/catp/README.md` defining its CLI interface.
    - *Why:* **`Praxis/Symbiosis` (Legibility)** — A tool cannot be a good partner to the user if its interface is undocumented.

**✅ Exit Criteria:**
1. `catp` installs via standard package managers without the dotfiles repo.
2. Root `README.md` separates "Config" instructions from "Tool" instructions.

---

## 🧠 Phase 2: The Declarative Shift (Tooling)

**Goal:** Replace imperative shell scripts with declarative package management.
**Primary Invariant:** **`Logos/Prudence` (Declarative over Imperative)** — *Define "what" we want (state), not "how" to get it (script), to reduce fragility.*

- [ ] **Adopt Mise (or similar):** Create a `mise.toml` to define versions for Node, Python, Go, Starship, and Fzf.
    - *Why:* **`Ethos/Legitimacy` (Single Source of Truth)** — One file lists all required runtimes, rather than scattering version numbers across scripts.
- [ ] **Refactor Install:** Modify `install.conf.template.yaml` to delegate to the package manager.
    - *Why:* **`Logos/Vigor` (Maintenance)** — Reduces the complexity of the install script, making it easier to maintain and less prone to breakage.
- [ ] **Hygiene:** Remove `bin/dockerd-*` scripts.
    - *Why:* **`Logos/Kenosis` (Subtraction)** — Remove home-grown scripts that duplicate standard functionality (Docker plugins/aliases).

**✅ Exit Criteria:**
1. Tool versions are pinned in `mise.toml`.
2. Installation is idempotent (safe to run multiple times).

---

## 👁️ Phase 3: The Configuration Inversion (Flexibility)

**Goal:** Refactor `catp` to follow the Open/Closed principle by externalizing configuration.
**Primary Invariant:** **`Ethos/Aisthesis` (Situational Awareness)** — *The tool must sense and adapt to its local environment (cwd) rather than relying on hardcoded rules.*

- [ ] **Config Loader:** Refactor `catp` to look for `.catpignore` or `.catp.toml`.
    - *Why:* **`Praxis/Symbiosis` (Adaptability)** — Allows the user to configure the tool for *their* project without modifying the tool's code.
- [ ] **Remove Hardcoding:** Deprecate `GLOB_INCLUDE` / `GLOB_EXCLUDE` in `config.py`.
    - *Why:* **`Logos/Elenchus` (Falsification)** — Hardcoded lists assume a static world; moving them to config allows the user to correct the tool's assumptions.
- [ ] **Feature:** Add `--init` flag to generate a default config.
    - *Why:* **`Praxis/Concord` (Onboarding)** — Reduces friction for new users adopting the tool.

**✅ Exit Criteria:**
1. Users can exclude new directories without editing Python source code.

---

## 🚀 Strategic Horizons

- **CI/CD:** Automated testing of the install script. (*Invariant: `Logos/Elenchus`*)
- **Secret Management:** Integration with 1Password CLI. (*Invariant: `Logos/Prudence`*)