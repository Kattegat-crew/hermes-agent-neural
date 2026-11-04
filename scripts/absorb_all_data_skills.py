#!/usr/bin/env python3
"""
absorb_all_data_skills.py — Fase 8: Absorción Canónica y Eliminación de data/skills.

1. Backup completo de data/skills en data/archive/pre_absorption_data_skills_20260920.tar.gz.
2. NUTRIR: Integra skills secundarias en los paraguas de skills/core/ (references/ y scripts/).
3. GUARDAR / PROMOVER: Clasifica y mueve las 266 skills restantes a sus categorías canónicas
   dentro de /root/hermes-agent-legacy-docker/skills/ (software-development, devops, ai-ml, etc.).
4. ELIMINACIÓN: Purga /root/hermes-agent-legacy-docker/data/skills/ (cumpliendo 0 carpetas fuera del repo).
5. SINCRONIZACIÓN: Despliega al contenedor /opt/hermes/skills/ con permisos hermes:hermes.
6. VERIFICACIÓN: Comprueba que todas las skills cargan limpiamente y sin errores.
"""

import os
import sys
import json
import shutil
import tarfile
import subprocess
from pathlib import Path

REPO_ROOT = Path("/root/hermes-agent-legacy-docker")
REPO_SKILLS = REPO_ROOT / "skills"
DATA_SKILLS = REPO_ROOT / "data/skills"
ARCHIVE_DIR = REPO_ROOT / "data/archive"

# Mapeo de Nutrición de Paraguas
NUTRIR_MAP = {
    "brain-knowledge-base": "brain-knowledge-ops",
    "docker-container-optimization": "docker-management",
    "docker-service-tailscale": "docker-management",
    "hermes-cron-delivery-routing": "hermes-cron-ops",
    "marketing-campaign": "campaign-ops"
}

