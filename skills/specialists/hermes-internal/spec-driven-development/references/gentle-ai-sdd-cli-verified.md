# gentle-ai SDD/OpenSpec — command surface verified 19/08/2026

Verified live on this VPS at `/usr/local/bin/gentle-ai` (v2.3.0), against `/opt/repos/golden-game-landing`.

## sdd-status (real output, no change yet)

```
## SDD Status: unresolved
schema: gentle-ai.sdd-status@1
store: openspec
planning_home: /opt/repos/golden-game-landing/openspec
next: sdd-new

### Summary
- apply: blocked
- verify: blocked
- archive: blocked
- tasks: 0/0 complete

### Blocked Reasons
- No active OpenSpec changes found under openspec/changes.
```

Interpretation: the engine is alive and waiting; it expects an OpenSpec `openspec/` root (specs/ + changes/) in each repo. "next: sdd-new" is the bootstrap step — there is NO `sdd-new` binary command; you create the OpenSpec root by hand.

## review status (real live output)

```
gentle-ai review status --cwd /opt/repos/golden-game-landing
{
  "schema": "gentle-ai.review-authority-status/v1",
  "operation": "review/status",
  "repository": "/opt/repos/golden-game-landing",
  "complete": true,
  "authoritative": true,
  "status": "clean",
  "entries": [],
  "locks": [],
  "diagnostics": []
}
```

`complete:true, authoritative:true, status:clean, locks:[]` = healthy, no pending gates.

## Full command groups (from `gentle-ai --help`, tail)

- SDD: `sdd-status [change]`, `sdd-continue [change]`,
  `sdd-attempt <status|begin|finish|reset> --cwd <repo> --change <change>`
  (also accepts `acquire`/`settle` in the orchestration context),
  `sdd-verify-validate --input <path|-> --requirements <n> --scenarios <n>`.
- Review: `review start|capture-result|inspect-candidate|finalize|validate|status|repair|mode`
  plus legacy-v1 compatibility `review-start|review-step|review-resume|review-bundle-export|review-bundle-import|review-validate`.
- Ecosystem: `install`, `uninstall`, `sync`, `skill-registry refresh`, `update`, `upgrade`, `restore`, `doctor`, `version`.

## Paths / env on this VPS

- `gentle-ai`: `/usr/local/bin/gentle-ai` · Engram: `/usr/local/bin/engram` · (GGA also present).
- Safe-directory fix: `git config --global --add safe.directory /opt/repos/<repo>`.

## Source tip (barc@barckcode, 19/08/2026)

- Original: https://x.com/i/status/2090117010604634189
- Brain raw: `/opt/data/brain/raw/x-feed-2026-08-19-barckcode-sdd-multiagente.md`
- Companion spec-driven vibecoder flow: `/opt/data/brain/raw/2026-08-06-twitter-mathieuhq-spec-driven-workflow.md`
  (Hermes → /grill-with-docs → /to-spec → /to-tickets → label agent-ready → Codex dev VPS → PR).