# Revisión independiente de CÓDIGO en 3 tajadas (caso 11-sep-2026)

Extiende §4.5 del SKILL.md: cómo se audita **código ya escrito** (no un plan) con un modelo externo sin herramientas. Caso real: repo `marketing-campaign-generator`, `glm5.3-flash` vía `api.nan.builders`.

## Por qué tajadas y no un prompt gigante

El revisor NO puede leer el repo ni ejecutar nada: juzga **solo lo que le pegas**. Un prompt con todo el material (>150 KB) diluye la atención y no permite paralelizar. Tres tajadas de 40-50 KB corren en paralelo y cada una tiene un criterio de éxito distinto.

| Tajada | Material | Lo que se le pide |
|---|---|---|
| 1. Código nuevo | Archivos completos + su contrato + sus tests | Bugs reales, **falsos verdes**, casos límite, qué falta para producción |
| 2. Cadena de gasto / seguridad | El diff de los cambios + el módulo del gate **completo** | "Vías de gasto: vía → ¿gate? → línea exacta"; combinaciones de flags que producen gasto real; tests que faltan |
| 3. Claims vs evidencia | Tu **lista de afirmaciones** al humano + la **evidencia cruda** (salidas de comandos, logs, tests) | Veredicto por afirmación: sostenida / exagerada / no sostenida / insuficiente + condiciones para firmar un OK |

**Diseño del corte (lección real):** la tajada 3 devolvió «evidencia insuficiente» para las afirmaciones sobre el gate porque **el código del gate estaba en la tajada 2**. Si una afirmación depende de código, pega en su tajada el fragmento mínimo que la prueba, o dilo en el prompt («esto lo audita el revisor 2, no lo evalúes»). Un corte mal elegido produce un veredicto blando que parece culpa del revisor.

## Ejecución

```bash
# material: prompt + evidencia, una sola pieza por revisor
cat prompt_r1_bridge.md mat_r1.md > full_r1.md
for r in 1 2 3; do (python3 /opt/data/scripts/nan_reviewer.py full_r$r.md out_r$r.md 20000 > log_r$r.txt 2>&1 &); done
```

Medido: 218 s / 250 s / 112 s, veredictos **5-6,5/10**, respuestas de 8,7-10,9 KB. `finish_reason: length` en una tajada = el razonamiento se comió `max_tokens` (ver las tres trampas en §4.5). Salidas y prompts quedan en `/opt/data/review/` para poder citarlos después.

## Qué encontró (taxonomía de hallazgos que se repite)

19 hallazgos sobre código que ya tenía **656 tests verdes**. Los patrones, que son los que hay que buscar en cualquier revisión futura:

- **CRÍTICO — parser que corrompe en silencio.** Celda de tabla markdown con `|` sin escapar → columnas extra → el resto del texto se descartaba sin aviso (el pie legal llegaba cortado al artefacto). Arreglo: recomponer columnas + avisar.
- **ALTO — default invertido rompe un llamador.** El worker dejó de pasar el modo al motor y un job `live: true` corría dry en silencio. Arreglo: modo siempre explícito en el borde + test de contrato + conflicto de flags = error.
- **ALTO — efecto secundario antes de validar.** El planner escribía el archivo de salida **antes** de validar contra el contrato (artefacto inválido en disco con exit 1). Arreglo: validar todo y escribir al final.
- **ALTO — dato derivado presentado como declarado.** La estructura inferida por máquina se emitía sin marca de origen, indistinguible de la escrita por el humano. Arreglo: campo `origin` por ítem + bandera explícita para aceptarlo.
- **ALTO — patrón de texto sin límites ni normalización.** El veto de vocabulario daba falsos positivos (subcadena dentro de otra palabra) y falsos negativos (acentos). Arreglo: normalizar + `\b` + escanear solo el texto que "sale al aire".
- **ALTO — verificación opcional que falla abierto.** La medición de la locución era opt-in y no poder medir devolvía éxito. Arreglo: por defecto se mide; no poder medir = error, con escape explícito registrado en el artefacto.
- **MEDIO — conflicto de flags resuelto hacia el lado peligroso**; ruta raíz mal calculada (`parents[N]`); denylist de strings exactos (`"Agente Ragnar"` pasaba); proveedor sin test de choke point; campo validado contra la fuente equivocada (notas internas en vez del texto final); registro corrupto → diccionario vacío silencioso; elección arbitraria ante ambigüedad.
- **BAJO —** números decimales no parseados, filas descartadas sin contarlas, códigos de salida contaminados, campo de metadatos basura, contrato decorativo (nadie lo valida), sin timeouts, nombre de log fijo que se pisa.

**Lo común a todos: fallan sin error.** Eso es lo que hay que pedirle al revisor: no «¿está bien?», sino «¿dónde puede decir OK estando mal?».

## Cerrar el ciclo (sin esto, la revisión no sirve)

1. Fix de cada hallazgo real; los de diseño (p. ej. que `approved_by` no sea prueba criptográfica) se **documentan como límite**, no se disfrazan de arreglados.
2. Re-correr la suite **como el usuario del servicio** (ver §6 del SKILL.md) y separar los fallos de entorno de los reales.
3. Dejar la tabla de hallazgos con su estado en el documento del plan (sección propia), incluidos los **abiertos** y por qué.
4. Decirle al humano los veredictos con su número (5-6,5/10) y no solo "quedó bien": la nota baja es información útil.
