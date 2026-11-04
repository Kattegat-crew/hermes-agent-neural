---
name: identity-cleanup
description: "Use when fixing a person identity across the wiki."
tags: [identidad, limpieza, wiki, memoria, brain, perfiles]
version: 1.0.0
author: Ragnar
license: MIT
metadata:
  hermes:
    tags: [identity, cleanup, wiki, memory, user-profile]
    category: devops
---

# Identity Cleanup Protocol

Systematic approach to updating person identities across all knowledge systems.
Covers replacing old names, Discord IDs, roles, and all cross-references.

## When to Use

- User corrects their name/identity after a session reset
- Wrong person profile was stored and needs replacement
- Discord usernames change
- Role changes (CEO → CTO, etc.)
- Multiple old references exist from previous corrections that were added instead of replaced

## The Core Problem

When identity corrections happen across sessions, the **persistent memory** gets updated correctly, but **static wiki files** don't. The agent loads the wiki files on every session start, so old references persist forever.

**Result:** Agent works correctly mid-session (memory says "Jesús") but starts every new session saying "Jonathan" (ACCESS.md still says "Jonathan").

## Decision Framework

| Element | Action |
|---------|--------|
| **Person name** | Update everywhere |
| **Discord username** | Update in ACCESS.md, HERMES.md, security files |
| **Discord ID** | Update if changed, remove if deprecated |
| **Roles** | Update in roster, organigrama, entity pages |
| **Entity files** | Update or create new; delete obsolete |
| **Cross-references** | Update ALL files that mention the old name |
| **Memory** | Update persistent memory entry |

## Step-by-Step Process

### 1. Search and Inventory

```bash
# Find ALL references to old name/ID across brain wiki
search_files(pattern="OldName|OldDiscordID|OldNickname", path="/opt/data/brain", output_mode="content")
```

Categorize findings:
- **Core files** (injected every session): ACCESS.md, HERMES.md, SOUL.md, USER.md
- **Entity pages**: `entities/*.md` — person profiles
- **Cross-references**: organigrama, nexa_labs, ragnar, hermes_messaging, hermes_security, hermes_context_files
- **Concept pages**: organigrama, financiamiento, infrastructure
- **Tasks**: `tasks/pending.md`
- **Obsolete files**: old entity files that should be deleted

### 2. Update Core Files First

These load into every session — fix them first:

| File | What to change |
|------|----------------|
| `ACCESS.md` | Roster table — role, name, Discord username, IDs |
| `HERMES.md` | Communication section — admin/CTO names and Discord |
| `entities/<old_name>.md` | Update content OR delete if replacing |
| `entities/<new_name>.md` | Create new entity page if needed |

**Patch strategy:** Use `patch` with exact strings. Include enough surrounding context to ensure uniqueness.

### 3. Update Cross-References

Search for the old name/nickname and update ALL occurrences:

- `concepts/organigrama.md` — team structure
- `concepts/financiamiento.md` — team references
- `concepts/infrastructure.md` — system owners
- `entities/nexa_labs.md` — company description
- `entities/ragnar.md` — reporting structure
- `entities/hermes_messaging.md` — allowlist references
- `entities/hermes_security.md` — Discord/Telegram IDs
- `entities/hermes_context_files.md` — agent descriptions
- `tasks/pending.md` — task assignments

### 4. Delete Obsolete Entity Files

If a person's entity file is being replaced:

```bash
rm /opt/data/brain/entities/<old_file>.md
```

### 5. Verify — Zero Tolerance

After all patches, run a final search for ALL old identifiers:

```bash
search_files(pattern="OldName|OldNickname|OldDiscordID|OldID", path="/opt/data/brain", output_mode="content")
```

**Expected result: 0 matches.** If any remain, find and fix them.

### 6. Update Persistent Memory

```
memory(action='replace', target='memory',
    content='User: Jesús Díaz (Discord: Jemadiar), CTO. NOT Jonathan...',
    old_text='User: Jonathan (Discord 713538631918157853)...')
```

## Common Pitfalls

- **Adding instead of replacing:** Previous corrections may have added new entries without removing old ones. Always search for ALL variants (full name, nickname, Discord ID, old username).
- **Forgetting cross-references:** The core roster file is only one of many places the name appears. Organigrama, entity pages, tasks, security — all reference team members.
- **Discord IDs vs usernames:** Users may change Discord usernames but keep the same ID. Update BOTH if available. Remove old IDs that are no longer valid.
- **Entity files not auto-synced:** Creating a new entity file doesn't delete the old one. Must manually remove obsolete files.
- **Session memory vs wiki files:** Persistent memory updates mid-session but wiki files persist across sessions. Both must be updated.
- **Signature footers:** Every file has a footer like "*Ragnar — NeuralCrew Labs*". These usually don't need updating for person changes.

## Verification Checklist

After cleanup, confirm:

1. `search_files(pattern="OldName|OldNickname|OldID")` → **0 results**
2. Core roster (ACCESS.md) has correct names, roles, Discord usernames
3. New entity page exists with correct profile
4. Old entity page deleted (if replaced)
5. Cross-references updated in organigrama, nexa_labs, ragnar
6. Security/messaging files updated (no stale Discord IDs)
7. Tasks updated (no references to old names)
8. Persistent memory updated

## Example: Jonathan → Jesús Identity Correction

This is the exact pattern used for the NeuralCrew Labs identity fix:

1. Searched for `Jonathan|Chucho|713538631918157853|742803595241717840` → found 30+ references
2. Updated ACCESS.md roster table
3. Updated HERMES.md communication section
4. Updated Jonathan's entity page with new Discord username
5. Created new Jesús Díaz entity page
6. Deleted old "jesus_chucho.md" entity file
7. Patched 10+ cross-reference files (organigrama, financiamiento, infrastructure, nexa_labs, ragnar, hermes_messaging, hermes_security, hermes_context_files, tasks/pending)
8. Final search → 0 results. Verified clean.
