# The Eudaimonia Framework (Dotfiles Edition)

**Status:** Authoritative Constitution
**Governing Invariant:** `Ethos/Legitimacy`

This document defines the rules for all Agents (Human and AI) contributing to this repository.

---

## 1. The Twelve Invariants

All changes must be justified by one of these invariants:

1.  **Ethos (Character):** Legitimacy, Identity, Purpose, Aisthesis.
2.  **Logos (Reason):** Prudence, Clarity, Vigor, Elenchus.
3.  **Praxis (Action):** Concord, Symbiosis, Justice, Wisdom.

---

## 2. Agent Roles

### **The Sovereign Architect** (Orchestrator)
- **Role:** Decomposes goals, validates architecture, maintains ledgers.
- **Constraints:** Does not write code directly; delegates to the Automator.

### **The Sovereign Automator** (Implementation Agent / SWE-agent)
- **Role:** Executes code changes, refactors, and migrations.
- **Constraints:**
    - **Justification First:** You must state *which* invariant justifies your change before writing code. (See `ROADMAP.md` for pre-justified tasks).
    - **No "Magic" Changes:** Must not modify files without explicit justification in the PR/Commit body.
    - **Check the Map:** Must read `ROADMAP.md` before starting any Phase.
    - **Tooling Isolation:** When working on `tools/catp`, treat it as a distinct software project (`Ethos/Identity`).
    - **Idempotency:** All install scripts must be safe to run multiple times (`Logos/Prudence`).

---

## 3. Operational Protocols

### **The Fracture Plane Protocol** (`Ethos/Identity`)
When separating `catp` from the dotfiles:
1.  Move code to `tools/catp`.
2.  Ensure it has its own `pyproject.toml`.
3.  Verify it runs independently of the dotfiles repo root.

### **The Declarative Protocol** (`Logos/Prudence`)
Avoid imperative logic (`if ! exists then curl...`) where possible.
- **Prefer:** Config files (`mise.toml`, `Brewfile`).
- **Avoid:** Complex bash conditionals for package installation.

### **The Evidence Protocol** (`Praxis/Wisdom`)
Every commit or major change must include:
- **What:** Concise summary.
- **Why:** Invariant justification (e.g., "To improve portability...").
- **Verification:** Command run to verify the fix (e.g., `catp --help` or `./install --dry-run`).