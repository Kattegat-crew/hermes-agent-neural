# Historical Langfuse Server Migration Proposal — DECLINED

* **Associated spec**: [01-spec.md](./01-spec.md)
* **Associated design**: [02-design.md](./02-design.md)
* **Status**: Historical evidence only — the user rejected this heavy server-migration route in favor of existing Hermes + existing Langfuse.
* **Scope**: Preserve the previously prepared version/capacity/backup/restore/validation/rollback analysis for reference. Nothing below is the current plan or authorizes installation, image pulls, backups, database queries, service changes, credentials access, or traffic movement.
* **Inventory snapshot**: Reported 2026-10-17 02:50 UTC (2026-10-16 local, America/Bogota)

> **Superseded decision:** Do not execute this v3/v4 migration route. The current objective is to assess a minimum compatible Hermes transport using the already-running Langfuse `2.95.11`; no new server, collector, cloud resource, or dependency is in scope.

## Historical recommendation (not current plan)

Prepare a staged migration from the current Langfuse v2 deployment to the SDK4-compatible server route:

1. Run a parallel Langfuse `3.29.0` stage with background migrations disabled until traffic has shifted. Since `3.29.0` is below the SDK4 server minimum `3.63.0`, use this bridge to validate UI, authentication, and migration behavior only; do not claim SDK4 ingestion compatibility or promise uninterrupted SDK4 ingestion through this stage.
2. Enable and complete the four v3 background migrations sequentially; then advance to the `3.225` image alias resolved to config version `3.225.11`, pinned by digest.
3. Upgrade ClickHouse to the v4-compatible `25.12` digest while still on v3, then move to Langfuse `4.63.0` initially in `legacy` write mode—not `dual` or `events_only`.
4. Keep SDK `4.15.2` pinned; do not reinstall or downgrade it. Do not expect SDK4 ingestion during the `3.29.0` bridge. Retire the legacy SDK2 producer alias before a later, separately reviewed `events_only` cutover.

This is a proposed destination, not a deployment-ready plan. Current host headroom, shared PostgreSQL, unknown Langfuse database size, unverified backups/restores, incomplete secret mapping, and unknown capture configuration are blocking gates. The final operational choice, capacity provision, backup/restore rehearsal, maintenance window, and production authorization remain open.

## Evidence and limits

### Current topology and capacity snapshot

| Area | Read-only inventory result | Limit / implication |
|---|---|---|
| Langfuse | Server `2.95.11`, one container observed, `400 MiB` memory limit / about `197 MiB` use | A single utilization sample is not a capacity forecast. |
| Compose ownership | `/opt/docker/langfuse/docker-compose.yml` exists outside this Git repository | This proposal does not edit it. |
| Host | 8 CPU; reported total memory `25.2 GB`, available `11.7 GB`; 8 GB swap, `0.87 GB` used; load `6.19 / 5.80 / 6.15`; free disk `199 GB` | Snapshot only; do not treat load or free disk as a throughput or backfill forecast. |
| PostgreSQL | Shared `infra-postgres` PostgreSQL `16.10`, pgvector `0.8.0-pg16`; physical volume about `917 MB` serving other applications too | Langfuse database name and logical size are unknown. Do not infer them from the shared volume or dump/restore the whole cluster. Do not upgrade PostgreSQL as part of this proposal. |
| ClickHouse / Blob | No ClickHouse deployment was found in the inventory; v3/v4 object-store readiness is not established | New components and storage location are required, subject to a capacity and destination decision. |
| Redis | Public Redis image manifest config reports `REDIS_VERSION=7.4.11` | This is image metadata, not evidence of the production Compose setting or deployed Redis version; service ownership and readiness remain unknown. |
| Auth/config | OIDC and NextAuth names are present, but effective authentication is unverified. Vault mapping has three crypto fields; project/API-key mapping is incomplete. | Preserve existing auth/encryption/project-key behavior via Vault. Do not place secret values or Vault paths in this document. |

Official Langfuse minimum sizing totals **11 CPU and 25.5 GiB** for web, worker, PostgreSQL, Redis, ClickHouse, and local MinIO/blob storage. If PostgreSQL is external/shared, the listed local minimum is **9 CPU / 21.5 GiB**; with external PostgreSQL and blob storage it is **7 CPU / 17.5 GiB**. These are vendor minimums, not a workload model. The reported host has 8 CPU and 11.7 GB available memory; GB/GiB are not assumed interchangeable. Do not claim the host is deployment-ready or mathematically incapable of every low-load deployment from this one sample. Before placing services, choose either capacity expansion/dedicated capacity or an explicitly approved managed ClickHouse/blob destination, then measure workload and headroom. No vendor purchase, account creation, or new-destination access is authorized.

