# `catp` Product Roadmap

**Status:** Active

**Portfolio parent:** [E5 — Independent `catp` product](../../ROADMAP.md#e5-independent-catp-product)

**Governing invariants:** `Ethos/Identity`, `Ethos/Aisthesis`, `Praxis/Symbiosis`

**Last audited:** 2026-08-04

This is the execution-level roadmap for `catp`. The root roadmap owns portfolio ordering, cross-component dependencies, and repository-wide safety. This file owns `catp` packaging, behavior, distribution, configuration, and product validation.

## Product objective

Make `catp` an independently buildable, installable, and configurable CLI for producing Git-aware repository manifests and LLM-ready snapshots without depending on the dotfiles repository layout.

## Verified current state

### Working

- The implementation lives under `tools/catp/`.
- Repository, file, and content zoom levels are implemented.
- Git collection includes tracked and untracked non-ignored files.
- Notebook output truncation and cross-platform clipboard strategies exist.
- The repository-local `bin/catp` launcher works by adding `tools/` to `sys.path`.
- The existing zoom suite passes with 30 tests in the audited environment.

### Blocking independence

- Setuptools package discovery returns no package in the current flat layout.
- `pip`, `pipx`, `uv tool`, wheel, and module installation are not verified.
- Metadata declares Python 3.8, while the source uses Python 3.10 syntax.
- Metadata references missing `CHANGELOG.md` and `py.typed` files.
- Package metadata declares MIT while the root repository license is CCxL.
- `projects/cat_project/cli.py` remains as a divergent legacy implementation.
- `bin/catp` couples execution to the dotfiles checkout.

## Milestone overview

| Milestone | Outcome | Status | Depends on |
| --- | --- | --- | --- |
| C1. Package foundation | Clean artifacts install and expose both entry points | In progress | License decision |
| C2. Behavioral contract | CLI inputs, Git collection, filtering, notebooks, and clipboard are tested | Planned | C1 test layout |
| C3. Distribution and migration | One supported installation channel replaces repository coupling | Planned | C1, C2 |
| C4. Project configuration | `.catp.toml` externalizes snapshot policy | Planned | C2 stable semantics |
| C5. Product assurance | CI prevents packaging, compatibility, and documentation drift | Incremental | Lands throughout C1–C4 |

## C1. Package foundation

**Outcome:** `catp` builds and installs as a conventional Python application.

### C1.1 Resolve product metadata — Decision required

- [ ] Decide whether `catp` inherits the root CCxL license or uses a separate license.
- [ ] Align license metadata, classifiers, documentation, and artifact contents.
- [ ] Set `requires-python` to the actual supported minimum; the lowest-cost correction is Python 3.10+.
- [ ] Remove unsupported Python classifiers and align Ruff's target version.
- [ ] Decide whether `py.typed` support is intentional; add the marker or remove the declaration.
- [ ] Add a changelog or remove the missing changelog URL.

### C1.2 Adopt a conventional layout — Planned

Target structure:

```text
tools/catp/
├── pyproject.toml
├── README.md
├── ROADMAP.md
├── src/
│   └── catp/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── clipboard.py
│       ├── config.py
│       └── core.py
└── tests/
    └── test_*.py
```

- [ ] Move package modules under `src/catp/` without changing public behavior.
- [ ] Move tests under `tests/` and import the installed package rather than `tools.catp`.
- [ ] Configure setuptools package discovery for the `src` layout.
- [ ] Preserve `catp.cli:main` and `python -m catp` as supported entry points.

### C1.3 Prove artifact installation — Planned

- [ ] Build wheel and sdist artifacts in a clean environment.
- [ ] Install the wheel into a temporary environment.
- [ ] Run `catp --help` from the installed console script.
- [ ] Run `python -m catp --help` from the installed package.
- [ ] Confirm execution does not depend on the dotfiles root or modified `sys.path`.

### C1 acceptance criteria

1. Package discovery finds exactly the intended `catp` package.
2. Wheel and sdist builds succeed from `tools/catp/`.
3. Both installed entry points execute in a clean environment.
4. Package metadata, Python support, and license claims agree.

## C2. Behavioral contract

**Outcome:** Public behavior is explicit, validated, and protected by focused tests.

### C2.1 CLI validation — Planned

- [ ] Reject depth values below `-1`.
- [ ] Require positive maximum file size and clipboard timeout values.
- [ ] Enforce or redesign the documented `--allow` and `--only` relationship.
- [ ] Specify exit codes for no repositories, no matching files, clipboard failure, invalid input, and unexpected errors.
- [ ] Test all zoom-specific default output names.

### C2.2 Git and collection semantics — Planned

- [ ] Test collection against temporary real Git repositories.
- [ ] Test tracked, untracked, ignored, nested-repository, symlink, and outside-root behavior.
- [ ] Decide whether tracked-only collection is needed as an option.
- [ ] Test size limits, explicit paths, include/exclude precedence, and skipped-file reporting.
- [ ] Keep core library functions from calling `sys.exit()` where returning or raising is more composable.

### C2.3 Filtering policy — Planned

- [ ] Resolve `pnpm-lock.yaml` appearing in both inclusion and exclusion policy.
- [ ] Decide and document policy for `yarn.lock`, `poetry.lock`, `go.mod`, `go.sum`, and other dependency manifests.
- [ ] Test default pattern behavior rather than duplicating unverified lists in documentation.
- [ ] Clarify whether `--allow` removes exact default patterns or overrides exclusions by glob.

### C2.4 Notebook and clipboard behavior — Planned

- [ ] Test notebook output stripping and malformed notebook handling.
- [ ] Replace overly broad exception handling with actionable errors.
- [ ] Test Wayland, X11, macOS, Windows/WSL, OSC52, timeout, and unavailable-tool paths with mocks.
- [ ] Preserve the generated output when clipboard copying fails and document the resulting exit status.

### C2 acceptance criteria

1. Valid and invalid CLI inputs have deterministic behavior and tests.
2. Git and filtering semantics are covered using real temporary repositories.
3. Notebook and clipboard error paths are isolated and actionable.
4. Public behavior documented in `README.md` matches executable tests.

## C3. Distribution and migration

**Outcome:** Users install `catp` through one supported channel, and legacy repository coupling is removed.

### C3.1 Choose distribution channel — Decision required

Evaluate:

| Option | Strength | Cost/risk |
| --- | --- | --- |
| PyPI | Familiar `pipx`/`uv tool` installation | Name availability, release automation, public support commitment |
| VCS/subdirectory | No registry release required | Installation syntax and source layout are less discoverable |
| Repository-local artifact | Minimal publication overhead | Weak independence and update experience |

- [ ] Select and document one primary installation path.
- [ ] Define versioning and release policy.
- [ ] Add package index badges only after a published artifact is verified.

### C3.2 Retire legacy paths — Planned

- [ ] Compare `projects/cat_project/cli.py` features with current product intent.
- [ ] Migrate deliberately retained features with tests or document their removal.
- [ ] Delete the legacy implementation after migration decisions are complete.
- [ ] Replace `bin/catp` path injection with the supported installed command.
- [ ] Update root bootstrap only after the distribution channel is proven.

### C3 acceptance criteria

1. One installation channel is documented and exercised in CI.
2. The legacy implementation and `sys.path` launcher are gone.
3. Versioning, release, and rollback expectations are documented.
4. A user can install and run `catp` without cloning the dotfiles repository.

## C4. Project configuration

**Outcome:** Projects adapt snapshot behavior without editing package source.

### C4.1 Define `.catp.toml` — Planned

- [ ] Define a typed schema for includes, directory exclusions, file exclusions, size limits, notebook behavior, and clipboard defaults.
- [ ] Prefer one configuration format rather than introducing both `.catpignore` and `.catp.toml` initially.
- [ ] Define discovery scope: current directory, repository root, parent traversal, and optional user-level config.
- [ ] Define precedence: built-ins < user/project configuration < CLI.
- [ ] Define merge versus replace semantics for lists.

### C4.2 Implement and migrate — Planned

- [ ] Add a loader with actionable validation errors.
- [ ] Add `catp --init` to create a documented default configuration without overwriting existing files.
- [ ] Preserve current defaults through the first migration unless a behavior change is explicitly documented.
- [ ] Deprecate direct reliance on hardcoded policy constants.

### C4.3 Documentation synchronization — Planned

- [ ] Generate or test CLI option documentation from argparse.
- [ ] Generate or test default-policy documentation from the configuration model.
- [ ] Add configuration examples for common Python, frontend, infrastructure, and monorepo cases.

### C4 acceptance criteria

1. Users can change snapshot policy without modifying Python source.
2. Discovery, precedence, and merge behavior are documented and tested.
3. `catp --init` is idempotent and does not overwrite user configuration.
4. CLI and configuration documentation are checked against implementation.

## C5. Product assurance

**Outcome:** Every supported product claim has automated evidence.

### C5.1 Initial CI — Planned

- [ ] Test the supported Python version matrix.
- [ ] Run Ruff and pytest.
- [ ] Build wheel and sdist artifacts.
- [ ] Install the wheel and smoke-test both entry points.
- [ ] Run tests against the installed package rather than repository import shortcuts.

### C5.2 Quality gates — Planned

- [ ] Add coverage reporting after measuring a realistic baseline.
- [ ] Check missing package files, broken metadata URLs, and README links.
- [ ] Compare generated CLI help with documented options.
- [ ] Add release artifact inspection for license and package contents.

### C5 acceptance criteria

1. CI covers every supported Python version and public entry point.
2. A release cannot pass with an empty package, missing metadata files, or stale CLI documentation.
3. Product behavior and configuration changes include regression tests.

## Recommended execution order

1. Resolve license and Python support decisions.
2. Complete C1 package layout and isolated installation.
3. Establish C5 build/install CI immediately around C1.
4. Harden behavior under C2.
5. Select distribution and retire legacy paths under C3.
6. Externalize policy under C4.

Configuration work should follow behavioral stabilization; otherwise existing contradictions risk becoming permanent public schema.
