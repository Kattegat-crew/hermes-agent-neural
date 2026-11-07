---
name: hermes-gateway-p0-playbook
description: "Use when the Hermes gateway flaps or a guard misfires."
tags: [hermes, gateway, systemd, hooks, guard, fail_closed, vigia, p0]
version: 1.0.1
license: MIT
author: Ragnar
triggers:
  - "espejo"
  - "gateway flapea: reinicio en bucle / sale con status 1 cada pocos segundos / systemd reintenta sin parar"
  - "replace: Refusing --replace / cannot be proven to belong / gateway.pid stale"
  - "hooks: guard fail_closed / selfcheck de hooks / un guard bloquea de más"
  - "alertas: muro de mensajes de Vigía / avisos duplicados de systemd"
  - "estado falso: plataforma fatal o disconnected que no cambia"
---

# Playbook P0 del gateway y de los guards

## When to Use

- La unidad del gateway se reinicia en bucle o sale con status 1 cada pocos segundos.
- El log muestra `Refusing --replace` / `cannot be proven to belong` / `gateway.pid` stale.
- El selfcheck de hooks reporta que un guard dejó de bloquear, o un guard bloquea comandos legítimos.
- Vigía empieza a repetir avisos idénticos de systemd sin freno.
- Un informe dice que una plataforma está `fatal` o `disconnected` pero no cambia nunca.
- Palabra clave de prueba de routing: `espejo`.

Cuatro fallos distintos se disfrazan de "el gateway está roto". Este es el orden de
diagnóstico y la lección de cada uno, verificada el 04-nov-2026.

## 1. Bucle de reinicios con `--replace`

**Síntoma:** la unidad sale con status 1 cada ~23 s. El journal solo muestra el banner
"Hermes Gateway Starting...", que no dice nada. Vigía empieza a inundar el hilo.

**Dónde mirar de verdad:**

```python
import json
for linea in open('/opt/hermes-agent-data/logs/gateway-exit-diag.log'):
    d = json.loads(linea)
    if d.get('tag') in ('gateway.start', 'asyncio.run.returned'):
        print(d)
```

Contar arranques y salidas fallidas en la ventana. Si `argv` es `gateway run --replace`
en todos, el problema es el registro PID, no el gateway.

**Causa:** un cliente (el dashboard) lanza un gateway detached con `--idle-exit` cuando no
encuentra uno. Si muere sin ruta de salida, deja `gateway.pid` con un PID ajeno; cada
arranque `--replace` se niega a señalarlo ("cannot be proven to belong") y systemd reintenta.

**Arreglo sin tocar el core:** un `ExecStartPre` que sanee el registro y **siempre** salga 0
—PID muerto se borra con copia de seguridad, PID del mismo unit se espera, PID de otro unit
se respeta—. Un `ExecStartPre` que devuelva error dispara el mismo bucle que intenta evitar.

## 2. Guard fail_closed que deja de bloquear o bloquea de más

- El bridge acepta dos dialectos: `{"action":"block"}` (Hermes) y `{"decision":"block"}`
  (Claude-Code). Emitir los dos evita discusiones con el selfcheck.
- Un guard por substring grita en falso y acaba desactivado. Tres filtros mínimos:
  1. partir el comando por segmentos (`;`, `&&`, `||`, `|`, salto de línea) — un patrón de
     escritura solo cuenta en su segmento;
  2. tratar `sed` como escritura solo con la bandera de edición en sitio;
  3. exigir que el comando mencione la ruta protegida, o un `cd` a un home de Hermes.
- Los patrones de escritura desde Python (`open` con modo escritura, `write_text`,
  `yaml.dump`) deben evaluarse **solo** en ejecución de código: en un comando de shell,
  cualquier `json.dumps` parece una escritura.
- Antes de activar un cambio: matriz de casos, el selfcheck de hooks y el test de
  integración del bridge. Nunca editar el guard vivo sin probar una copia aparte.

## 3. Muro de mensajes de Vigía

La notificación de systemd corre en **cada** parada: en un bucle de 23 s son ~40 mensajes.
Hace falta una ventana de silencio por `(unidad, evento)` con contador de suprimidos que se
resuma en el siguiente aviso; dejar siempre exentos el fallo definitivo, el arranque y la
recuperación.

## 4. `gateway_state.json` con estados congelados

El JSON acumula entradas de procesos anteriores. Un `whatsapp: fatal` o un
`api_server: disconnected` cuyo `writer_pid` no existe en `/proc` es basura, no una avería.
Comprobar antes si la plataforma está deshabilitada en la config y en el `.env` del perfil,
y filtrar por escritor vivo antes de reportar.

## Regla transversal

Un informe que dice "0 crons afectados" merece la misma desconfianza que un guard que dice
"todo en orden": cruzar siempre con la base de ejecuciones y con el estado real de los
procesos antes de dar un cierre por bueno.
