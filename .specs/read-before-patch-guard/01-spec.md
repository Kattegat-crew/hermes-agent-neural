# Especificación: guard `read-before-patch`

- **Estado**: propuesta (pendiente de OK del Admin para despachar)
- **Autor**: Ragnar
- **Fecha**: 12-nov-2026
- **Origen**: peguelo de la sesión `20261112_113301_5fa3e5e1` — 6 `patch` sobre archivos del
  worktree sin `read_file` previo, con la regla ya escrita en la skill `core/peguelo`.
  4ª aparición de la misma lección ⇒ promoción a guard (regla 1-2-3 del ledger).

## 1. Problema

El agente edita con `patch` archivos cuyo contenido **no ha leído en esta sesión** (o leyó hace
turnos y el archivo ya cambió). El resultado no es un error visible: es un `patch` que aplica
sobre una versión distinta, o que falla y se reintenta a ciegas. `write_file` ya está protegido
por Hermes (se niega a sobrescribir sin lectura previa); **`patch`/`edit_file` no**.

Medido sobre `state.db` (950 sesiones con actividad, solo lectura):

| Métrica | Valor |
|---|---|
| escrituras (`write_file` + `patch` + `edit_file`) | 2.526 |
| `patch` sin lectura ni escritura previa del mismo path en la sesión | **404 (16%)** |
| sesiones afectadas | **83 de 299** con escrituras (28%) |
| de esos 404, casos que solo difieren en la forma de la ruta (relativa vs absoluta) | 45 |

Es decir: entre 16% y 18% de las ediciones se hacen a ciegas, y el guard las habría bloqueado.

## 2. Objetivo

Que un `patch`/`edit_file` sobre un archivo existente solo se ejecute si el agente **vio el
contenido que hay ahora**:

- hubo un `read_file` de esa ruta en la sesión **y** el archivo no cambió desde entonces, o
- el propio agente escribió esa ruta en la sesión **y** el archivo no cambió desde esa escritura.

Comparación por **huella** (`mtime_ns` + `size`), no por memoria del agente. Si la huella no
coincide, se bloquea y el mensaje dice exactamente qué `read_file` ejecutar.

## 3. No objetivos

- No valida que el `old_string` del patch sea correcto (eso lo hace la herramienta).
- No cubre lecturas parciales: `read_file` con `offset/limit` cuenta como lectura de la ruta.
  Se documenta como límite conocido; la v2 podría exigir cobertura del rango.
- No bloquea `terminal`, `execute_code` ni `sed`/`awk` por shell: fuera de alcance por diseño
  (el guard protege la herramienta de edición estructurada, no prohíbe shell).
- No mide ni corrige el comportamiento del modelo: solo impide la edición a ciegas.

## 4. Criterios de aceptación

- CA1 `patch` sobre archivo existente sin lectura previa ⇒ bloqueado, exit 2, mensaje con el
  `read_file` exacto a ejecutar.
- CA2 `patch` tras `read_file` y sin cambios en disco ⇒ permitido.
- CA3 `patch` tras `read_file` pero con el archivo modificado por otro proceso ⇒ bloqueado.
- CA4 `patch` tras `write_file` propio y sin cambios posteriores ⇒ permitido.
- CA5 `patch` sobre ruta inexistente ⇒ permitido (deja que la herramienta reporte su error).
- CA6 rutas relativas se resuelven contra el `cwd` del payload; symlinks por `realpath`.
- CA7 modo `shadow` (default al desplegar): registra lo que habría bloqueado y **no** bloquea.
- CA8 modo `enforce`: bloquea según CA1-CA6.
- CA9 kill switch: si existe `/opt/hermes-agent-data/state/hooks/read-before-patch/DISABLED`
  el hook permite todo y lo registra una vez.
- CA10 ningún error interno del hook puede bloquear la flota: ante excepción, exit 0 y log.
  (Por eso `fail_closed: false` en su entrada de config, a diferencia del Config Shield.)
- CA11 replay sobre `state.db` reproducible: reporta cuántos `patch` habría bloqueado y cuántos
  son falso positivo por forma de ruta.
