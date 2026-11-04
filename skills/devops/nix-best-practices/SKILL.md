---
name: nix-best-practices
description: "Use when writing Nix flakes or reproducible dev shells"
tags: [nix, flakes, direnv, devshell, reproducibilidad, devops, entornos]
license: MIT
compatibility: hermes, opencode, bash
metadata:
  hermes:
    tags: [nix, flakes, devshell, direnv, reproducibility, devops]
    category: devops
---

# Nix Flakes & Reproducible Development Environments

Best practices for building, pinning, and automating reproducible development shells and system packages using Nix.

## 1. Core Principles

- **Deterministic Dependencies**: Lock every single binary, library, and compiler version into `flake.lock`. Never rely on unpinned channels.
- **Hermetic Dev Environments**: Developers and CI runners must share the exact same toolchain definitions.
- **Zero Host Pollution**: Tools required for a project must live inside the project's devShell, not installed globally on the operating system.

---

## 2. Standard `flake.nix` DevShell Architecture

```nix
{
  description = "Reproducible multi-language development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python311
            python311Packages.pip
            nodejs_20
            git
            ripgrep
            jq
          ];

          shellHook = ''
            echo "🚀 Entered hermetic Nix dev environment [$(python3 --version)]"
          '';
        };
      });
}
```

---

## 3. Automation & Direnv Integration

1. **Automatic Activation**: Add `use flake` to `.envrc` in the project root.
2. **Fast Caching**: Use `nix-direnv` to cache shell evaluations and avoid delay when changing directories:
   ```bash
   # In .envrc
   if ! has nix_direnv_version || ! nix_direnv_version 3.0.4; then
     source_url "https://raw.githubusercontent.com/nix-community/nix-direnv/3.0.4/direnvrc" "sha256-..."
   fi
   use flake
   ```
3. **Updating Dependencies**:
   ```bash
   # Update a specific input
   nix flake lock --update-input nixpkgs

   # Audit inputs
   nix flake metadata
   ```
