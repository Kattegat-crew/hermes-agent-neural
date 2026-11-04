---
name: agent-fleet-botmaker-learnings
description: "Use when building or auditing specialist Hermes bots."
tags: [hermes, bots, profiles, soul, skills, fleet, config, flota]
version: 1.0.0
author: Ragnar (NeuralCrew Labs)
license: MIT
metadata:
  hermes:
    tags: [hermes, bots, profiles, soul, independence-pin, skills, fleet]
    category: autonomous-ai-agents
    related_skills: [hermes-agent, hermes-skills-provisioning, client-agent-soul-survey]
---

# Agent Fleet: botmaker learnings

Conocimiento destilado de la evaluación de `techjanitor/botmaker` (2026-09-06).
Filosofía >= código. El repo es juvenil (3 commits); lo valioso son 3 reglas.

## 1. Independence-pin (regla de flota)

> Un bot que **opera** un servicio no debe correr en la ruta de inferencia de ese
> servicio. Si el servicio local (GPU / inference / ComfyUI / un worker) se cae,
> el bot operador debe seguir pensando.

- Aplica a: especialistas que hablan *a* una API/servicio (ComfyUI, inference local, reel-worker).
- Pinear el bot a un proveedor hosted: `hermes -p NAME config set model.provider <hosted>` + `model.default <model>`.
- **Pitfall "create leftover":** `hermes profile create` copia el bloque de modelo del perfil
  default (a veces un `base_url` local). Tras crear: `hermes -p NAME config unset model.base_url`
  y `config unset model.api_key`. Verificar: `hermes -p NAME config get model` debe imprimir
  SOLO `default` + `provider` (sin `base_url`).
- NUNCA `config set` vía edición manual de `config.yaml`; `config set` es la vía.
- Pins actuales (verificados 2026-09-06): todos los perfiles (default, roshi, vigia, 8 dioses,
  comms) -> NaN-Builders. Sin `base_url` local heredado en ninguno.

## 2. One-screen SOUL (guía de `soul-craft.md`)

Un SOUL de especialista bueno es **una pantalla**. Si no cabe, el procedimiento va en un skill.

Secciones REQUERIDAS:
1. **Identity** — el nombre del trabajo primero (`You are Botmaker`), y el modelo/perfil,
   dicho llano si preguntan. No la web del vendor. No "you are a helpful assistant".
2. **Job** — primer párrafo: "You are the X." + "load skill Y on every in-scope question".
   Un solo trabajo.
3. **Hard constraints** — **ganadas**, no decorativas. Si no puedes nombrar una constraint
   que de verdad dolería, aún no la tienes; no inventes una.
4. **Voice** — elegida a propósito, no un paste del modelo stock. Herencia es tono, no identidad.
   No copiar el bloque #Style de otro bot.
5. **What you are not** — la mitad útil del prompt; corta trabajo fuera de misión.
6. **Disagreement** — corregir al humano sin victory lap; una pregunta cuando el trabajo es
   difuso; "no sé" > adivinar confiado.

NO meter en el SOUL: pins/IPs/último incidente (van a MEMORY.md o skill), protocolo
bot-a-bot (ya lo inyecta Hermes), la runbook (va en SKILL.md), biografía del humano.

## 3. Skill discovery: os.walk vs rglob (HALLAZGO)

> **El bug de botmaker NO aplica a nuestro runtime.**

- botmaker afirma que Hermes `Path.rglob("SKILL.md")` no desciende symlinks de directorio
  (Py3.11). Cierto en su entorno.
- **Hermes v0.21 / Python 3.13** descubre skills con `os.walk(skills_dir, followlinks=True)`
  (`agent/prompt_builder.py` ~L1648, `agent/skill_utils.py` ~L1304) — SÍ sigue symlinks de dir.
- Verificado en vivo 2026-09-06 en `profiles/bragi/skills` (145 symlinks de dir):
  `rglob` encontró 8 SKILL.md; `os.walk(followlinks=True)` encontró 153.
- **Conclusión de diseño:** NO convertir symlinks de dir existentes a file-level symlinks
  solo por esta heurística. Antes de refactorizar materialización de skills, verificar qué
  usa el runtime actual (`grep -rn "os.walk\|followlinks\|rglob" /opt/hermes/agent/`).
- `link_skill_tree.py` (file-level symlinks) solo interesa en runtimes Py3.11 o donde el
  descubrimiento use `rglob` directo.

## 4. Doc one-home + drift tripwire (opcional)

- Regla: cada regla tiene UN solo owner (método en skill tree, estado de flota en el vault,
  historial en changelog). Útil como disciplina anti-drift; ya la cubrimos con la escalera
  de errores y la suite de regresión del pipeline (ver `agent-configuration-drift`).

## 5. Certificar capacidades: platform_toolsets (verificado 09/09)

Los especialistas nacen SIN `platform_toolsets` en su config.yaml → caen al toolset
default mínimo (sin terminal/code_execution/delegation/image_gen/navegación). Por eso
"no tienen las capacidades del default".

**Fix (verificado en Bragi, piloto F1):** espejar el `platform_toolsets` del default en la
config del especialista.

```python
import yaml, shutil, time
cfgpath = f"/opt/data/profiles/{slug}/config.yaml"
src = open(cfgpath).read()
shutil.copy2(cfgpath, cfgpath + f".bak-ragnar-f1-{int(time.time())}")
pt = yaml.safe_load(open("/opt/data/config.yaml"))["platform_toolsets"]
block = yaml.dump({"platform_toolsets": pt}, sort_keys=False, allow_unicode=True)
lines = src.splitlines(keepends=True)
idx = next(i+1 for i,l in enumerate(lines) if l.startswith("_config_version"))
open(cfgpath, "w").write("".join(lines[:idx]) + block + "".join(lines[idx:]))
yaml.safe_load(open(cfgpath))  # validar YAML
```

Verificar: `hermes -p <slug> config get platform_toolsets.cli` (debe listar terminal,
code_execution, etc.) y `hermes -p <slug> doctor`.
**No requiere reinicio** si el gateway del especialista está abajo (config aplica al
despertar). Regla anti-slop: mencionar `model.default`/`agent.name` intactos tras editar.

## 6. One-screen SOUL aplicado (verificado 09/09, Bragi F2)

Reescribir SOUL.md con las 6 secciones del craft: **Job** (una frase + "cargo la skill
que toca"), **Qué NO soy** (la mitad útil), **Voz** elegida, **Constraints duras ganadas**
(las que dolerían), **Disenso** (sin victory lap, "no sé" > adivinar), **Tarjeta**.
Backup antes (`SOUL.md.bak-ragnar-f2-*`). Módulo y compliance al inicio.

## Referencia

- Repo congelado: `/opt/data/repos/botmaker/` (commit `93eb3b6`).
- Runbook fuente: `skills/autonomous-ai-agents/botmaker/{SKILL.md,references/*.md}` y
  `scripts/{link_skill_tree.py,drift_check.py}`.
