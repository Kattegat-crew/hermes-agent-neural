# Feature Specification: MCP idle lifecycle policy

* **Status**: Approved (sign-off del Admin, 2026-11-13)
* **Author**: Roshi (perfil roshi) para Jesús Díaz (CTO)
* **Target Module**: `scripts/` (operaciones), sobre primitivas existentes de `utils.py`
* **Created**: 2026-11-13
* **Updated**: 2026-11-13 (revisión fase 1 → correcciones B1/M1/M2/M3)

---

## 1. Problem Statement & Motivation

* **What is the problem?** El reciclado por inactividad **ya existe** en el núcleo y **ya está en uso**
  en producción (verificado: 72 reciclados `stdio session recycled after idle_timeout_seconds` en
  `logs/gateway.log`). Lo que falta es una **vía soportada, verificable e idempotente** para fijar y
  auditar esa política sobre un perfil completo: hoy hay que editar 31 bloques YAML a mano, sin
  validación y sin forma de comprobar que el valor escrito es el que el núcleo realmente lee.
* **Riesgo concreto que motiva la herramienta:** `idle_timeout_seconds` admite dos ubicaciones
  (top-level y bajo `lifecycle:`) y el núcleo **prioriza la top-level**. Un script ingenuo que
  escriba en `lifecycle:` deja el valor efectivo intacto — el archivo parece cambiado y nada cambia.
  Esa trampa es exactamente la que esta feature debe imposibilitar.
* **Why solve it now?** El operador necesita bajar la ventana de 300 s a 200 s de forma uniforme y
  con evidencia previa (`--dry-run`) y posterior (`--check`), sin tocar el núcleo ni reiniciar.

---

## 2. Goals & Non-Goals

### Goals
- [x] Aplicar una política uniforme de `idle_timeout_seconds` a los servidores MCP **stdio** de un
      `config.yaml` mediante un comando reproducible.
- [x] Escribir siempre en la ubicación que el núcleo lee primero (top-level), sincronizando la copia
      `lifecycle.idle_timeout_seconds` si el servidor ya la declara (evita shadowing incoherente).
- [x] Preservar comentarios, orden y claves existentes (loader y writer round-trip del proyecto).
- [x] Ser idempotente: una segunda ejecución no produce cambios ni reescribe el archivo.
- [x] Permitir simulación (`--dry-run`) y verificación (`--check`) sin escribir.

### Non-Goals (Out of Scope)
- No se modifica el núcleo del agente ni la semántica de reciclado de MCP.
- No se aplica a servidores HTTP (`url`): el núcleo no los recicla por inactividad.
- No se instalan binarios ni se sustituyen envoltorios `npm exec` (fase posterior).
- No se reinicia ningún servicio: el cambio surte efecto en el siguiente arranque del gateway.
- No se tocan servidores no-MCP ni claves ajenas a `mcp_servers.<name>`.

---

## 3. User Stories & Functional Requirements

* **US-1**: Como operador de flota, quiero aplicar `idle_timeout_seconds=200` a todos los MCP stdio
  de un perfil en un solo comando, para que los procesos mueran tras 200 s sin uso.
  * **Requirement 1.1**: El comando debe aceptar `--config <ruta>` y `--idle-seconds <int>` (default 200).
  * **Requirement 1.2**: Debe escribir `idle_timeout_seconds` **en la raíz** de cada entrada de
    `mcp_servers` que tenga `command` (stdio). Los que solo tengan `url` se reportan como omitidos.
  * **Requirement 1.3**: Si el servidor ya declara `lifecycle.idle_timeout_seconds`, esa copia se
    sincroniza al mismo valor para que no quede sombreada.
  * **Requirement 1.4**: `--idle-seconds 0` debe escribirse tal cual (desactiva el reciclado).

* **US-2**: Como revisor, quiero ver el efecto antes de aplicarlo.
  * **Requirement 2.1**: `--dry-run` imprime la tabla `servidor: antes -> después` y no escribe.
  * **Requirement 2.2**: `--check` sale con código 3 si el **valor efectivo** de algún servidor
    difiere del pedido, 0 si todos lo cumplen. Nunca escribe.
  * **Requirement 2.3**: `--dry-run` y `--check` son mutuamente excluyentes (error de uso, exit 2).

---

## 4. Acceptance Criteria & Invariants

* **Scenario 1**: Política aplicada sobre un servidor sin clave previa
  * **Given**: `mcp_servers.a.command` sin `idle_timeout_seconds`
  * **When**: se ejecuta `--idle-seconds 200`
  * **Then**: `mcp_servers.a.idle_timeout_seconds == 200`, sin crear bloque `lifecycle`, resto de
    claves intactas y comentarios preservados.

* **Scenario 2**: Idempotencia
  * **Given**: un archivo ya configurado a 200 s
  * **When**: se ejecuta de nuevo
  * **Then**: cero cambios, mtime sin tocar y contenido byte-idéntico.

* **Scenario 3**: Claves existentes preservadas
  * **Given**: un servidor con `lazy: true`, `lifecycle.max_lifetime_seconds: 3600`, `env` y `args`
  * **When**: se aplica la política
  * **Then**: `lazy`, `max_lifetime_seconds`, `env` y `args` mantienen su valor.

* **Scenario 4**: Config inválido
  * **Given**: un archivo sin bloque `mcp_servers` o un YAML ilegible
  * **When**: se ejecuta el comando
  * **Then**: mensaje en stderr y exit 2, sin escribir el archivo.

* **Scenario 5**: Precedencia (regresión B1)
  * **Given**: `idle_timeout_seconds: 100` top-level (con o sin `lifecycle: 200`)
  * **When**: se pide 200 y luego `--check`
  * **Then**: el top-level queda en 200, la copia `lifecycle` se sincroniza si existía, y `--check`
    sale 0 solo cuando el valor **efectivo** es 200.

* **Scenario 6**: Servidor HTTP
  * **Given**: entrada con solo `url`
  * **When**: se aplica la política
  * **Then**: no se escribe nada en esa entrada y aparece en `skipped_http` del reporte.

---

## 5. Invariantes

- Lectura con `utils._roundtrip_load` y escritura **solo** con `utils.atomic_roundtrip_yaml_save`
  (`scripts/check_config_yaml_writers.py` limpio).
- Nunca se elimina ninguna clave: el documento completo mutado es lo que se persiste.
- La precedencia de lectura replica **exactamente** la del núcleo (`tools/mcp_tool_common.py`):
  top-level primero, `lifecycle.*` como fallback, valores inválidos ignorados.
- Ninguna ejecución toca procesos, servicios ni red.