### Backup and tool evidence

- One candidate SQL backup of about `1.277 GB` dated 2026-10-14 was found; no successor restore proof was established. Its existence is not evidence of recoverability.
- On PROD, `restic 0.16.4` and `rclone 1.60.1-DEV` were observed. A systemd-only search found no Langfuse backup unit; this does not prove that no other scheduler or backup path exists.
- No database backup, ClickHouse backup, object-store backup, restore, image pull, or service restart was performed for this proposal.
- The Langfuse database name and logical size, ClickHouse history size, object-store size, retention period, throughput, and acceptable RPO/RTO remain unknown. Do not create cluster-wide dumps, restore the shared PostgreSQL cluster, or invent capacity/RPO/RTO values.

## Version route and compatibility

| Stage | Proposed exact image/version | Purpose and gate |
|---|---|---|
| Current | `2.95.11` | Existing v2 service. |
| Parallel bridge | `3.29.0` | Langfuse recommends this checkpoint for parallel v2/v3 operations; keep background migrations disabled until traffic shifts. This version is below SDK4's server minimum; validate UI/auth/migration only, not SDK4 ingestion. |
| Latest-v3 checkpoint | Registry alias `3.225`, resolved config version `3.225.11` | Pin web and worker digests below; complete all four v3 background migrations before proceeding. A `3.225.12` release exists, but its image endpoint returned 404 in the supplied manifest check; do not target it. |
| V4 server | `4.63.0` | Start initially in `legacy` write mode with native OTEL `dual_write`; consider v4 `dual` only after a separately approved healthy transition. Do not begin in `events_only`. |
| ClickHouse | Tag `25.12` pinned by digest below | Meet the v4 minimum before upgrading the server. Reported patch label `25.12.11.4` was not independently verified as the exact tag in this preparation. |
| Redis | Public image manifest config reports `REDIS_VERSION=7.4.11`; tag `7` pinned by digest below | The image metadata is not proof of deployed runtime version. Verify the active service and resource ownership before migration. |
| PostgreSQL | Keep shared `16.10` / `pgvector 0.8.0-pg16` | V4 requires PostgreSQL `15+`; preserve the existing shared service. No PG image digest was captured and no PG upgrade is proposed. |

The selected Hermes plugin remains SDK `4.15.2`; Langfuse documents Python SDK v4 compatibility with server `>=3.63.0`, while server `2.95.11` and bridge `3.29.0` are below that minimum. Do not claim SDK4 ingestion compatibility at the v3.29 bridge or promise uninterrupted SDK4 ingestion through it. The selected SDK4 positive ingestion canary belongs only at the compatible `3.225.11` or v4 checkpoint, after stage-specific auth/migration checks. The v3-to-v4 guide distinguishes the v4 server upgrade from the later data-model cutover. In `legacy` and `dual` modes, v3 APIs and older SDK producers continue to work; in `events_only`, Python SDK v2 and older are rejected and legacy ingestion/read APIs stop working. Therefore, do not claim v4 always rejects SDK2: that rejection applies to the `events_only` mode. The SDK4 selected PM runtime already imports; this proposal does not reinstall or downgrade it.

### Proposed initial v4 configuration (not applied)

Start v4 in legacy compatibility mode with native OTEL behavior set to dual-write, while keeping historic backfill and preview opt-in disabled:

```dotenv
LANGFUSE_MIGRATION_V4_WRITE_MODE=legacy
LANGFUSE_MIGRATION_V4_NATIVE_OTEL_BEHAVIOUR=dual_write
LANGFUSE_MIGRATION_V4_ALLOW_PREVIEW_OPT_IN=false
LANGFUSE_BACKGROUND_MIGRATION_V4_ENABLE_HISTORIC_BACKFILL=false
```

This is a proposed configuration shape only; no config or service was changed. Historic backfill is a one-time operation. Keep it disabled until a later, separately approved transition to `dual` has been confirmed healthy; starting backfill too early can miss the intervening data interval. During any later `dual` period, keep backfill disabled until deliberate read-path and propagation validation is complete. Do not rely on defaults to select `events_only`; that mode requires a separate explicit decision after all legacy producers and consumers are retired or migrated.

### Proposed image bill of materials

These immutable digests are from the supplied read-only public-manifest inventory. No image layers were pulled for this work. Reconfirm tag-to-digest resolution and architecture immediately before any separately authorized deployment; a digest is not permission to install an image.

