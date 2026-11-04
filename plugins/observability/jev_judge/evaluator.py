"""evaluator.py — Jev System One Decision & Evaluation Engine.

Evaluates Hermes agent turns against archetype-driven ground truth rules and
pushes typed scores/evaluations directly to Langfuse traces.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Canonical paths
PLUGIN_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = PLUGIN_DIR / "knowledge"

try:
    import sys
    if str(KNOWLEDGE_DIR) not in sys.path:
        sys.path.insert(0, str(KNOWLEDGE_DIR))
    from schema_loader import get_ground_truth_for_profile
except Exception as e:
    logger.error("Failed to import schema_loader: %s", e)
    get_ground_truth_for_profile = None


DEFAULT_TYPESAFE_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"


class JevJudge:
    """Core evaluation client connecting Hermes agents to Jev System One."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 15.0
    ):
        self.api_key = (api_key or os.environ.get("TYPESAFE_API_KEY", "")).strip()
        self.endpoint = (endpoint or os.environ.get("TYPESAFE_ENDPOINT") or DEFAULT_TYPESAFE_ENDPOINT).strip()
        self.model = model or os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

        # Fallback to secrets file if env var not set
        if not self.api_key:
            secret_paths = [
                Path("/root/hermes-agent-legacy-docker/data/secrets/typesafe.json"),
                Path("/opt/hermes/data/secrets/typesafe.json"),
                Path("/opt/data/secrets/typesafe.json"),
            ]
            for sp in secret_paths:
                if sp.exists():
                    try:
                        with open(sp, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            self.api_key = data.get("api_key", "").strip()
                            self.endpoint = data.get("endpoint") or data.get("base_url") or self.endpoint
                            if self.api_key:
                                break
                    except Exception as ex:
                        logger.warning("Could not read secrets from %s: %s", sp, ex)

    def evaluate_turn(
        self,
        profile_name: str,
        user_input: str,
        bot_output: str,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate a single agent conversation turn using Jev System One."""
        if not self.api_key:
            return {"status": "skipped", "reason": "Missing TYPESAFE_API_KEY"}

        if not get_ground_truth_for_profile:
            return {"status": "error", "reason": "schema_loader unavailable"}

        bundle = get_ground_truth_for_profile(profile_name)
        archetype = bundle.get("archetype", "general_assistant")
        questions = bundle.get("questions", {})

        if not questions:
            return {"status": "skipped", "reason": f"No questions defined for archetype {archetype}"}

        state_payload = {
            "agent_profile": profile_name,
            "archetype": archetype,
            "ground_truth_context": bundle.get("context", ""),
            "user_input": user_input,
            "bot_output": bot_output,
            **(metadata or {})
        }

        payload = {
            "model": self.model,
            "state": state_payload,
            "questions": questions
        }

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                answers = result.get("answers", {})
                eval_report = {
                    "status": "success",
                    "profile_name": profile_name,
                    "archetype": archetype,
                    "model": result.get("model", self.model),
                    "answers": answers,
                    "trace_id": trace_id
                }

                # Push scores to Langfuse if trace_id is supplied
                if trace_id:
                    self.push_scores_to_langfuse(trace_id, answers)

                return eval_report

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            logger.error("Jev API HTTP %d error: %s", e.code, err_body)
            return {"status": "error", "http_code": e.code, "error": err_body}
        except Exception as e:
            logger.error("Jev evaluation error: %s", e)
            return {"status": "error", "error": str(e)}

    def push_scores_to_langfuse(
        self,
        trace_id: str,
        answers: Dict[str, Any],
        base_url: Optional[str] = None,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None
    ) -> None:
        """Push evaluation answers to Langfuse trace as native scores."""
        base_url = (base_url or os.environ.get("HERMES_LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_BASE_URL") or "").rstrip("/")
        pk = public_key or os.environ.get("HERMES_LANGFUSE_PUBLIC_KEY") or os.environ.get("LANGFUSE_PUBLIC_KEY") or ""
        sk = secret_key or os.environ.get("HERMES_LANGFUSE_SECRET_KEY") or os.environ.get("LANGFUSE_SECRET_KEY") or ""

        if not pk or not sk or not base_url:
            for env_path in [Path("/opt/hermes/.env"), Path("/root/hermes-agent-legacy-docker/.env"), Path(".env")]:
                if env_path.exists():
                    try:
                        with open(env_path, "r", encoding="utf-8") as ef:
                            for eline in ef:
                                eline = eline.strip()
                                if eline and not eline.startswith("#") and "=" in eline:
                                    ek, ev = eline.split("=", 1)
                                    ek, ev = ek.strip(), ev.strip()
                                    if not pk and ek in ("HERMES_LANGFUSE_PUBLIC_KEY", "LANGFUSE_PUBLIC_KEY"):
                                        pk = ev
                                    elif not sk and ek in ("HERMES_LANGFUSE_SECRET_KEY", "LANGFUSE_SECRET_KEY"):
                                        sk = ev
                                    elif not base_url and ek in ("HERMES_LANGFUSE_BASE_URL", "LANGFUSE_BASE_URL"):
                                        base_url = ev.rstrip("/")
                    except Exception:
                        pass

        base_url = base_url or "http://localhost:3000"
        if not pk or not sk:
            logger.warning("Missing Langfuse API keys (pk/sk). Skipping score push.")
            return

        import base64
        auth_header = f"Basic {base64.b64encode(f'{pk}:{sk}'.encode()).decode()}"

        for name, ans in answers.items():
            ans_type = ans.get("type")
            score_val = None
            str_val = None
            comment = f"Jev System One ({ans_type})"

            if ans_type == "noul":
                score_val = float(ans.get("noul", 0.0))
            elif ans_type == "score":
                score_val = float(ans.get("score", 0.0))
            elif ans_type == "choice":
                str_val = str(ans.get("choice", ""))
                score_val = float(ans.get("confidence", 1.0))
                comment = f"Jev choice: {str_val} (conf: {score_val:.2f})"

            score_body = {
                "traceId": trace_id,
                "name": f"jev_{name}",
                "value": score_val if score_val is not None else 0.0,
                "stringValue": str_val,
                "comment": comment
            }

            try:
                score_req = urllib.request.Request(
                    f"{base_url}/api/public/scores",
                    data=json.dumps(score_body).encode("utf-8"),
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(score_req, timeout=5) as score_resp:
                    pass
            except Exception as ex:
                logger.warning("Failed to push score %s to Langfuse: %s", name, ex)
