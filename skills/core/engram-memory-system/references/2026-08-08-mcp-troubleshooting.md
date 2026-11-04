# Engram MCP — Session Troubleshooting Log (08/08/2026)

## Symptoms

Engram MCP responded to 1 engram tool call, then became unreachable with:
```
MCP server 'engram' is unreachable after N consecutive failures. Auto-retry available in ~55s.
```

## Root Cause

**Not a bug in engram.** The `Permission denied` exceptions from Python code writing to `.hermes/` and `.engram/` caused the MCP subprocess to crash after handling 1-2 requests. Hermes' circuit breaker then parked the server after 4+ failed consecutive handshakes.

The crash pattern was:
1. engram MCP starts and responds to first call (mem_stats, mem_context, etc.)
2. Server tries to write to SQLite/state → Permission denied
3. Server crashes, Hermes logs "Connection closed" / "McpError"
4. Hermes retries, fails 3 more times → server parked
5. Auto-retry window ~51-55s before next attempt

## Fix

```bash
# 1. Fix ownership (UID 10000 = hermes user inside container)
chown -R hermes:hermes /opt/data/home/.hermes/ /opt/data/home/.engram/

# 2. Clear circuit breaker by restarting container
docker restart hermes-agent
```

## Verification Pattern

After fix, engram handles 6+ consecutive calls without crashing:
1. mem_stats — OK
2. mem_context — OK
3. mem_current_project — OK  
4. mem_session_start — OK
5. mem_save — OK
6. mem_judge — OK
7. mem_search — OK

## Config Files

### Main config: `/opt/data/config.yaml`
Has engram MCP defined as:
```yaml
mcp_servers:
  engram:
    command: engram
    args:
    - mcp
```
(Without `--tools=agent` — exposes ALL tools including mem_stats, mem_context)

### gentle-ai sync config: `/opt/data/home/.hermes/config.yaml`
```yaml
mcp_servers:
  engram:
    command: /usr/local/bin/engram
    args:
    - mcp
    - --tools=agent
```
(With `--tools=agent` — exposes only agent-facing tools like mem_save, mem_search, mem_judge)

## .engram/config.json

Created to resolve ambiguous project error (multiple git repos in cwd):

```json
{"project_name": "hermes"}
```

- Field must be `project_name`, NOT `project` (engram validates required field)
- Without this file, engram tries auto-detection from git remotes and fails with "ambiguous project: multiple git repos found in cwd"
- The recovery_token from the ambiguous error allows one-shot writes with `project_choice_reason=user_selected_after_ambiguous_project`

## Memory Stats After Migration (4 observations)

Project "hermes" now has 4 active observations:
1. persona: "Ragnar - Chief Orchestrator - Core Identity"
2. persona: "Equipo NeuralCrew Labs"
3. client: "Clientes NeuralCrew Labs"  
4. architecture: "Infraestructura y Stack"

All dedup conflicts resolved as "compatible" (distinct categories, kept separate).