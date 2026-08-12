# `catp` — context-aware repository snapshots

`catp` creates Git-aware repository manifests, file manifests, and full source snapshots for LLM workflows.

**Status:** repository-local beta

**Runtime:** Python 3.10+ as currently implemented

**Distribution:** not currently published or independently installable

## Current execution model

Run the repository launcher from a dotfiles checkout:

```bash
./bin/catp --help
./bin/catp --zoom contents
```

The launcher adds the repository's `tools/` directory to `sys.path` and imports `catp.cli`. Although `pyproject.toml` exists, its current setuptools package discovery finds no package because the Python modules sit directly beside the project file. Therefore these are **not yet supported**:

```text
pip install catp
pipx install catp
uv tool install catp
pip install -e tools/catp
```

Detailed packaging and product work is tracked in the [`catp` roadmap](ROADMAP.md), under portfolio epic **E5: Independent `catp` product** in the root [`ROADMAP.md`](../../ROADMAP.md). Publication should wait until isolated wheel installation and both public entry points are tested.

## Usage

```bash
# Full snapshot of the current repository
./bin/catp

# Snapshot selected paths
./bin/catp src/ tests/

# Repository tree only
./bin/catp --zoom repos --depth 2

# Matching file list without contents
./bin/catp --zoom files --only "*.py"

# Full contents at unlimited repository-discovery depth
./bin/catp --zoom contents --depth -1

# Write to a selected output file
./bin/catp --out context.txt

# Copy the generated output to the clipboard
./bin/catp --clipboard
```

### Zoom levels

| Value | Output | Default suffix |
| --- | --- | --- |
| `repos` | Discovered repository tree | `-repos.txt` |
| `files` | Matching file manifest | `-files.txt` |
| `contents` | Full matching file contents (default) | `-llm.txt` |

When `--out` is omitted, output is written beneath the platform temporary directory using the current directory name and the suffix above.

## CLI reference

The authoritative option definitions are in `cli.py`. Run `./bin/catp --help` for generated help.

| Option | Meaning |
| --- | --- |
| `paths...` | Restrict collection to selected paths; defaults to the current repository |
| `-z, --zoom {repos,files,contents}` | Select output resolution |
| `-o, --out PATH` | Select output path |
| `-k, --max-kb KB` | Maximum included file size; default `400` KB |
| `--only PATTERN...` | Add inclusion patterns using OR semantics; repeatable |
| `-e, --exclude PATTERN...` | Add exclusion patterns using OR semantics; repeatable |
| `-a, --allow PATTERN...` | Remove exact patterns from the default exclusion set |
| `--no-ipynb-truncate` | Preserve notebook outputs instead of stripping them |
| `-q, --quiet` | Suppress informational output |
| `-v, --verbose` | Log filtering decisions |
| `-c, --clipboard` | Copy the generated output to the system clipboard |
| `--clipboard-timeout SECONDS` | Clipboard operation timeout; default `10.0` seconds |
| `-d, --depth N` | Discover nested Git repositories to depth `N`; `-1` means unlimited |

`--allow` is described by the parser as requiring an inclusion flag, but that relationship is not yet enforced. Its current implementation removes exact default exclusion patterns rather than acting as a general override glob.

## Collection behavior

### Git integration

For each discovered repository, `catp` uses:

```text
git ls-files --cached --others --exclude-standard
```

This includes tracked files and untracked, non-ignored files. It respects standard Git ignore rules, but it is not a tracked-files-only snapshot. Review untracked material before sharing generated output.

### Filtering

Default inclusion and exclusion policy currently lives in `config.py`. The lists are implementation details and are not duplicated here because they have previously drifted from documentation.

Notable current behavior:

- common source, infrastructure, configuration, documentation, and notebook patterns are included;
- dependency, build, VCS, IDE, binary, archive, and large-file patterns are excluded;
- exclusions are applied before inclusion;
- `pnpm-lock.yaml` appears in both the include and exclude configuration and is therefore effectively excluded;
- `poetry.lock` and `yarn.lock` are currently included.

Milestone C4 in the [`catp` roadmap](ROADMAP.md) will introduce a `.catp.toml` contract after the contradictory built-in policies are resolved.

### Clipboard support

Clipboard mode selects platform-specific tools:

- Wayland: `wl-copy`
- X11: `xsel` or `xclip`
- macOS: `pbcopy`
- Windows/WSL: `clip.exe` or PowerShell
- fallback: OSC52 through a writable `/dev/tty`

If clipboard copying fails, the output file remains written but the command returns failure.

## Development and validation

The existing repository test suite focuses on zoom behavior:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tools/catp/test_zoom.py -q
```

At the 2026-08-04 audit, this passed with 30 tests. This does **not** validate package building or installation.

Priority test gaps include:

- wheel and sdist builds;
- isolated installation and public entry points;
- supported Python-version matrix;
- real Git repository integration;
- filtering and `--allow` semantics;
- notebook error handling;
- clipboard strategy selection and failures;
- numeric argument validation and output errors.

## Modernization milestones

The component [`ROADMAP.md`](ROADMAP.md) is the source of truth for execution detail:

| Milestone | Purpose | Status |
| --- | --- | --- |
| C1 Package foundation | Conventional layout, truthful metadata, build/install smoke tests | In progress |
| C2 Behavioral contract | Validate CLI behavior and expand integration/error-path coverage | Planned |
| C3 Distribution and migration | Choose a channel, retire legacy code and the import shim | Planned |
| C4 Project configuration | Add typed `.catp.toml`, precedence, and `--init` | Planned |
| C5 Product assurance | Add compatibility, artifact, and documentation checks | Incremental |

Root E1.5 owns the prerequisite license decision, while root E6 coordinates repository-wide assurance.

## Known packaging and metadata blockers

- Setuptools package discovery currently returns no package.
- Source uses Python 3.10 syntax while metadata declares Python 3.8.
- `pyproject.toml` references a missing `CHANGELOG.md` and `py.typed` marker.
- No verified `catp` project is published at the documented PyPI name.
- Package metadata declares MIT while the root repository uses the Cosmic Coexistence License.
- `projects/cat_project/cli.py` remains as a divergent legacy implementation.

## Contributing

Open issues in the [main repository](https://github.com/pcuci/dotfiles/issues). Packaging, safety, and contract alignment take priority over feature expansion.

## License

The intended package license is unresolved. The root [`LICENSE`](../../LICENSE) is the Cosmic Coexistence License, while `pyproject.toml` currently declares MIT. Do not publish package artifacts until this conflict is explicitly resolved.
