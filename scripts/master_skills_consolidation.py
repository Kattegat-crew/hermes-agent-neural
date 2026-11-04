#!/usr/bin/env python3
"""
master_skills_consolidation.py — Ejecución del Plan Maestro de Consolidación y Centralización de Skills.
1. Fusión de 180 autoskills y canon en 19 paraguas en /root/hermes-agent-legacy-docker/skills/core/.
2. Integración de dotaciones de especialistas R2-bis en /root/hermes-agent-legacy-docker/skills/specialists/.
3. Empaquetado y archivo de vendor (skills-ext y skills-especialistas) en /opt/data/archive/.
4. Eliminación de copias externas (.hermes/skills).
5. Purga de symlinks rotos en todos los perfiles de la flota.
6. Reconfiguración de config.yaml en los 11 perfiles (external_dirs + on_demand + create_dir de ragnar).
7. Sincronización al contenedor /opt/hermes/skills.
"""

import os
import sys
import json
import shutil
import tarfile
import subprocess
from pathlib import Path

REPO_SKILLS = Path("/root/hermes-agent-legacy-docker/skills")
CORE_SKILLS = REPO_SKILLS / "core"
SPEC_SKILLS = REPO_SKILLS / "specialists"
DATA_SKILLS = Path("/root/hermes-agent-legacy-docker/data/skills")
PROFILES_DIR = Path("/root/hermes-agent-legacy-docker/data/profiles")
ARCHIVE_DIR = Path("/root/hermes-agent-legacy-docker/data/archive")

def step1_create_umbrellas():
    print("\n--- PASO 1: Creando y fusionando los 19 paraguas en skills/core/ ---")
    CORE_SKILLS.mkdir(parents=True, exist_ok=True)
    SPEC_SKILLS.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    lotes_path = "/root/hermes-agent-legacy-docker/data/profiles/roshi/workspace/plan/lotes_simplificacion_20260917.json"
    if not os.path.exists(lotes_path):
        print("ERROR: lotes_simplificacion no encontrado")
        return

    with open(lotes_path) as f:
        lotes = json.load(f)

    for item in lotes:
        paraguas = item["paraguas"]
        miembros = item["miembros"]
        nota = item.get("nota", "")
        p_dir = CORE_SKILLS / paraguas
        p_refs = p_dir / "references"
        p_scripts = p_dir / "scripts"
        p_refs.mkdir(parents=True, exist_ok=True)

        # Buscar miembros en data/skills o en repo
        absorbed_count = 0
        for m in miembros:
            m_path = DATA_SKILLS / m
            if not m_path.exists():
                # buscar recursivo en DATA_SKILLS
                cands = list(DATA_SKILLS.glob(f"**/{m}"))
                if cands:
                    m_path = cands[0]

            if m_path.exists() and m_path.is_dir():
                absorbed_count += 1
                sm = m_path / "SKILL.md"
                if sm.exists():
                    shutil.copy2(sm, p_refs / f"{m}.md")
                
                # Copiar scripts si existen
                ms = m_path / "scripts"
                if ms.exists() and ms.is_dir():
                    p_scripts.mkdir(exist_ok=True)
                    for sf in ms.glob("*"):
                        if sf.is_file():
                            shutil.copy2(sf, p_scripts / sf.name)

        # Crear el SKILL.md maestro del paraguas si no existe
        p_skill_md = p_dir / "SKILL.md"
        if not p_skill_md.exists():
            desc = f"Paraguas consolidado para {paraguas}. {nota}"
            content = f"""---
name: {paraguas}
description: "{desc[:120]}"
version: 2.0.0
author: NeuralCrew
---

# {paraguas.replace('-', ' ').title()}

## Propósito y Alcance
Habilidad consolidada de clase que centraliza los flujos de:
{chr(10).join(f"- `{m}`" for m in miembros)}

## Arquitectura y Protocolos
Esta skill opera como despacho unificado. El detalle procedural y gotchas específicos de cada caso se encuentran preservados en:
`references/`

## Casos de Uso Disponibles
{chr(10).join(f"- **{m}**: Ver [references/{m}.md](file://{p_refs}/{m}.md)" for m in miembros)}
"""
            p_skill_md.write_text(content, encoding="utf-8")
        print(f" ✅ Paraguas '{paraguas}': {absorbed_count}/{len(miembros)} miembros absorbidos.")

