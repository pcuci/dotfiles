# catp - Context-Aware Snapshot Tool

**A CLI tool for creating LLM-ready code snapshots with intelligent file filtering and Git-aware collection.**

[![PyPI version](https://badge.fury.io/py/catp.svg)](https://pypi.org/project/catp/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 Installation

### Via pipx (Recommended)

```bash
pipx install catp
```

### Via pip

```bash
pip install catp
```

### Via uv

```bash
uv tool install catp
```

### From Source

```bash
git clone https://github.com/pcuci/dotfiles.git
cd dotfiles/tools/catp
pip install -e .
```

## 📖 Usage

### Basic Usage

```bash
# Snapshot current directory
catp

# Snapshot specific paths
catp src/ tests/

# Save to custom location
catp --out my-snapshot.txt

# Copy to clipboard
catp --clipboard
```

### Advanced Filtering

```bash
# Include only Python files
catp --only "*.py"

# Exclude test files and node_modules
catp --exclude "**/test*" --exclude "**/node_modules/**"

# Allow specific exclusions (combine with --only)
catp --only "*.js" --allow "**/node_modules/**"

# Limit file size
catp --max-kb 200

# Disable Jupyter notebook output truncation
catp --no-ipynb-truncate
```

### Git Repository Scanning

```bash
# Scan multiple levels deep for Git repos
catp --depth 2

# Include all files in Git repos regardless of ignore rules
catp --depth 1  # Infinite depth
```

## 🎯 Command Line Options

```
Usage: catp [OPTIONS] [PATHS...]

Context-aware snapshot tool for LLM workflows.

Positional Arguments:
  paths                 Paths to include (e.g., src/ tests/). If empty, scans current directory.

Options:
  -o, --out PATH        Output file path (default: /tmp/{repo-name}-llm.txt)
  -k, --max-kb KB       Maximum file size in kilobytes (default: 400)
  --only PATTERN+       Glob patterns to select files (overrides defaults)
  -e, --exclude PATTERN+ Glob patterns to exclude files (adds to blocklist)
  -a, --allow PATTERN+  Disable default exclusions (requires --only)
  --no-ipynb-truncate   Include Jupyter notebook outputs
  -q, --quiet           Suppress informational output
  -v, --verbose         Enable detailed filtering logs
  -c, --clipboard       Copy final snapshot to system clipboard
  --clipboard-timeout S Timeout for clipboard operations (default: 10.0s)
  -d, --depth N         Scan for Git repos up to N levels deep (-1 for infinite)
  -h, --help            Show this help message
```

## 🔍 File Inclusion Logic

### Default Included Extensions

catp includes files with these extensions by default:

- **Web**: `.js`, `.jsx`, `.ts`, `.tsx`, `.vue`, `.css`, `.scss`, `.sass`, `.html`, `.tmpl`
- **Backend**: `.py`, `.go`, `.java`, `.cs`, `.php`, `.rb`, `.rs`
- **Config**: `.json`, `.yaml`, `.yml`, `.toml`, `.xml`, `.config`, `.ini`, `.cfg`
- **DevOps**: `.tf`, `.hcl`, `.dockerfile`, `.sh`, `.bash`, `.ps1`
- **Docs**: `.md`, `.mdx`, `.txt`
- **Data**: `.ipynb`, `.sql`

### Default Exclusions

These directories and patterns are excluded by default:

- **Version Control**: `.git/`
- **Dependencies**: `node_modules/`, `vendor/`, `__pycache__/`, `.venv/`
- **Build Artifacts**: `dist/`, `build/`, `.terraform/`
- **Binaries**: Files ending in `.min.*`, `.png`, `.jpg`, `.exe`, etc.
- **Lock Files**: `package-lock.json`, `yarn.lock`, `poetry.lock`, etc.

### Git Integration

catp automatically discovers Git repositories and collects files tracked by Git. This ensures only relevant project files are included, respecting `.gitignore` rules.

## 🌟 Key Features

- **Git-Aware**: Automatically finds and respects Git repository boundaries
- **Smart Filtering**: Intelligent inclusion/exclusion with glob patterns
- **Cross-Platform Clipboard**: Supports Windows, macOS, Linux (X11/Wayland)
- **Size Limits**: Prevents accidentally including large binary files
- **Jupyter Support**: Intelligently truncates notebook outputs for LLM consumption
- **Configurable**: Extensive options for customizing file selection

## 📋 Examples

### Frontend Project
```bash
catp --only "*.{js,jsx,ts,tsx,css,html}" --exclude "**/node_modules/**"
```

### Python Backend
```bash
catp --only "*.py" --exclude "**/test*" --exclude "**/__pycache__/**"
```

### Multi-Service Repository
```bash
catp --depth 2 --max-kb 300
```

### Quick Clipboard Copy
```bash
catp -c -q --only "*.py" src/
```

## 🤝 Contributing

Found a bug or want to suggest a feature? Open an issue on the [main repository](https://github.com/pcuci/dotfiles/issues).

## 📄 License

MIT License - see the [main LICENSE](../LICENSE) file for details.

---

**Part of the [Sovereign Dotfiles](https://github.com/pcuci/dotfiles) project.**