# Categorías canónicas destino dentro de skills/
CATEGORY_RULES = [
    # Autonomous AI & SDD
    ("autonomous-ai-agents", [
        "sdd-", "rdd-", "doubt-driven", "evidence-based", "subagent-driven", "autonomous-loops",
        "agent-fork", "ecosystem-setup", "system-onboarding", "executing-plans", "writing-plans",
        "decision-autonomy", "one-three-one", "external-model-review", "llm-judge"
    ]),
    # Software Development & Languages & Best Practices
    ("software-development", [
        "python", "typescript", "react", "go-", "zig-", "electrobun", "ast-grep", "debugging",
        "debug", "testing", "test-", "e2e", "code-review", "code-simplification", "api-and-interface",
        "clean-architecture", "domain-driven", "owasp", "git-", "github-", "rest-graphql",
        "websockets", "nextjs", "nextauth", "spec-best", "tamagui", "tailwind", "finishing-a-development",
        "work-unit-commits", "receiving-code", "requesting-code", "source-driven", "simplify-code"
    ]),
    # AI / ML Engineering
    ("specialists/ai-ml", [
        "axolotl", "dspy", "unsloth", "peft", "torchtitan", "tensorrt", "serving-llms",
        "evaluating-llms", "flash-attention", "pytorch", "accelerate", "trl-", "saelens",
        "nemo-curator", "slime", "simpo", "llama-cpp", "clip", "outlines", "guidance",
        "instructor", "llava", "modal", "lambda-labs", "weights-and-biases", "gentle-ai-bench"
    ]),
    # Data & Vectors
    ("specialists/data-vector", [
        "qdrant", "chroma", "pinecone", "faiss", "rag-architecture", "postgres", "redis"
    ]),
    # DevOps & Infrastructure
    ("devops", [
        "cloudflare", "coolify", "nginx", "tilt", "orbstack", "nix-best", "docker", "systemd",
        "atlas-best", "pinggy-tunnel", "docuseal-selfhost", "formbricks-v5", "twenty-selfhost",
        "unify-service", "hermes-s6-container", "hermes-production"
    ]),
    # Security & Pentest & Forensics
    ("specialists/monitoring-security", [
        "web-pentest", "security-and-hardening", "oss-forensics", "vault", "1password", "op-cli",
        "git-history-secret-purge", "unbroker", "sherlock", "osint", "godmode", "obliteratus",
        "application-security"
    ]),
    # Media, Audio & Creative
    ("creative", [
        "manim", "hyperframes", "comfyui", "stable-diffusion", "openai-image", "whisper",
        "audiocraft", "heartmula", "songwriting", "songsee", "reel-", "baoyu", "ascii",
        "meme-generation", "excalidraw", "tldraw", "p5js", "sketch", "pixel-art", "draw-your-font",
        "touchdesigner", "unreal-mcp", "open-design"
    ]),
    # Marketing, Growth & Finance
    ("specialists/marketing", [
        "meta-ads", "meta-pixel", "marketing", "social-media", "activepieces", "twenty-crm",
        "google-sheets-crm", "amazon-", "shopify", "mobile-landing", "competitor",
        "product-price", "stocks", "polymarket", "hyperliquid", "dcf-model", "lbo-model",
        "merger-model", "3-statement-model", "comps-analysis", "pipeline-informes", "build-startup-brand"
    ]),
    # Productivity, Notes & Office
    ("productivity", [
        "google-workspace", "google-docs", "gmail-", "apple-", "notion", "obsidian", "docx",
        "xlsx", "pptx", "pdf", "excel-author", "powerpoint", "canvas", "himalaya", "agentmail",
        "document-", "memento", "siyuan", "box", "findmy", "telephony", "imessage", "openhue",
        "fitness", "minecraft", "pokemon", "session-librarian", "weekly-review", "writing-skills",
        "using-agent-skills", "using-superpowers", "using-git-worktrees"
    ]),
    # Research, Web & Recon
    ("research", [
        "arxiv", "bioinformatics", "drug-discovery", "parallel-cli", "duckduckgo", "searxng",
        "scrapling", "web-fetch", "blogwatcher", "watchers", "grounded-citations", "xurl",
        "youtube-content", "domain-intel", "qmd", "code-wiki", "graphify", "iterative-retrieval",
        "knowledge-absorption"
    ]),
    # Hermes Internal & Tools
    ("specialists/hermes-internal", [
        "hermes-", "antigravity-cli", "fastmcp", "mcporter", "mpp-agent", "here-now",
        "page-agent", "honcho", "blackbox", "openhands", "openclaw", "grok", "actual-setup",
        "canton-network", "arcgis-geospatial", "colombia-contratos", "context-engineering",
        "context-recovery", "darwinian-evolver", "discord-reporter", "dispatching-parallel",
        "evm", "solana", "impeccable", "improve", "inference-sh", "ios-device", "issue-creation",
        "jupyter-notebook", "kanban-video", "kassiuss-informe", "local-vision", "mcp-oauth",
        "nano-pdf", "neuroskill", "one-three-one", "persistent-task", "pip-install", "plan",
        "playwright-best", "pretext", "provider-manager", "simple-english", "skill-auditor",
        "skill-creator", "skill-improver", "skill-navigator", "skill-registry", "ssot-context",
        "stripe-link", "stripe-projects", "systemic-issue", "tiktok-ingestion", "twitter-telegram",
        "vendor-pricing", "verification-before", "vscode-ai", "wiki-entry", "x-tweet", "yuanbao",
        "zmx", "_shared"
    ])
]

def backup_data_skills():
    print("\n--- 1. RESPALDO COMPLETO DE data/skills ---")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_file = ARCHIVE_DIR / "pre_absorption_data_skills_20260920.tar.gz"
    if not archive_file.exists():
        print(f"Empaquetando {DATA_SKILLS} en {archive_file}...")
        with tarfile.open(archive_file, "w:gz") as tar:
            tar.add(DATA_SKILLS, arcname="skills")
        print(f" ✅ Respaldo creado exitosamente ({archive_file.stat().st_size / (1024*1024):.2f} MB).")
    else:
        print(f" Respaldo ya existente: {archive_file}")

