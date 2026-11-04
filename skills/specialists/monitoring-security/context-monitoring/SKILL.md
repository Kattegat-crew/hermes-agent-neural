---
name: context-monitoring
description: "Use when tracking Hermes context and token usage."
tags: [hermes, contexto, tokens, monitoreo, sesiones, costos]
---

# Context Monitoring & Token Tracking

## What it is
Hermes exposes token usage and context metrics through CLI commands and a SQLite database. This skill covers how to monitor context usage, token consumption, and system health.

## Commands

### Quick status
```bash
hermes status          # Overall system status
hermes sessions stats  # Session store statistics
```

### Token analytics
```bash
hermes insights --days 7    # Token usage, costs, tool patterns, activity trends (last 7 days)
hermes insights --days 30   # Last 30 days
```

### Session details
```bash
hermes sessions list --limit 10   # Recent sessions
hermes sessions browse            # Interactive session picker
```

### Custom monitor script
```bash
/opt/data/scripts/context-monitor.sh           # Full report (text)
/opt/data/scripts/context-monitor.sh --json    # JSON output
/opt/data/scripts/context-monitor.sh --quiet   # Minimal output for cron
```

### Direct DB queries
Session data lives in `/opt/data/state.db` (SQLite):
- `input_tokens` — cumulative input tokens (lifetime, not current context)
- `output_tokens` — cumulative output tokens
- `cache_read_tokens` / `cache_write_tokens` — cache usage
- `reasoning_tokens` — reasoning effort tokens
- `estimated_cost_usd` / `actual_cost_usd` — costs
- `end_reason` — 'compression', 'session_reset', 'cli_close', or null (active)

## Key facts
- qwen3.6 context window on nan.builders: ~131,072 tokens
- Hermes auto-compacts at ~60-70% context usage
- `input_tokens` is **cumulative across session lifetime** — includes all compaction cycles
- After compaction, system_prompt is updated with summary, old messages condensed
- System prompt size (~16KB ≈ 12-16k tokens) is the baseline context overhead

## Cron monitoring
Cron job `005151f7eb20` runs context monitor every 30m (3 times), delivers to current chat.

## Related: Loop Detection
If you notice sessions with abnormally high message counts (100+ messages for a simple task), check for loop patterns. See the `loop-detection` skill for prevention. Key indicator: 15+ consecutive tool calls of the same type with the same failure pattern.