| Component | Proposed image pin | Evidence / qualification |
|---|---|---|
| Langfuse web bridge | `docker.langfuse.com/langfuse/langfuse:3.29.0@sha256:726e1b081e71fffcd24c810d71dbd6ce655d351459aff26cf5c40dca2ab0d01c` | Read-only manifest result. |
| Langfuse worker bridge | `docker.langfuse.com/langfuse/langfuse-worker:3.29.0@sha256:0fc868c5188d0d1c672f9644ea5996a1d53bc737d002dc4207b71c425cb80b7a` | Read-only manifest result. |
| Langfuse web v3 checkpoint | `docker.langfuse.com/langfuse/langfuse:3.225@sha256:a343f64e035eb01aeea358703a0428945d909d01e19452509a5a830862dda878` | Config reports version `3.225.11`. |
| Langfuse worker v3 checkpoint | `docker.langfuse.com/langfuse/langfuse-worker:3.225@sha256:8a28c946bb5401eef488153fa294db5a79bd99dd5c90db8e4d39559374c9ebd3` | Read-only manifest result. |
| Langfuse web v4 | `docker.langfuse.com/langfuse/langfuse:4.63.0@sha256:67f48d12a190e4ad585249c75ae1ce172b449de3dbbe7486b8179cd28e21408e` | Read-only manifest result. |
| Langfuse worker v4 | `docker.langfuse.com/langfuse/langfuse-worker:4.63.0@sha256:ca32a8fb2a214c7b5f42dd9c540c8072e41db659cb621f317911ce695ad6bca2` | Read-only manifest result. |
| ClickHouse | `docker.io/clickhouse/clickhouse-server:25.12@sha256:8a790dd3468db22b1d4e7b18a176f378ff5ff6053b9c48dd4ea1fa71a24c5ba6` | Digest resolved from the `25.12` family; exact patch tag/version not separately verified. |
| Redis | `docker.io/library/redis:7@sha256:4fa24486b8bcca8eec45ee0eb166edc674795e53a2b53d1a9ef263eecebaac85` | Public image manifest config reports `REDIS_VERSION=7.4.11`; this is not evidence of the production Compose/runtime version. |
| MinIO/blob | `cgr.dev/chainguard/minio@sha256:c93745c56fccdaf0e5dcb88999a96a65a136428beb045ef5d546255a80d747a7` | Immutable digest reported; software version label unverified. Not new-install approval. |

## Backup, restore, and rollback gates

No backup work is authorized or performed now. Before migration is proposed for execution, the operator must complete and independently review these controls:

1. Resolve the Langfuse database identity using an explicitly authorized credential source without logging credentials. Capture a database-scoped PostgreSQL custom-format dump, required role/grant/ACL/owner references, and a non-secret config snapshot. Preserve encryption salts/keys, NextAuth/OIDC configuration, and project API keys only through the approved Vault process; never in Git, Markdown, shell history, or an unencrypted backup.
2. Include the relevant ClickHouse and S3/blob data in the snapshot plan. Immediately before the v4 server/schema step, take a consistent PostgreSQL plus ClickHouse snapshot; the v3-to-v4 migration also depends on the blob/event store and its retention/versioning policy. Establish a write-freeze/queue-drain boundary for consistency and record it in the approved runbook.
3. Encrypt backups, restrict access, record cryptographic checksums and retention, and prove the backup tool reports success. Do not infer success from an artifact's name or size.
4. Restore into an isolated database/stack—not the shared PostgreSQL cluster—and rehearse both application compatibility and recovery. Verify aggregates/counts, project/user identities, API-key authentication without exposing key values, and historical trace IDs while avoiding trace payload inspection. Record exact restore time and observed result to inform, not invent, RPO/RTO.
5. Verify successful backup and restore using the selected approved tooling before any traffic cutover. The existing old SQL artifact is not a substitute for a fresh, verified, complete migration backup.

Rollback boundaries differ by stage:

- **Before v3 traffic shift**: Keep v2 serving traffic. Any test instance must use its isolated resources; no shared DB mutation is authorized in this preparation.
- **After v3 migration/new writes**: Do not promise lossless rollback to v2. A v2 restoration requires a database-scoped isolated snapshot or an explicitly approved write-freeze/RPO and verified event replay strategy; restoring the whole shared PostgreSQL cluster is prohibited.
- **V4 while `legacy`/`dual`**: Prefer rolling forward in v4's `legacy` mode. After v4 schema migrations, a plain image swap back to v3 is not safe; an official ClickHouse schema rewind or matched pre-upgrade PostgreSQL+ClickHouse restore and rehearsal is required. Restoring pre-upgrade snapshots loses post-snapshot data.
- **`events_only` cutover**: Treat as the irreversible data-model boundary. New events land only in the new tables; a v3 rollback would miss post-cutover data. Do not cross this boundary until all SDK2 legacy aliases and other legacy clients are retired, historic-data coverage is accepted, and a separately approved write-freeze/RPO/replay plan exists.

