---
name: atlas-best-practices
description: "Use when diffing, linting or applying DB schema migrations."
tags: [atlas, migraciones, esquema, postgres, mysql, ci-cd, declarativo, hcl]
license: MIT
compatibility: hermes, opencode, bash
metadata:
  hermes:
    tags: [atlas, database, migrations, schema, postgres, mysql, ci-cd, devops]
    category: devops
---

# Atlas Database Migrations & Declarative Schema Management

Best practices for managing database schemas declaratively, generating versioned migration files, and validating schema integrity using Atlas (Ariga).

## 1. Core Principles

- **Declarative Schema as Code**: Treat HCL schema files (or ORM models like Prisma/Ent/SQLAlchemy) as the desired state.
- **Versioned Migrations**: Never mutate production databases directly. Generate migration scripts using `atlas migrate diff`.
- **Pre-deployment Verification**: Always run `atlas migrate lint` against a temporary dev container to catch destructive changes (e.g., column drops, type changes causing locks).

---

## 2. Essential Workflows

### A. Inspect Existing Database
Generate an HCL schema representation from a live database:
```bash
atlas schema inspect -u "postgres://user:pass@localhost:5432/dbname?sslmode=disable" > schema.hcl
```

### B. Generate Versioned Migrations (Diff)
Compare desired state in HCL (or models) against current migrations directory:
```bash
atlas migrate diff create_users_table \
  --dir "file://migrations" \
  --to "file://schema.hcl" \
  --dev-url "docker://postgres/16/dev?search_path=public"
```

### C. Lint Migrations (Safety Guard)
Detect data loss, non-concurrent index creation, or table lock risks:
```bash
atlas migrate lint \
  --dir "file://migrations" \
  --dev-url "docker://postgres/16/dev?search_path=public" \
  --latest 1
```

### D. Apply Migrations to Target Database
```bash
# Check pending status
atlas migrate status \
  --dir "file://migrations" \
  --url "postgres://user:pass@localhost:5432/dbname?sslmode=disable"

# Apply pending migrations safely
atlas migrate apply \
  --dir "file://migrations" \
  --url "postgres://user:pass@localhost:5432/dbname?sslmode=disable"
```

---

## 3. Production Invariants for Agents

1. **Dev-URL Required**: Always supply `--dev-url` (using ephemeral Docker or test DB) during diff/lint operations to ensure deterministic SQL calculation.
2. **Never Ignore Destructive Warnings**: If Atlas reports a `DS102` (data loss risk) or `BC102` (backward incompatibility), explicitly migrate with safe multi-step patterns (Add column -> backfill -> make NOT NULL).
