"""schema_loader.py — Dynamic Ground Truth & Archetype Resolver for Jev Evaluator.

Provides 100% scalable auto-discovery for all Hermes agent profiles across DEV and PROD.
When a new agent is added to the fleet, GroundTruthManager automatically resolves its
archetype and builds the evaluation payload for Jev System One without requiring any
code changes.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


KNOWLEDGE_DIR = Path(__file__).resolve().parent
ARCHETYPES_PATH = KNOWLEDGE_DIR / "archetypes.json"
REGISTRY_PATH = KNOWLEDGE_DIR / "profiles_registry.json"
CASINO_GT_PATH = KNOWLEDGE_DIR / "casino_ground_truth.json"


class GroundTruthManager:
    """Singleton manager for archetypes, profile registry, and ground truth data."""

    def __init__(self, knowledge_dir: Path = KNOWLEDGE_DIR):
        self.knowledge_dir = Path(knowledge_dir)
        self.archetypes: Dict[str, Any] = {}
        self.registry: Dict[str, Any] = {}
        self.casino_gt: Dict[str, Any] = {}
        self._load_all()

    def _load_all(self) -> None:
        if ARCHETYPES_PATH.exists():
            with open(ARCHETYPES_PATH, "r", encoding="utf-8") as f:
                raw_arch = json.load(f).get("archetypes", {})
                # Normalize questions to dict format expected by Jev wire API
                for arch_key, arch_val in raw_arch.items():
                    raw_q = arch_val.get("evaluation_questions", {})
                    if isinstance(raw_q, list):
                        norm_q = {}
                        for item in raw_q:
                            q_id = item.get("id")
                            if q_id:
                                norm_q[q_id] = {k: v for k, v in item.items() if k != "id"}
                            else:
                                norm_q[f"q_{len(norm_q)}"] = item
                        arch_val["evaluation_questions"] = norm_q
                self.archetypes = raw_arch

        if REGISTRY_PATH.exists():
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                self.registry = json.load(f).get("profiles", {})

        if CASINO_GT_PATH.exists():
            with open(CASINO_GT_PATH, "r", encoding="utf-8") as f:
                self.casino_gt = json.load(f)

    def resolve_archetype(self, profile_name: str, profile_dir: Optional[str] = None) -> str:
        """Resolve the archetype of an agent profile via 4-tier discovery:
        1. Explicit match in profiles_registry.json
        2. HERMES_ARCHETYPE in profile .env file
        3. Semantic keyword analysis in SOUL.md
        4. Fallback to general_assistant
        """
        # Tier 1: profiles_registry.json
        if profile_name in self.registry:
            arch = self.registry[profile_name].get("archetype")
            if arch and arch in self.archetypes:
                return arch

        # Look for profile directory in standard paths if not provided
        candidates = []
        if profile_dir:
            candidates.append(Path(profile_dir))
        candidates.extend([
            Path(f"/root/hermes-agent-legacy-docker/data/profiles/{profile_name}"),
            Path(f"/opt/hermes/data/profiles/{profile_name}"),
            Path(f"/opt/data/profiles/{profile_name}")
        ])

        found_dir: Optional[Path] = None
        for c in candidates:
            if c.is_dir():
                found_dir = c
                break

        if found_dir:
            # Tier 2: HERMES_ARCHETYPE in .env
            env_file = found_dir / ".env"
            if env_file.exists():
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            m = re.match(r"^HERMES_ARCHETYPE\s*=\s*['\"]?([a-zA-Z0-9_\-]+)['\"]?", line.strip())
                            if m:
                                cand_arch = m.group(1).lower().replace("-", "_")
                                if cand_arch in self.archetypes:
                                    return cand_arch
                except Exception:
                    pass

            # Tier 3: Semantic keywords in SOUL.md
            soul_file = found_dir / "SOUL.md"
            if soul_file.exists():
                try:
                    with open(soul_file, "r", encoding="utf-8") as f:
                        text = f.read().lower()

                    if any(k in text for k in ("casino", "anfitrión virtual", "ruleta", "bono")):
                        return "casino_host"
                    if any(k in text for k in ("asistente personal", "asistente exclusivo", "misión: asistente", "asistente de oficina")):
                        return "personal_executive_assistant"
                    if any(k in text for k in ("técnico", "arquitectura", "kamehameha", "muten roshi", "desarrollo", "código", "backend")):
                        return "technical_assistant"
                    if any(k in text for k in ("copy", "ads", "guion", "anti-slop", "social media", "reel", "brand voice")):
                        return "content_marketing"
                    if any(k in text for k in ("sre", "observabilidad", "mantenimiento", "uptime", "vigila")):
                        return "infrastructure_admin"
                except Exception:
                    pass

        # Tier 4: Fallback
        return "general_assistant"

    def get_evaluation_bundle(self, profile_name: str, profile_dir: Optional[str] = None) -> Dict[str, Any]:
        """Build the full context, hard rules, and questions bundle ready for Jev System One."""
        archetype_key = self.resolve_archetype(profile_name, profile_dir)
        archetype_def = self.archetypes.get(archetype_key, self.archetypes.get("general_assistant", {}))
        profile_meta = self.registry.get(profile_name, {})

        # Build comprehensive ground-truth context string
        context_parts: List[str] = [
            f"EVALUATION ARCHETYPE: {archetype_def.get('name', archetype_key)}",
            f"ARCHETYPE DESCRIPTION: {archetype_def.get('description', '')}",
            f"AGENT PROFILE NAME: {profile_name}",
        ]

        if profile_meta:
            context_parts.extend([
                f"DISPLAY NAME: {profile_meta.get('display_name', profile_name)}",
                f"OWNER / AUDIENCE: {profile_meta.get('owner', 'N/A')}",
                f"PROFILE DESCRIPTION: {profile_meta.get('description', '')}",
            ])
            overrides = profile_meta.get("overrides", {})
            if overrides:
                context_parts.append(f"SPECIFIC CONSTRAINTS & OVERRIDES: {json.dumps(overrides, ensure_ascii=False)}")

        # Add domain ground truth if casino host
        if archetype_key == "casino_host":
            context_parts.append("\n=== CASINO DOMAIN GROUND TRUTH ===")
            forbidden = (
                self.casino_gt.get("forbidden_compliance_dictionary")
                or self.casino_gt.get("global_guardrails", {}).get("prohibited_platform_terms", [])
            )
            if forbidden:
                context_parts.append(f"FORBIDDEN WORDS (Zero Tolerance): {', '.join(forbidden)}")
            
            entities = self.casino_gt.get("casinos") or self.casino_gt.get("brands") or {}
            for b_key, b_val in entities.items():
                context_parts.append(f"\nBRAND: {b_val.get('brand_name')} (NIT: {b_val.get('nit')})")
                context_parts.append(f"Official Website: {b_val.get('official_website') or b_val.get('web_portal')}")
                context_parts.append(f"Roulette URL: {b_val.get('roulette_link') or b_val.get('roulette_portal')}")
                context_parts.append(f"Promos: {json.dumps(b_val.get('promotions', {}), ensure_ascii=False)}")
                redemp = b_val.get('redemption_rules', [])
                if isinstance(redemp, dict):
                    redemp = [f"{k}: {v}" for k, v in redemp.items()]
                context_parts.append(f"Redemption Rules: {'; '.join(redemp)}")
                
                branches = b_val.get('official_venues') or b_val.get('branches') or []
                if isinstance(branches, dict):
                    venues_list = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in branches.items()]
                elif isinstance(branches, list):
                    venues_list = [f"{v.get('city', v.get('name', ''))}: {v.get('address', '')} ({v.get('google_maps_url', v.get('maps_url', ''))})" for v in branches if isinstance(v, dict)]
                else:
                    venues_list = []
                context_parts.append(f"Official Venues: {'; '.join(venues_list)}")


        hard_rules = archetype_def.get("hard_compliance_rules", [])
        questions = archetype_def.get("evaluation_questions", {})

        return {
            "profile_name": profile_name,
            "archetype": archetype_key,
            "archetype_name": archetype_def.get("name"),
            "hard_compliance_rules": hard_rules,
            "tone_guidelines": archetype_def.get("tone_guidelines"),
            "tool_usage_expectations": archetype_def.get("tool_usage_expectations"),
            "context": "\n".join(context_parts),
            "questions": questions
        }


# Convenience singleton
default_manager = GroundTruthManager()


def get_ground_truth_for_profile(profile_name: str, profile_dir: Optional[str] = None) -> Dict[str, Any]:
    """Top-level helper function to retrieve evaluation bundle for a profile."""
    return default_manager.get_evaluation_bundle(profile_name, profile_dir)