## Staged validation and approval gates

The following are acceptance gates, not commands to run now:

1. **Historical review status**: The user declined this migration route in favor of a lightweight Hermes adapter. The feature-branch-chain decision now applies only to the current local Hermes source work units; it does not revive this migration proposal or authorize deployment.
2. **Capacity and ownership**: Confirm service ownership, resource allocations, available storage, network/identity/auth, and target host/destination. Choose dedicated/expanded capacity or explicitly approved managed services. An isolated performance/staging test needs its own authorization.
3. **Backup/restore rehearsal**: Prove the database-scoped and ClickHouse/blob restore in an isolated stack before moving traffic.
4. **V2 → V3**: Keep v2 intact; on the `3.29.0` bridge validate UI/auth/migration behavior only. Do not send or claim SDK4 ingestion canaries here. Set v3 background migrations off until shift, then turn them on and observe each migration until complete.
5. **V3 checkpoint**: Verify all v3 migrations are complete on `3.225.11`, stable queue/worker health, UI/API reads, project/auth/key preservation, and an approved no-sensitive-content SDK4 canary before v4. A successful HTTP `207` is only event acceptance/queueing; verify the authorized canary ID becomes queryable/UI-visible after asynchronous processing.
6. **V3 → V4**: Upgrade ClickHouse first, verify required grants and capacity, snapshot PostgreSQL and ClickHouse, then deploy v4 initially in `legacy` with the proposed native OTEL `dual_write` configuration. Keep SDK4.15.2 and all existing producers stable; validate compatible SDK4 ingest, reads, OIDC/NextAuth, projects, and keys. A later `dual` write-mode transition requires separate approval and health/read-path/propagation checks. Do not change capture mode to `full` or broaden telemetry as part of migration.
7. **Later data-model cutover**: Keep v4 `legacy`/`dual` until every producer is compatible, the SDK2 alias is retired, any evaluators/exports/API consumers are migrated, and history is backfilled or covered by a full accepted retention rollover. Only a separate review and explicit user approval may select `events_only`.

Every stage requires a phase reviewer and a documented go/no-go. Fail closed on unknown DB size, unverified backup/restore, incomplete migrations, capacity shortfall, auth/key loss, unhealthy queue/worker, or privacy drift. This proposal does not authorize an image pull, backup, install, deployment, service operation, or production trace.

## Sources

- [Langfuse v2 → v3 self-hosted migration guide](https://langfuse.com/self-hosting/upgrade/upgrade-guides/upgrade-v2-to-v3) — parallel v3.29.0 bridge, background migration sequencing, required components.
- [Langfuse v3 → v4 self-hosted migration guide](https://langfuse.com/self-hosting/upgrade/upgrade-guides/upgrade-v3-to-v4) — ClickHouse minimum/version order, `legacy`/`dual`/`events_only`, history backfill, rollback constraints.
- [Langfuse scaling requirements](https://langfuse.com/self-hosting/configuration/scaling) — service minimum CPU and memory guidance.
- [Langfuse SDK/server compatibility](https://langfuse.com/docs/compatibility) — supported server floor for SDKs.
- [Langfuse SDK overview](https://langfuse.com/docs/observability/sdk/overview) — SDK/server compatibility requirements.
- [Langfuse v4.63.0 Compose source](https://github.com/langfuse/langfuse/blob/v4.63.0/docker-compose.yml), [v3.29.0 release](https://github.com/langfuse/langfuse/releases/tag/v3.29.0), [v3.225.11 release](https://github.com/langfuse/langfuse/releases/tag/v3.225.11), [v4.63.0 release](https://github.com/langfuse/langfuse/releases/tag/v4.63.0).

## Preparation status

No backups, restore rehearsals, capacity tests, image pulls, migration commands, service restarts, or traffic shifts were performed during this prior preparation. Database size, current ClickHouse/blob service, backup completeness, restore behavior, event throughput, and available destination capacity remain unknown. The user declined the migration route; this document is retained as historical evidence only, not an active proposal or deployment plan.
