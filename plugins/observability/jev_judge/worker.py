"""worker.py — Background Evaluation Daemon for Jev System One.

Polls Langfuse Postgres for closed conversation traces lacking Jev scores,
resolves profile archetype, executes Jev evaluation, and attaches native scores.
Runs asynchronously without adding latency to live bot interactions.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("jev_worker")

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from evaluator import JevJudge

# Load environment from .env if available
for env_path in [Path("/opt/hermes/.env"), Path("/root/hermes-agent-legacy-docker/.env"), Path(".env")]:
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass


def query_unscored_traces(limit: int = 10, db_host: str = "100.73.30.29") -> List[Dict[str, Any]]:
    """Query recent conversation traces that have not yet been evaluated by Jev."""
    sql = f"""
    SELECT t.id, t.name, t.user_id, t.input::text, t.output::text
    FROM traces t
    WHERE t.user_id IS NOT NULL 
      AND t.input IS NOT NULL 
      AND t.output IS NOT NULL
      AND t.output::text NOT LIKE '%[SILENT]%'
      AND NOT EXISTS (
          SELECT 1 FROM scores s 
          WHERE s.trace_id = t.id AND s.name LIKE 'jev_%'
      )
    ORDER BY t.timestamp DESC
    LIMIT {limit};
    """
    
    raw = None
    # 1. Try local docker exec first (if running on PROD host)
    try:
        res = subprocess.run(
            ["docker", "exec", "infra-postgres", "psql", "-U", "langfuse", "-d", "langfuse", "-t", "-A", "-F", "|||", "-c", sql],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=True
        )
        raw = res.stdout.decode("utf-8").strip()
    except Exception:
        raw = None

    # 2. Fallback to SSH to db_host if local docker exec failed
    if raw is None:
        cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no", f"root@{db_host}",
            f"docker exec infra-postgres psql -U langfuse -d langfuse -t -A -F '|||' -c \"{sql}\""
        ]
        try:
            raw = subprocess.check_output(cmd, timeout=15).decode("utf-8").strip()
        except Exception as e:
            logger.error("Failed to query Postgres traces via Docker/SSH: %s", e)
            return []

    traces = []
    for line in raw.splitlines():
        parts = line.split("|||")
        if len(parts) >= 5:
            t_id, t_name, t_user, t_in, t_out = parts[0], parts[1], parts[2], parts[3], parts[4]
            # Extract plain text content if JSON wrapped
            user_msg = t_in
            if t_in.startswith("{"):
                try:
                    user_msg = json.loads(t_in).get("content", t_in)
                except Exception:
                    pass

            bot_msg = t_out
            if t_out.startswith("{"):
                try:
                    bot_msg = json.loads(t_out).get("content", t_out)
                except Exception:
                    pass

            # Ignore silent internal cron messages or empty output
            if bot_msg and bot_msg.strip() != "[SILENT]":
                traces.append({
                    "id": t_id,
                    "name": t_name,
                    "profile_name": t_user,
                    "input": user_msg,
                    "output": bot_msg
                })
    return traces


def process_batch(judge: JevJudge, limit: int = 5) -> int:
    """Process a single batch of unscored traces."""
    unscored = query_unscored_traces(limit=limit)
    if not unscored:
        logger.debug("No unscored traces pending.")
        return 0

    processed = 0
    for t in unscored:
        t_id = t["id"]
        profile = t["profile_name"]
        logger.info("Evaluating trace %s for bot [%s]...", t_id, profile)
        
        res = judge.evaluate_turn(
            profile_name=profile,
            user_input=t["input"],
            bot_output=t["output"],
            trace_id=t_id
        )
        
        if res.get("status") == "success":
            logger.info("Trace %s successfully evaluated (Archetype: %s, Answers: %d)",
                        t_id, res.get("archetype"), len(res.get("answers", {})))
            processed += 1
        else:
            logger.warning("Trace %s evaluation skipped/failed: %s", t_id, res.get("reason") or res.get("error"))
            
    return processed


def run_daemon(poll_interval: float = 30.0, batch_size: int = 10):
    """Run persistent background loop."""
    logger.info("Starting Jev Evaluation Daemon (Poll interval: %.1fs, Batch size: %d)...", poll_interval, batch_size)
    judge = JevJudge()
    while True:
        try:
            count = process_batch(judge, limit=batch_size)
            if count > 0:
                logger.info("Processed %d traces in batch.", count)
        except Exception as e:
            logger.error("Error in daemon loop: %s", e)
        time.sleep(poll_interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jev Evaluation Background Worker")
    parser.add_argument("--once", action="store_true", help="Process one batch and exit")
    parser.add_argument("--limit", type=int, default=10, help="Batch limit per run")
    parser.add_argument("--interval", type=float, default=30.0, help="Daemon poll interval in seconds")
    args = parser.parse_args()

    judge = JevJudge()
    if args.once:
        count = process_batch(judge, limit=args.limit)
        print(f"Processed {count} traces.")
    else:
        run_daemon(poll_interval=args.interval, batch_size=args.limit)
