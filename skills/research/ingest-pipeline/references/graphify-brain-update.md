# Graphify Extract for Brain Knowledge Graph

## Problem

The brain's knowledge graph (`graphify-out/graph.json`) was 3 weeks stale (Aug 16, 2026) and didn't include the 102+ external sources ingested via the wiki pipeline.

## Architecture

`graphify extract` scans `/opt/data/brain/` recursively, calls an LLM backend for semantic extraction, and produces a JSON knowledge graph. The brain contains:
- `entities/` (55) — stable entity pages
- `concepts/` (23) — concept pages  
- `ingestas/` (106+ tuits, 25 repos, 2 tiktoks) — new structured ingesta files
- `raw/` (111) — legacy dump (NOT useful for graph extraction)

## Pitfalls Discovered

### 1. Model Selection
- **deepseek-v4-flash** (default): produces INVALID JSON in graphify extract — chunks get truncated, retried infinitely, and the process hangs. This is a known limitation for graphify's extraction prompt.
- **deepseek-v4-flash-0731**: returns 401 "no access" on NaN-Builders (not enabled in plan).
- **qwen3.6**: WORKS RELIABLY — produces valid JSON for graphify's extraction. This is the correct model for this task.

### 2. Concurrency Limits
- NaN-Builders limits 5 simultaneous requests per API key (ALL accounts share one key).
- The Hermes gateway also uses this key for LLM calls.
- Safe concurrency for graphify: **≤2** (leaves headroom for the gateway).
- Using `--max-concurrency 4` or `8` causes 429 errors when the gateway is also active.

### 3. Output Path
- `graphify extract --out /opt/data/brain/graphify-out` creates the graph at `/opt/data/brain/graphify-out/graphify-out/graph.json` (nested).
- Correct: `--out /opt/data/brain` → graphify creates `graphify-out/` inside, producing `/opt/data/brain/graphify-out/graph.json`.

### 4. Partial Results Are Normal
- graphify reports: `WARNING: N/M semantic chunk(s) failed — see errors above. Partial results returned.`
- This is acceptable — the graph still captures most nodes. Previous successful builds also had partial results.

## Merge Pattern (Cumulative Graph)

The graph must never lose prior nodes when re-extracting. The pattern:

1. **Backup** current `graph.json` → `graph.json.bak`
2. **Extract** new (with `--force`, produces fresh partial graph)
3. **Merge** backup + new → `graph.json`
4. **Cleanup** backup

This uses `graphify merge-graphs`:
```bash
graphify merge-graphs graph.json.bak graph.json --out graph.json
```

Verified: merge produces 2335 nodes (2183 original + 70 new ingestas + 82 deduped) with 2071 edges.

## Cron Script

`/opt/data/scripts/brain_graph_update_wrapper.sh`:
- Runs in background as Hermes cron script-job (`brain-graph-update-noche`, 3:30 AM)
- Executes inside the Docker container via `docker exec hermes-agent`
- Extracts NaN API key from config.yaml (Python YAML parser, not grep — more reliable)
- Model: qwen3.6, concurrency: 2, api-timeout: 90
- Backup → extract → merge → cleanup
- Output to `/tmp/brain_graph_cron.log` (host-visible for diagnostics)

## Verification

After graph update, verify ingestas are indexed:
```python
import json
d = json.load(open('/opt/data/brain/graphify-out/graph.json'))
inest = [n for n in d['nodes'] if 'ingesta' in n.get('label','').lower() or 'x.com' in n.get('label','')]
print(f"{len(d['nodes'])} nodes, {len(inest)} ingesta nodes")
```

## Graph Query

Once the graph is updated, use `graphify query "<question>"` or `python3 /opt/data/tools/memory_graph.py "<question>"` to search semantically.