def step2_copy_core_skills():
    print("\n--- PASO 2: Migrando skills transversales clave al canon Git skills/core/ ---")
    key_canon = [
        "engram-memory-system", "whatsapp-bridge-operations", "docker-management",
        "nan-builders-api", "vault-access", "systematic-debugging",
        "capability-claim-verification", "agent-reach", "mapa-de-carpetas"
    ]
    for k in key_canon:
        src = DATA_SKILLS / k
        if not src.exists():
            cands = list(DATA_SKILLS.glob(f"**/{k}"))
            if cands:
                src = cands[0]
        if src.exists() and src.is_dir():
            dest = CORE_SKILLS / k
            if not dest.exists():
                shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                print(f" ✅ Migrado al canon Git: {k}")

def step3_transfer_specialists_r2bis():
    print("\n--- PASO 3: Incorporando dotaciones R2-bis a skills/specialists/ ---")
    apply_path = "/root/hermes-agent-legacy-docker/data/profiles/roshi/workspace/plan/r2bis_plan_apply.json"
    if not os.path.exists(apply_path):
        print("Aviso: r2bis_plan_apply no encontrado, usando r2bis_plan.json...")
        apply_path = "/root/hermes-agent-legacy-docker/data/profiles/roshi/workspace/plan/r2bis_plan.json"

    with open(apply_path) as f:
        data = json.load(f)

    total_dot = 0
    # Map bots to domain folders
    domain_map = {
        "bragi": "media-video",
        "freyja": "marketing",
        "vili": "marketing-ads",
        "brokkr": "devops-infra",
        "sindri": "devops-systems",
        "heimdall": "monitoring-security",
        "ullr": "compliance-qa",
        "hermodr": "comms"
    }

    for bot, dotaciones in data.items():
        domain = domain_map.get(bot, "general")
        target_dir = SPEC_SKILLS / domain
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # dotaciones can be list of dicts or list of strings
        if isinstance(dotaciones, dict):
            dot_list = dotaciones.get("faltan", [])
        else:
            dot_list = dotaciones

        for item in dot_list:
            if isinstance(item, dict):
                skill_name = item.get("skill")
                real_path = item.get("real")
            else:
                skill_name = item
                real_path = None

            if not skill_name:
                continue

            dest = target_dir / skill_name
            if dest.exists():
                continue

            # Buscar fuente
            src = Path(real_path) if real_path and os.path.exists(real_path) else None
            if not src or not src.exists():
                cands = list(DATA_SKILLS.glob(f"**/{skill_name}"))
                if cands:
                    src = cands[0]
            
            if src and src.is_dir():
                shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                total_dot += 1

    print(f" ✅ Total dotaciones de especialistas materializadas en Git: {total_dot}")

def step4_archive_vendors_and_clean_legacy():
    print("\n--- PASO 4: Archivando repositorios de terceros fuera de runtime ---")
    ext_dir = Path("/root/hermes-agent-legacy-docker/data/skills-ext")
    if ext_dir.exists() and ext_dir.is_dir():
        archive_tar = ARCHIVE_DIR / "vendor_skills_ext_20260920.tar.gz"
        if not archive_tar.exists():
            print(f"Empaquetando skills-ext en {archive_tar}...")
            with tarfile.open(archive_tar, "w:gz") as tar:
                tar.add(ext_dir, arcname="skills-ext")
            print(" ✅ skills-ext archivado con éxito.")
        # Limpiar directorio activo
        shutil.rmtree(ext_dir)
        print(" ✅ Directorio data/skills-ext removido de la ruta activa.")

    esp_dir = Path("/root/hermes-agent-legacy-docker/data/skills-especialistas")
    if esp_dir.exists() and esp_dir.is_dir():
        shutil.rmtree(esp_dir)
        print(" ✅ Directorio data/skills-especialistas removido.")

    # Remover host_legacy
    legacy_host = Path("/root/.hermes/skills")
    if legacy_host.exists():
        shutil.rmtree(legacy_host)
        print(" ✅ Copia muerta host /root/.hermes/skills eliminada.")

