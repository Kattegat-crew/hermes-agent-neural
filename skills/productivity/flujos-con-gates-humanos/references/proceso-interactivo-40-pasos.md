# Proceso de guiones como flujo interactivo (40 interacciones) — spec y vacíos

Acordado con Yisus el 12-sep-2026. Es el "cómo debe quedar" del proceso de guiones de campaña. El plan
de implementación completo vive en `workspace/plans/PLAN-PROCESO-GUIONES-INTERACTIVO-2026-09-12.md`.

## Paso = UNA interacción (usuario ⇄ agente)

**Arranque**
1. Usuario pide ejecutar el proceso de guiones.
2. Agente ejecuta `guion_session.py` y muestra menú de **empresa** (registradas + nueva).
3. Usuario selecciona empresa.
4. Agente muestra menú de **campañas** de esa empresa (con vigencia) + "nueva".
5.1 Campaña existente: agente avisa si el T&C cambió y qué quedó derogado; sigue en 9.
5.2 Campaña nueva: agente pide documentos (T&C/políticas, brief del evento, fechas, premios, sedes, legal, identidad).
6. Usuario entrega los documentos.
7. Agente propone el borrador del **contrato de campaña**.
8. Usuario revisa y firma el contrato → queda versionado como única fuente.
9. Agente muestra menú de **tipo de pieza** (reel · story · post · carrusel · banner).
10. Usuario selecciona el tipo.
11. Agente muestra menú de **alcance**: local específico o campaña general.
12.1 Local: usuario elige sede → agente carga dirección, fotos reales y placa.
12.2 General: agente usa placa "pintas de las cartas" y avisa que no hay dato de pueblo.
13. Agente fija fecha/slot con el calendario y crea la sesión con **bloqueo duro**.

**Datos y concepto**
14. Agente presenta la **ficha de datos duros** (mecánica con fuente, fechas, premios, legal, pendientes).
15. Usuario aprueba o corrige → firma etapa 0. **GATE 1**
16. Agente propone **2-3 conceptos** (ángulo, gancho con fuente, saturación) y recomienda uno.
17. Usuario elige o pide ajuste (máx. 2 vueltas) → firma etapa 1.
18. Agente escribe el **guion** contra el T&C vigente y el formato de serie de la campaña.
19. Agente **mide** la locución (edge-tts) y corre el lint (pie legal, veto, spine, duración real).
20. Usuario aprueba, ajusta o STOP → firma etapa 2. **GATE 2**

**Producción (por el motor que ya existe)**
21. Agente genera el **plan de escenas** (`brief.json`) con escenas/tomas y costo estimado.
22. Usuario aprueba el plan.
23. Agente arma los **prompts de imagen** con los sheets de la campaña + refs de la sede.
24. Usuario aprueba los prompts. **GATE 3**
25. Agente pide **candado de gasto** de keyframes (nº, precio, tope, intentos).
26. Usuario firma → agente genera por el motor y verifica identidad y ausencia de texto inventado.
27. Agente presenta keyframes + QA + gasto real; usuario aprueba o manda repetir (con costo dicho antes).
28. Agente compone la **post-producción** (logo, cifras, placa, pie legal).
29. Usuario aprueba los overlays.
30. Agente arma los **prompts de animación** y pide candado de clips.
31. Usuario firma → agente ejecuta y registra clips + costo real.
32. Usuario aprueba los clips.
33. Agente produce el **audio** (edge $0 · ElevenLabs con candado) y lo mide contra las ventanas.
34. Usuario aprueba la voz.
35. Agente **ensambla** el reel 9:16 y lo sube al portal de revisión.
36. Usuario revisa y aprueba (si pide ajuste, el agente dice qué se regenera y cuánto cuesta).

**Cierre**
37. Agente corre **QA-INTEGRIDAD** contra el T&C y pide la firma del Admin.
38. Admin aprueba → agente marca la pieza `aprobado` en el calendario.
39. Agente publica en el slot programado y registra el resultado.
40. Agente cierra la sesión: costo real, bitácora y aprendizaje que alimenta la campaña.

## Vacíos verificados que impiden esos pasos (12-sep-2026, read-only)

| # | Vacío | Evidencia |
|---|---|---|
| G1 | Sin capa de campaña: datos duros y calendario con ruta fija | `guion_session.py:56` `DATOS=data/datos-duros.yaml` · `:57` `CALENDARIO=planning/calendario-sep2026/calendario.jsonl` |
| G2 | Clientes nuevos no entran | parser `choices=["golden","lucky"]` (`:866`, `:883`) |
| G3 | Sin menús ni estado de conversación (`siguiente`/`menu`) | comandos de un solo tiro |
| G4 | La firma no llega al gate físico | `candado` solo anota en la sesión; `.spend-gate.json` lo valida `scripts/spend_gate.py` |
| G5 | Etapas pagadas no ejecutan ni devuelven nada | sin `POST /jobs` ni manifest de vuelta a la sesión |
| G6 | Sin etapa 6 real (overlays por campaña) | existen `image_refiner.py`/`ffmpeg_client.py`, no un armador |
| G7 | Portal y calendario sin cablear desde la sesión | `publish-review.sh`, `cron_publish_due.py` existen, nadie los llama |
| G8 | QA-INTEGRIDAD de la pieza final a mano | `auto_auditor.py` audita audio/video, no cumplimiento |
| G9 | Sin prueba de genericidad | no hay fixture de campaña ficticia |
| G10 | Direcciones de sede no existen en dato estructurado | `assets/sedes/index.json`: `direccion: None` en las 13 |

## Diseño en 4 capas

```
CAPA 1 CAMPAÑA    planning/<slug>/campaign.yaml  (contrato único; nuevo contracts/campaign.schema.json)
CAPA 2 PIEZA      sessions/<pieza>/  (12 etapas, bloqueo duro, firmas, bitácora)
CAPA 3 DIÁLOGO    guion_session.py como máquina de interacción (menu/siguiente + interaccion.jsonl)
CAPA 4 EJECUCIÓN  scene_plan → reel_worker /jobs → manifest → portal → calendario → content-intel
```

Contrato de campaña (campos): `slug, cliente, marca(s), evento, mecanica{texto, fuente{id,fecha,version},
vigencia}, fechas/jornadas, premios[], pie_legal por marca, sedes_activas[] + direcciones, canales +
cadencia, formato_serie, vocabulario_vetado[], personajes/sheets por tipo de pieza, reglas de imagen,
voz por marca, presupuesto por etapa, piezas[]`.

## Fases del plan (todas $0, dry-run)

- **F0** contrato de campaña: schema + migrador desde `data/datos-duros.yaml`/calendario + loader + prueba con campaña ficticia.
- **F1** máquina de interacción: `interaccion.jsonl`, `siguiente`/`menu`, estados por paso y **un test por cada una de las 40 interacciones**.
- **F2** firma y gate físico: `candado` escribe `.spend-gate.json` (TTL ≤ 24 h, `providers`); job live sin gate = bloqueado.
- **F3** puente al motor: `plan` con filtros de campaña, `producir` (job + manifest de vuelta), `postimagen`, QA keyframes/clips.
- **F4** cierre: portal + firma Admin + `aprobado` en calendario + QA-INTEGRIDAD + costo real.
- **F5** verificación: E2E de genericidad en dry-run, documentación y regresión cero contra la campaña vigente.

**Regla de parada:** ninguna unidad se cierra sin evidencia observada (comando + salida).
