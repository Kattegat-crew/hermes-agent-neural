---
name: hermes-runtime-self-report
description: "Use when asked which model or provider an agent runs on."
version: 1.0.0
author: curator-ragnar
category: devops
metadata:
  hermes:
    tags: [hermes, modelo, proveedor, config, fallback, flota]
    related_skills: [capability-claim-verification, hermes-profile-inventory, provider-manager]
---

# «¿Qué modelos eres?» — responder sobre mi propio runtime

**Cuándo:** «¿qué modelos eres?», «¿con qué modelo corres?», «¿qué modelo usa Roshi?», «¿tenemos fallback entre proveedores?». Es una pregunta de identidad/configuración: se contesta con la **config viva**, no con el encabezado de la sesión ni de memoria.

## 1. El encabezado de sesión NO es la config (caso 12-sep-2026)

El bloque de contexto de cada sesión trae etiquetas **derivadas**. Caso real: el header decía `Model: deepseek-v4-flash · Provider: custom`, mientras `/opt/data/config.yaml` declara `provider: NaN-Builders` con `base_url: https://api.nan.builders/v1`. Repetir el header como si fuera la config es dar un dato falso con seguridad.

Rutas y lectura (el perfil por defecto NO usa `profiles/<slug>/`):

```bash
# perfil default
sed -n '1,60p' /opt/data/config.yaml
grep -n -E "^fallback_providers|^model:|^  default:|^  provider:|^  base_url:|^  max_tokens:" /opt/data/config.yaml
# otro perfil
sed -n '1,60p' /opt/data/profiles/<slug>/config.yaml
```

Cita siempre `archivo:linea` en la respuesta: es lo que la hace auditable.

## 2. Separa tres cosas: agente / modelo / cascada

- **Agente:** Hermes Agent + perfil (p. ej. Ragnar, perfil `default`). El modelo es la capa de abajo, no la identidad.
- **Modelo activo:** `model.default` + `model.provider`, más su ventana real y capacidades desde el catálogo `providers.<P>.models.<m>` (`context_length`, `supports_vision`, `name`).
- **Cascada real:** `fallback_providers: []` = **SIN fallback automático**, aunque `providers:` liste varios (B.AI, OpenCode-Go…) y esos otros proveedores apunten al mismo endpoint. No anuncies redundancia por ver proveedores declarados; solo cuentan los que están en la cascada.
- **Auxiliares** (modelo de revisión de fondo, modelo de tareas rápidas, compresión): si quien pregunta administra la flota, son parte de la respuesta honesta — «trabajo con X, y para Y uso Z».

## 3. Forma de la respuesta

- 3-6 líneas. Modelo activo **primero**, con proveedor y endpoint; el resto del catálogo declarado como *apoyo, no identidad*.
- Cierra con la ruta del archivo leído y, si el dato puede haber cambiado (rotación de modelos, cambios de proveedor), dilo: es un snapshot, no una constante.
- Si la pregunta era sobre **otro** perfil/bot, lee el config de ESE perfil; no extrapoles el tuyo.

## ¿En qué servidor estoy? — identidad de host por IP, no por hostname (caso 16-sep-2026)

«¿dónde corres?», «¿qué RAM tiene prod?» exigen identificar el host **con evidencia de red** antes de citar cifras. Caso real: afirmé «estoy DENTRO del PROD (.222), hostname vmi3151337» y medí RAM/disco — FALSO: era DEV (.250); el Admin lo corrigió («FALSOOO tu, ragnar, corres en el servidor .250»). La cifra que reporté como PROD (7.9 GB RAM, swap al 72%) era la de DEV.

Reglas:
- La identidad se decide por **IP pública / Tailscale** (`ip -4 addr show`), nunca por `hostname`: ambos VPS OVH usan nombres `vmiNNNNNN` parecidos (DEV=vmi3151337, PROD=vmi3513784).
- Toda cifra que cites (`free`, `df`, `nproc`, procesos) debe salir del comando ejecutado **dentro de las comillas del ssh** al host en cuestión; un `hostname`/`free` corrido en mi shell local describe DEV, no el objetivo.
- Snapshot verificado de la flota (re-verificar antes de citar en decisiones de capacidad): `references/fleet-host-identity.md`.
- Si el Admin corrige la identidad de host: aceptar de inmediato y re-medir AMBOS hosts por IP directa en un solo turno. En el runtime desktop los alias `ssh dev`/`ssh prod` no resuelven (DNS interno) — conectar por IP.

## ¿Qué hardware tiene cada host? — medición como insumo de decisión (caso 16-sep-2026)

«¿qué RAM tiene PROD?», «¿dónde instalamos X?» exigen cifras **frescas y comparativas**: medir AMBOS hosts por IP en el mismo turno (mismo comando, dentro del ssh de cada uno), etiquetar cada cifra con fecha/hora, y razonar por holgura relativa («PROD: 3.6x la RAM libre de DEV, 7x el disco, 2x cores») — no por valores absolutos aislados. Reglas:

- El comando canónico (`hostname; ip -4 addr show | grep inet; free -m; df -h /; nproc`) corre en los DOS hosts antes de responder cualquier comparación de capacidad.
- Las cifras de un plan/decisión caducan: quien las ejecute después debe re-medir en vivo antes de actuar sobre ellas.
- Si la cifra que vas a citar va a terminar en un documento persistente (plan de brain, informe), la medición es el primer paso OBLIGATORIO del turno — citar un snapshot viejo allí replica el error de abajo.
- La clase «evaluar software self-hosted y decidir dónde desplegarlo» tiene skill propia: `self-hosted-tool-evaluation` (devops).

## Pitfalls

- **Afirmar que hay fallback sin leer `fallback_providers`.** La lista vacía es el caso normal aquí.
- **Copiar la key al chat.** En el YAML suele venir truncada (`sk-JzB...ohYw`): no la completes ni la cites, y no la pegues en informes.
- **Confundir modelo de imagen con proveedor de texto**: el catálogo de un proxy puede servir un solo modelo de imagen distinto del de texto; son cadenas separadas.
- **Inventar la ventana de contexto o la visión**: sale del catálogo del proveedor en la config, no de la reputación del modelo.
- **Contestar de Estado 1 (sin tools)**: la pregunta parece trivial pero exige leer disco; es una lectura barata y legítima.
- **Decidir identidad de host por `hostname` o atribuir salida local a un host remoto.** Ambos VPS tienen hostnames `vmiNNNNNN` casi iguales, y PROD no tiene swap: citar la RAM de DEV como PROD repite el caso del 16-sep-2026. Verifica la IP y ejecuta la medición dentro del ssh.

## Relación con otras skills

`capability-claim-verification` (devops) es el homólogo rico de esta clase (claims de configuración con evidencia read-only) y **hoy es user-owned**: el 12-sep-2026 `skill_manage` la rechazó con *not curator-managed (created_by=None)*. Si quieres que este contenido viva allí, pide `hermes curator adopt capability-claim-verification`; hasta entonces esta skill es el homólogo editable. `provider-manager` cubre el cambio de modelos (script `manage_provider.py`), no la respuesta sobre el estado.