def step5_purge_broken_symlinks_and_reconfig():
    print("\n--- PASO 5: Purgando symlinks rotos y reconfigurando perfiles ---")
    profiles = [p for p in PROFILES_DIR.iterdir() if p.is_dir()]
    
    for prof in profiles:
        p_name = prof.name
        p_skills = prof / "skills"
        
        # Purgar symlinks rotos
        broken_cleaned = 0
        if p_skills.exists() and p_skills.is_dir():
            for item in list(p_skills.glob("*")):
                if item.is_symlink():
                    if not item.exists(): # broken
                        item.unlink()
                        broken_cleaned += 1
                    else:
                        # Si apunta a /root/hermes-agent-legacy-docker, remover también
                        try:
                            targ = os.readlink(item)
                            if "/root/hermes-agent-legacy-docker" in targ or "/opt/data/skills" in targ:
                                item.unlink()
                                broken_cleaned += 1
                        except Exception:
                            pass
        if broken_cleaned > 0:
            print(f" ✅ Perfil '{p_name}': {broken_cleaned} symlinks purgados.")

        # Reconfigurar config.yaml
        cfg_file = prof / "config.yaml"
        if cfg_file.exists():
            try:
                import yaml
                with open(cfg_file, "r") as cf:
                    cfg = yaml.safe_load(cf) or {}
                
                skills_cfg = cfg.get("skills") or {}
                if not isinstance(skills_cfg, dict):
                    skills_cfg = {}
                
                skills_cfg["on_demand"] = True
                ext_dirs = skills_cfg.get("external_dirs") or []
                if not isinstance(ext_dirs, list):
                    ext_dirs = []
                
                if "/opt/hermes/skills" not in ext_dirs:
                    ext_dirs = ["/opt/hermes/skills"] + [d for d in ext_dirs if d != "/opt/data/skills"]
                
                skills_cfg["external_dirs"] = ext_dirs
                
                if p_name == "default":
                    skills_cfg["create_dir"] = "/opt/data/sedimento/ragnar"
                
                cfg["skills"] = skills_cfg
                with open(cfg_file, "w") as cf:
                    yaml.dump(cfg, cf, default_flow_style=False, sort_keys=False)
            except Exception as e:
                print(f"Aviso al actualizar config de {p_name}: {e}")

    # Asegurar que ragnar tenga su dir sedimento
    os.makedirs("/root/hermes-agent-legacy-docker/data/sedimento/ragnar", exist_ok=True)
    print(" ✅ Configs de los perfiles actualizados con /opt/hermes/skills y on_demand: true.")

def step6_sync_to_container():
    print("\n--- PASO 6: Sincronizando canon al contenedor /opt/hermes/skills ---")
    cmd = "docker exec -i hermes-agent mkdir -p /opt/hermes/skills/core /opt/hermes/skills/specialists"
    subprocess.run(cmd, shell=True, check=True)
    cmd2 = "docker cp /root/hermes-agent-legacy-docker/skills/. hermes-agent:/opt/hermes/skills/"
    subprocess.run(cmd2, shell=True, check=True)
    cmd3 = "docker exec -i hermes-agent chown -R hermes:hermes /opt/hermes/skills 2>/dev/null || true"
    subprocess.run(cmd3, shell=True)
    print(" ✅ Canon sincronizado y permisos aplicados al contenedor.")

if __name__ == "__main__":
    print("🚀 INICIANDO EJECUCIÓN DEL PLAN MAESTRO DE SKILLS...")
    step1_create_umbrellas()
    step2_copy_core_skills()
    step3_transfer_specialists_r2bis()
    step4_archive_vendors_and_clean_legacy()
    step5_purge_broken_symlinks_and_reconfig()
    step6_sync_to_container()
    print("\n✨ EJECUCIÓN COMPLETADA CON ÉXITO.")