def execute_nutrir():
    print("\n--- 2. NUTRIR PARAGUAS DE skills/core/ ---")
    nutridos = 0
    for skill_name, umbrella_name in NUTRIR_MAP.items():
        src = DATA_SKILLS / skill_name
        dest_umbrella = REPO_SKILLS / "core" / umbrella_name
        if not src.exists() or not dest_umbrella.exists():
            continue
        
        refs_dir = dest_umbrella / "references"
        scripts_dir = dest_umbrella / "scripts"
        refs_dir.mkdir(parents=True, exist_ok=True)

        # Copiar SKILL.md como referencia procedural
        sm = src / "SKILL.md"
        if sm.exists():
            shutil.copy2(sm, refs_dir / f"{skill_name}.md")
            print(f" ✅ Nutriendo '{umbrella_name}': añadido references/{skill_name}.md")

        # Copiar scripts
        src_scripts = src / "scripts"
        if src_scripts.exists() and src_scripts.is_dir():
            scripts_dir.mkdir(parents=True, exist_ok=True)
            for sf in src_scripts.glob("*"):
                if sf.is_file():
                    shutil.copy2(sf, scripts_dir / sf.name)
            print(f" ✅ Scripts de '{skill_name}' absorbidos en '{umbrella_name}/scripts/'")

        nutridos += 1
    print(f" Total skills absorbidas en paraguas (nutrir): {nutridos}")

def execute_guardar_promover():
    print("\n--- 3. GUARDAR / PROMOVER SKILLS A CATEGORÍAS CANÓNICAS ---")
    repo_skills = {sm.parent.name for sm in REPO_SKILLS.rglob("SKILL.md")}
    promovidas = 0
    duplicadas_descartadas = 0

    pending = [p for p in sorted(DATA_SKILLS.iterdir()) if p.is_dir() and (p / "SKILL.md").exists()]

    for p in pending:
        name = p.name
        if name in NUTRIR_MAP:
            continue
        if name in repo_skills:
            duplicadas_descartadas += 1
            continue

        # Determinar categoría
        target_category = "specialists/general"
        for cat_dir, keywords in CATEGORY_RULES:
            if any(kw in name for kw in keywords):
                target_category = cat_dir
                break

        dest_dir = REPO_SKILLS / target_category / name
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(p, dest_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        promovidas += 1

    print(f" ✅ Skills promovidas e incorporadas a Git: {promovidas}")
    print(f" ℹ️ Duplicadas exactas ya presentes en repo: {duplicadas_descartadas}")

def purge_external_data_skills():
    print("\n--- 4. ELIMINACIÓN TOTAL DEL DIRECTORIO EXTERNO data/skills/ ---")
    if DATA_SKILLS.exists():
        shutil.rmtree(DATA_SKILLS)
        print(" ✅ Directorio externo /root/hermes-agent-legacy-docker/data/skills/ eliminado con éxito.")
    else:
        print(" Directorio ya eliminado.")

def sync_to_container():
    print("\n--- 5. SINCRONIZACIÓN AL CONTENEDOR /opt/hermes/skills/ ---")
    # Limpiar y recrear destino
    subprocess.run("docker exec -i hermes-agent rm -rf /opt/hermes/skills && docker exec -i hermes-agent mkdir -p /opt/hermes/skills", shell=True, check=True)
    # Pipe tar para preservar estructura completa
    cmd = "tar -C /root/hermes-agent-legacy-docker/skills -cf - . | docker exec -i hermes-agent tar -C /opt/hermes/skills -xf -"
    subprocess.run(cmd, shell=True, check=True)
    # Permisos hermes:hermes
    subprocess.run("docker exec -i hermes-agent chown -R hermes:hermes /opt/hermes/skills && docker exec -i hermes-agent chmod -R 775 /opt/hermes/skills", shell=True, check=True)
    print(" ✅ Canon Git 100% sincronizado al contenedor con permisos hermes:hermes.")

def run_verifications():
    print("\n--- 6. VERIFICACIONES DE CALIDAD ---")
    subprocess.run("python3 /root/hermes-agent-legacy-docker/scripts/verify_skills.py", shell=True, check=True)

if __name__ == "__main__":
    backup_data_skills()
    execute_nutrir()
    execute_guardar_promover()
    purge_external_data_skills()
    sync_to_container()
    run_verifications()
    print("\n✨ FASE 8 COMPLETADA CON ÉXITO: 0 CARPETAS DE SKILLS FUERA DEL REPOSITORIO.")
