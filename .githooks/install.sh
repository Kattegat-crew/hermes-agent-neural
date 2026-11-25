#!/usr/bin/env bash
# Activa los hooks versionados del repo. Sin esto, .githooks/ es decorativo.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "hooks activos: $(git config core.hooksPath)"
echo "pre-push protege: main prod-stable"
