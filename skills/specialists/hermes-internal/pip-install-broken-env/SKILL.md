---
name: pip-install-broken-env
description: >-
  Use when pip is missing and PEP 668 blocks installs. Install pip and Python packages in environments where pip is missing, sudo is unavailable, curl/wget are not installed, and PEP 668 blocks direct installs. Use when you need to install Python packages but the standard tools (pip, sudo, curl, wget, ensurepip) are all missing. hermes: tags: [pip, python, packages, installation, environment, broken-env]
tags: [pip, python, pep668, instalacion, paquetes, entorno]
version: 1.0.0
author: hermes
license: MIT
metadata: {}
---

# Pip Install in Broken Environment

When standard package installation tools are missing, use Python's built-in
`urllib.request` to bootstrap pip, then install packages with `--break-system-packages`.

## Prerequisites

- Python 3.13+ available
- Network access (to download get-pip.py)

## Steps

1. **Download get-pip.py using Python's urllib** (since curl/wget may not be available):
   ```bash
   python3 -c "
   import urllib.request
   url = 'https://bootstrap.pypa.io/get-pip.py'
   print('Downloading get-pip.py...')
   urllib.request.urlretrieve(url, '/tmp/get-pip.py')
   print('Downloaded. Running...')
   exec(open('/tmp/get-pip.py').read())
   "
   ```

2. **If that fails with PEP 668 error**, run get-pip.py with the flag:
   ```bash
   python3 /tmp/get-pip.py --break-system-packages
   ```

3. **Add pip to PATH** if needed (it may install to a non-standard location):
   ```bash
   export PATH="/opt/data/home/.local/bin:$PATH"
   ```

4. **Install packages** with the break-system-packages flag:
   ```bash
   pip install --break-system-packages <package1> <package2> ...
   ```

## Environment Quirks

- `pip` and `pip3` commands may not exist initially — always use `python3 -m pip` or add `.local/bin` to PATH
- `sudo` is not available — cannot use `apt-get` or system package managers
- `curl` and `wget` may not be installed — use Python's `urllib.request` as fallback
- `python3 -m ensurepip` may not work — skip to downloading get-pip.py directly
- PEP 668 is enforced — always use `--break-system-packages` flag

## Common Package Groups

**Document parsing:**
```bash
pip install --break-system-packages python-docx openpyxl pandas PyPDF2 pdfplumber mammoth Pillow
```

**Web scraping:**
```bash
pip install --break-system-packages requests beautifulsoup4 lxml selenium
```

**Data science:**
```bash
pip install --break-system-packages numpy scipy matplotlib seaborn scikit-learn
```

## Pitfalls

- **Never pipe curl/wget directly to python3** without verification — it's a security risk. Use `urllib.request` to download first, then `exec()` the file.
- **PATH issues**: pip installs to `~/.local/bin` which may not be on PATH. Always check and export if needed.
- **--break-system-packages**: This bypasses PEP 668 protection. Only use in containerized or disposable environments. In production systems, prefer virtual environments.
- **Large installs**: Some packages (like `pandas` with numpy) can take several minutes. Set generous timeouts.

## Python Environment Cross-Contamination (hermes-agent repo, verified 2026-10-22)

The execution env exports `PYTHONPATH` pointing at the **3.14 venv site-packages** while the system pytest is **3.12**: bare `pytest` imports binary-incompatible wheels (pydantic_core, PIL._imaging, _cffi_backend fail on import) and single-process runs suffer file-order `sys.path` pollution (a test's `sys.path.insert` poisons later-collected modules).

- **Never run bare `pytest` against the hermes-agent repo** (`/opt/hermes-agent`). Canonical runner with per-file isolation:
  ```bash
  cd /opt/hermes-agent && env -u PYTHONPATH HERMES_PYTHON=/usr/bin/python3.12 \
    scripts/run_tests.sh tests/gateway/ -q -j 4
  ```
- Optional test deps missing from user-site (e.g. `wcwidth`) produce ~80 spurious failures on a first full run (~7.7k tests) — install them to user-site FIRST, before diagnosing anything as a real regression.
- Classify remaining failures as pre-existing vs introduced with a throwaway A/B worktree of the base commit, comparing per-file failure counts (see `using-git-worktrees` § Throwaway A/B Worktrees).
- A `.pth` file also injects the 3.14 venv into the 3.12 interpreter — do NOT try to "fix" the interpreter config; always route through the runner. Full details: `PROJECT_MEMORY.md` in the repo (SDD pre-flight read).
