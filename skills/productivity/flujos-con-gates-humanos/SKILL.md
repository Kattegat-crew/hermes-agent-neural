---
name: flujos-con-gates-humanos
description: "Use when designing flows with human approval gates"
tags: [gates, aprobaciones, firma-humana, human-in-the-loop, automatizacion, proceso, campanas]
version: 1.0.0
metadata:
  hermes:
    tags: [gates, aprobaciones, automatizacion, campanas, proceso, firma-humana]
    related_skills: [sesion-pieza-por-pieza, guion-reel-mesa-medida, campanas-qa-integridad]
---

# Flujos con gates humanos (construidos para Yisus)

Clase de trabajo: **disenar o construir un proceso asistido** donde el dueño aprueba paso a paso
(guiones de campana, generacion de piezas, pipelines con gasto, cualquier flujo por etapas). Aqui vive
CÓMO debe comportarse el agente y CÓMO debe quedar la automatizacion. El detalle del proceso de guiones
(40 interacciones, vacios y fases) esta en `references/proceso-interactivo-40-pasos.md`.

## Las 6 reglas que el dueño ya corrigio en carne propia (12-sep-2026)

1. **El freno vive en el script, no en la disciplina del agente.** Cita textual: *"no veo que estes
ejecutando un script del repo"*. Si la unica cosa que impide adelantar trabajo es mi autocontrol, no
existe: el bloqueo va en el codigo (funcion tipo `_exigir_etapa_previa()`), con test, y se muestra la
salida real del comando.
2. **Nunca adelantar etapas.** Escribir concepto + guion + elegir la sede de una pieza "para probar"
termino en: *"generaste completo el guion sin ninguna interaccion conmigo, eso no es lo que estabamos
programando"*. Se hace **solo el paso que toca** y se espera la firma; la sede y cada aprobacion las
firma un humano con su nombre (`--por NOMBRE`).
3. **Pasos = INTERACCIONES, no etapas.** Cuando pide el desglose de un proceso quiere la lista
usuario ⇄ agente numerada 1..N con ramas (`6.1`, `6.2`) y **una linea por paso**. Un desglose por
etapas o por fases lo rechaza: *"te dije muy claro que por pasos"*.
4. **Analizar y planear ANTES de editar.** "No edites, solo realiza el plan" = lectura read-only del
repo y un documento de plan (en `workspace/plans/`), sin commits ni archivos nuevos en el repo del
cliente. El plan lleva unidades de trabajo (WU), aceptacion medible, costo $0, riesgos/no-goals y las
decisiones que le tocan al dueño; cada hallazgo citado con `archivo:linea`.
5. **Evidencia, no promesas.** Al cerrar se pega la salida real (incluido el `ERROR: BLOQUEADO ...`),
`git status`/`git log` del repo tocado, y el conteo de tests. Nada se declara hecho por "deberia
funcionar".
6. **Un solo carril de estado.** No duplicar la maquina de estados en dos sitios (la copia vieja queda
declara como historica): el estado del proceso vive en un lugar y el resto lo lee.

## Como se entrega cada gate

- **Propuesta → correccion → cerrada:** maximo 2 vueltas por paso; si el cambio llega tarde, se dice
  QUE se regenera y CUANTO cuesta **antes** de ejecutarlo.
- **Costo $0 primero:** toda etapa gratis (texto, medicion, lint, plan, dry-run) se cierra antes de
  tocar una API paga, y la etapa paga exige firma explicita con presupuesto maximo (gate fisico tipo
  `.spend-gate.json`: `approved_by` humano + `providers` + TTL corto).
- **Bloqueo activo probado:** se demuestra con un comando que el script **rechaza** lo que no toca
  (`exit=1` + mensaje), y con la suite de tests en verde.

## Al construir el flujo (checklist de diseno)

1. Capa de contexto **generica** (contrato por campana/cliente) separada de la logica: nada de marcas,
   eventos, mecanicas ni rutas de UNA campana dentro del codigo.
2. Filtros iniciales como menus: cliente → campana → tipo → alcance → sede → fecha; el resto se hereda.
3. Estado por pieza en un directorio versionado, con bitacora append-only y hash del artefacto firmado.
4. Un test por paso del flujo (no solo por funcion).
5. Cableado a las piezas que YA existen del pipeline objetivo (motor, lint, publicacion) en vez de
   construir un pipeline paralelo.
6. Prueba de genericidad: un caso ficticio (otro cliente/mes/mecanica) corriendo de punta a punta en
   modo gratis.

## Pitfalls

- **Escribir artefactos "de referencia" sin firma contamina el estado:** si ya se escribio algo sin
  aprobacion, se mueve a `<sesion>/no-aprobado/`, se devuelve la etapa a su punto, y se anota en la
  bitacora que paso. No se borra el trabajo ni se deja contando como etapa.
