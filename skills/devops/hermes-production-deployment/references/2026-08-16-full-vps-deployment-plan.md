# Full VPS Deployment Plan Creation — 16 Aug 2026 Session

## Context

User requested a comprehensive deployment plan for a **NEW production VPS** (separate from current dev VPS 147.93.3.250). Initial plan omitted Gentle AI + Engram + GGA. User corrected this. Final plan at `/opt/data/plan-despliegue-nuevo-vps-produccion-v2.md`.

## Key Correction Signal

**User: "Incluiste gentle Ai y engram? Si no, investiga en la memoria y en los docs la función de estos dos"**

This revealed that Gentle AI + Engram are frequently omitted from infrastructure plans. They are the **Neural-Brain** — the system nervous center. Without them:
- Ragnar, OpenCode and Antigravity don't share context
- Each agent starts from zero every session
- MEMORY.md's ~10K char limit is hit constantly

## What was included in the final plan (v2.0)

| Section | Content |
|---------|---------|
| Architecture diagram | Nginx → 4 Hermes agents → Shared infra + Neural-Brain |
| 7-level program list | 0:OS → 1:Core infra → 2:Neural-Brain → 3:Obs → 4:Business → 5:Agents → 6:Web → 7:Future |
| Timeline by day | D1-D5+ with verification checkpoints per step |
| DNS map | neuralcrewlabs.com + subdomains + landing pages |
| Tailscale topology | VPS Prod (new) + VPS Dev (current) + Windows admin |
| Resource limits | CPU/RAM per container totalling ~15.7G of 16G |
| Neural-Brain section | Gentle AI + Engram + GGA architecture, comparison table with MEMORY.md, install commands |
| Risk table | 13 risks with mitigations including Engram DB corruption |
| Decision registry | 10 decisions with rationale |
| Checklist | ~70 verifiable items across all days |

## Gentle AI + Engram installation commands (verified)

```bash
# Gentle AI (trae Engram + GGA)
brew tap gentleman-programming/tap
brew update
pip install gentle-ai

# Verify
gentle-ai doctor  # should show 8/8 checks

# Connect agents
gentle-ai install --agents opencode,gemini-cli,antigravity

# Sync with Hermes
gentle-ai sync

# Configure project
mkdir -p /opt/data/.engram
echo '{"project_name": "neuralcrew"}' > /opt/data/.engram/config.json
chown -R hermes:hermes /opt/data/.engram/

# Verify Engram works
engram mcp --tools=agent
```

## User naming notes
- "talkers" = Tailscale (phonetic Spanish pronunciation)
- "Grame" = Gentle (as in Gentle AI) — confirmed in earlier session