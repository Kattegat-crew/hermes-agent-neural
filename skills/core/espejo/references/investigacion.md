# Base de investigación y decisiones de diseño

Qué hace la industria y qué copiamos (o no) en `espejo`.

## 1. Reflexion — Shinn et al., NeurIPS 2023

Arquitectura de reflexión verbal: el agente ejecuta, recibe una señal de feedback (escalar o en lenguaje libre) y escribe una reflexión que guarda en un **buffer de memoria episódica** para inducir mejores decisiones en intentos posteriores. No actualiza pesos: aprende en el contexto. En la práctica el buffer se mantiene pequeño; si crece, arrastra ruido y encarece cada intento.

**Tomado:** el ciclo ejecutar → reflexionar → reinyectar y el buffer episódico acotado (nuestro equivalente: el ledger + tope de 3 lecciones por sesión). **No tomado:** el bucle de reintento automático dentro de la misma tarea (aquí la autopsia es al cierre, no un loop de producción).

- https://arxiv.org/abs/2303.11366

## 2. CRITIC — Gou et al., ICLR 2024

La autocrítica sin herramientas externas es débil; con feedback de herramientas (ejecutar código, buscar, verificar) el modelo corrige de verdad. «Crucial importance of external feedback».

**Tomado:** el dossier se calcula desde `state.db` y los resultados reales de las tools; el agente no se evalúa «de memoria». **No tomado:** el ciclo interactivo multi-turno (aquí hay una sola pasada con evidencia precalculada).

- https://arxiv.org/abs/2305.11738

## 3. Huang et al. — «LLMs Cannot Self-Correct Reasoning Yet» (ICLR 2024)

La autocorrección **intrínseca** (sin feedback externo) no solo no mejora: a veces empeora el resultado. Sesgo de auto-preferencia y sycophancy.

**Tomado como límite explícito:** toda afirmación sin evidencia externa se marca «sin evidencia»; las correcciones del humano pesan 3x; la crítica adversarial es obligatoria para contrarrestar la complacencia.

- https://arxiv.org/abs/2310.01798

## 4. Postmortem blameless de Google SRE

Estructura: registro escrito del incidente, su impacto, las acciones tomadas, la causa raíz y las acciones de seguimiento para evitar la recurrencia; cultura blameless (se investigan las causas sistémicas, no se culpa a personas); revisión formal con criterios («¿se recogieron los datos clave? ¿la causa raíz es suficientemente profunda? ¿el plan de acciones es adecuado?») y la regla «no postmortem left unreviewed».

**Tomado:** el esqueleto (evidencia → impacto → causa → acción), la obligación de que toda lección tenga destino y dueño, y la revisión como parte del proceso. **Adaptado:** sin «difusión amplia» ni datos que identifiquen a usuarios finales (los informes son internos y pueden contener contexto de clientes).

- https://sre.google/sre-book/postmortem-culture/

## 5. Patrón `claude-reflect` (plugins de la comunidad Claude Code)

Sistema de autoaprendizaje de dos etapas: (1) hooks que detectan patrones de corrección («no, usa X», «actually…», «usa X no Y») y los encolan; (2) un comando `/reflect` que convierte esas correcciones en memoria permanente (CLAUDE.md/AGENTS.md) y, cuando detecta repetición, en skills reutilizables. Repo: https://github.com/BayramAnnakov/claude-reflect

**Tomado:** el enrutamiento por destino, la detección de correcciones como señal primaria, el modo «patrones» sobre N sesiones y la idea de que la corrección repetida se convierte en skill. **No tomado:** el hook que analiza **cada prompt** (demasiado ruido y coste por turno); aquí el análisis es al cierre y sobre el dossier completo.

## 6. Patrón «MISTAKES.md» / lecciones con evidencia

Registro append-only de errores con la evidencia del fallo; una regla solo se «promociona» cuando el mismo error reaparece. Evita aprender de un caso aislado.

**Tomado:** el ledger JSONL y la regla 1-2-3 (1 = ledger, 2 = parche, 3 = guard).

## Decisiones propias (no copiadas)

1. **Un disparador de una palabra (`espejo`)** en vez de un comando CLI: el cierre de sesión debe costar 6 letras.
2. **Dossier determinista en Python stdlib** (`state.db` en `mode=ro`, `active=1`): las métricas no dependen de que el modelo recuerde bien.
3. **Digest corto + JSON en disco**: el agente no se ahoga leyendo 4.000 mensajes.
4. **Rúbrica binaria de 8 checks** en vez de una nota 1-10: una nota subjetiva no es accionable.
5. **Destino obligatorio por lección** y tope de 3: sin destino, la reflexión se evapora; sin tope, se convierte en ruido.
6. **Guard como escalada, no como reflejo:** un hook por cada error es burocracia; solo a la tercera aparición.

## Lo que deliberadamente NO hacemos

- No puntuamos «calidad» con un LLM juez (coste y deriva); medimos hechos y citamos texto.
- No publicamos los informes ni los mandamos a clientes.
- No reintentamos la tarea automáticamente desde esta skill: eso es trabajo de la sesión, no de la autopsia.
- No sustituimos la revisión humana: el informe propone, el humano aprueba lo que toca config/prod.