- **Un scaffold que no pasa su propio linter es deuda inmediata:** si la herramienta genera el archivo
  con un formato que su propio validador rechaza, se arregla en la herramienta (con test), no a mano en
  cada pieza.
- **El "plan" no es un volcado:** en el chat va el resumen (vacios, fases, decisiones); el documento
  completo va adjunto (`MEDIA:`).


<!-- absorbido de specialists/devops-infra/pipelines-con-gate-humano (censo 2026-09-24) -->
# Flujos por etapas con gate humano (el freno vive en el código)


Clase de trabajo: el usuario pide **un proceso por etapas donde él aprueba cada paso** (producción de
piezas, documentos, publicaciones, despliegues, generaciones pagas). La lección que gobierna esta clase,
y que Yisus tuvo que corregir dos veces el 12-sep-2026:

> *"Generaste completo el guion sin ninguna interacción conmigo, eso no es lo que estábamos programando"*
> *"Siento que simplemente vas a trabajar en el orden que hablamos, pero no veo que estés ejecutando un
> script del repo"*

Traducción operativa: **no basta con portarse bien; el bloqueo tiene que estar en el código.**
Un pedido de "flujo asistido paso a paso" es un pedido de software con estados y firmas, no una promesa
verbal de disciplina.

## Reglas duras


1. **Nunca escribir una etapa cuyo predecesor no esté `aprobada`.** Se puede leer la especificación,
   medir, preparar candidatas y dejar todo listo — pero **no** redactar el entregable ni elegir por
   cuenta propia las decisiones que el usuario se reservó (sede, tema, alcance, gasto).
2. **Nunca firmar en nombre del usuario.** Los comandos de aprobación llevan `--por NOMBRE` y ese nombre
   solo se usa cuando él lo dio explícitamente (`--por Yisus` cuando dijo "la sede es X").
3. **El freno se implementa, no se promete.** Función de bloqueo en el script (ej. `_exigir_etapa_previa()
   en `guion_session.py`): cada comando de escritura verifica que la etapa anterior esté firmada, la
   aprobación no permite saltar etapas, y las etapas pagadas exigen un candado con presupuesto máximo.
   Si el hueco aparece en una sesión, se tapa **antes** de seguir produciendo.
4. **Antes de editar código: análisis y plan.** Yisus lo dijo textual: *"no edites nada, primero analicemos
   y planifiquemos"*. Primero inventario con evidencia (archivo:línea), después propuesta, después OK.
5. **Ritmo de 2 vueltas por etapa**: propuesta → corrección → cerrada. Cada cierre de etapa termina con
   el artefacto, el costo estimado y la pregunta `¿OK, ajuste o STOP?`. Nunca dos etapas en un mensaje.
6. **Si te adelantaste, sé honesto y no destruyas nada**: devuelve el estado a la etapa real, mueve lo
   no firmado a una carpeta `no-aprobado/`, anótalo en la bitácora y dilo en el chat. Yisus premia la
   honestidad; castiga el maquillaje.

## La máquina debe ser genérica (segundo pedido del 12-sep)


Un flujo atado a la instancia actual (una campaña, un cliente, un mes) es deuda: cuando la instancia
cambia hay que reescribirlo. El entregable de esta clase es una **máquina + un contrato por instancia**:

- Los datos duros, fechas, catálogos, plantillas, vetos y personajes salen del **contrato de la
  instancia** (ej. `planning/<slug>/campaign.yaml`), nunca de constantes en el código ni de rutas de un
  solo mes.
- El CLI arranca con **filtros iniciales** que cargan el contrato (`nueva --campaign <slug>`) y de ahí
  resuelve todo lo demás.
- **Prueba de genericidad obligatoria**: correr la máquina completa con una instancia **ficticia**
  (otro mes, otro evento, sin los elementos particulares de hoy) en modo dry-run. Si pasa, es genérica.
- Cómo auditar una máquina existente (búsqueda de constantes clavadas, quién invoca a quién, si el
  handoff con el pipeline real existe): `references/auditoria-de-genericidad.md`.

## Cómo cerrar cada etapa en el chat


```
ETAPA <n> · <NOMBRE> — <id de la pieza>
· qué se produjo (una línea) y dónde vive el artefacto
· costo real / estimado de la etapa
· lo que falta o cambió respecto a la etapa anterior
[adjunto o ruta del artefacto]
¿OK, ajuste o STOP?
```

## Señales de que el flujo está mal construido


- El agente puede escribir la etapa N sin que la N-1 esté firmada (hueco de bloqueo).
- La aprobación no deja rastro: sin hash del artefacto, sin nombre de quien firmó, sin bitácora.
- El estado real y el estado declarado difieren (artefactos escritos que "no cuentan" sin marcarlos).
- La máquina solo corre para la instancia de hoy (mes/campaña/cliente clavados en el código).
- El pipeline siguiente nunca se invoca desde la máquina: el handoff es un archivo que nadie lee.
