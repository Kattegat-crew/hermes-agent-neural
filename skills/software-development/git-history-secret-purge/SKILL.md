---
name: git-history-secret-purge
description: "Use when purging committed secrets from git history"
tags: [git, secrets, seguridad, filter-repo, historial, rotacion, leak]
---

# Git History Secret Purge

## Overview

Permanently remove secrets from git history using `git filter-repo` or `git filter-branch`, then verify zero occurrences and force push. Always rotate the secret after purging — once in history, assume compromised.

## When to Use

- API keys, passwords, or tokens found in git history
- `.env` files accidentally committed
- Sensitive files (certificates, private keys, tokens) in commits
- Preparing a repo for open-source release with internal secrets
- Responding to a suspected credential leak

## When NOT to Use

- Secrets only in `.gitignore` (preventive, not remediation)
- New repos with no history (just don't commit)
- When a full history rewrite is not acceptable (fork instead)

## Core Pattern

```
Backup → Locate → Rewrite → GC → Verify → Force push → Rotate secret
```

## Quick Reference

**Tool:** `git-filter-repo` (`pip3 install git-filter-repo`) or built-in `git filter-branch`
**Prevention:** `.gitignore` with `.env`, `node_modules/`, `dist/`, `*.pem`, `*.key`

## Implementation

### 1. Backup for rollback

```bash
git bundle create repo-backup-$(date +%Y%m%d).bundle --all
```

### 2. Locate secrets

```bash
# Search git history for a secret value
git log -S '<secret_value>' --all --oneline

# Grep tree content at every commit
```

### 3. Rewrite history

```bash
# Filter-repo: exclude files
git filter-repo --invert-paths --path .env --path .env.local --path node_modules/ --path dist/

# Or filter-repo: replace values in specific files
git filter-repo --replace-text <(echo "SECRET_VALUE=>NEW_VALUE")

# Built-in alternative (slower)
git filter-branch --force --index-filter   'git rm --cached --ignore-unmatch .env .env.local'   --prune-empty --tag-name-filter cat -- --all
```

### 4. Garbage collect

```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### 5. Verify zero occurrences

```bash
# Should return nothing
git log -S '<secret_value>' --all --oneline
git log -S '<secret_value>' --all  # encuentra commits con la ocurrencia
```

### 6. Force push

```bash
git push --force --all
git push --force --tags
```

### 7. Rotate the secret

- **Assume compromised.** Change the actual credential (API key, password, token).
- Update all `.env` files and services.
- Revoke old credentials at the provider.

## Common Mistakes

| Mistake | Consequence | Fix |
|---------|------------|-----|
| Forget reflog cleanup | Secrets still recoverable via reflog | `reflog expire --expire=now --all` + `gc --prune=now` |
| Push without verifying | Old commits still reachable | Verify with `git log -S` before push |
| Delete file only from HEAD | History still has secret | Rewrite entire history |
| Assume secret is safe after purge | It was in history long enough to be scraped | Always rotate the credential |
| Force push without notifying collaborators | Team's forks become broken | Notify team, have them rebase |

## Real-World Impact

- `.env` files with API keys committed to public repos get scraped within minutes
- Deleting a file in a new commit does NOT remove it from history
- `git filter-branch` is deprecated — use `git-filter-repo`
- Force push rewrites history — all collaborators must redo their work
