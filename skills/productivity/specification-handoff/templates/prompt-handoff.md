# Plantilla — PROMPT autocontenido para editor de código (AGY/OpenCode)

Copia y llena los `[PLACEHOLDERS]`. Regla de oro: el editor no ve la conversación, así que todo debe ir aquí.

## Estructura base

```markdown
# PROMPT PARA AGY — [ASUNTO (feature/componente)] ([CLIENTE])

> **Contexto:** este archivo es el PROMPT para que AGY (editor de código) implemente [ASUNTO].
> Leer primero [SPEC-...].md (fuente de verdad) y AGENTS.md del repo.
> Fecha: [FECHA] · Autor: NeuralCrew Labs (Digital Expressions)

## INICIO DEL PROMPT

Eres el editor de código del proyecto **[REPO]** (host: [RUTA/CONTAINER]).
Tu tarea: **[DESCRIPCIÓN GENERAL DE LA FEATURE]**.

### Contexto obligatorio
1. Lee primero `docs/SPEC-...md` (si no existe en docs/, búscalo o pídelo).
2. Respeta AGENTS.md (marca, arquitectura, no inventar datos, no hardcodear secretos).

### Alcance
A. **[Archivo 1]** (`ruta/archivo.jsx`): reemplazar/añadir [X] con estados `[estado1]`, `[estado2]`…
   — Reglas de validación: [validación y bloqueos].
   — Textos exactos (verbatim del doc legal sección [N]):
     `[TEXTO_1]`, `[TEXTO_2]`…
   — Enlaces: [a] → `/ruta1` (target=_blank), [b] → `/ruta2`.
B. **[Archivo 2]** — …
C. **[Rutas]** — agregar lazy imports + `<Route path="/[ruta]" …/>` en `App.jsx`.
D. **[Páginas nuevas]** — `src/pages/[Nombre].jsx` con Header/Footer y estilo del proyecto.
E. **[Backend]** — endpoint `POST /webhook/[x]`: validar/limpiar [campos]; ampliar INSERT `leads`;
   enviar claves a `notifyActivePieces`.
F. **[DB]** — actualizar `server/schema.sql` (instalaciones nuevas) + NUEVO archivo
   `server/add_[campos]_to_leads.sql` (NO ejecutar desde el repo; se aplica aparte en la DB).

### Reglas de ejecución
- No subas a producción ni hagas commit/push salvo que se te pida explícitamente.
- No toques [archivos que NO se modifican: p.ej. AgeVerification.jsx].
- Si algo no se puede cumplir tal cual, NO lo inventes: repórtalo en el informe.
- Antes de terminar ejecuta `npm run build` y verifica que compile.

### Entrega final (informe OBLIGATORIO, en español)
1. Resumen (3 líneas máximo).
2. Tabla de archivos creados/modificados (ruta, cambio, estado).
3. Checklist de aceptación del SPEC (✓/✗) con evidencia breve.
4. Payload final: JSON que envía el frontend y claves nuevas esperadas por el backend.
5. Lo que NO pudiste implementar/verificar.
6. Resultado de `npm run build`.
7. **Limpieza:** elimina ESTE archivo de prompt (`[nombre-del-prompt].md`) al finalizar e indica su borrado.
   El SPEC se conserva como documentación permanente.

## FIN DEL PROMPT
```

## Notas de uso
- Nunca promediar 2 features en 1 prompt: un prompt = un alcance verificable.
- Si el repo es read-only del lado del orchestrator, crear los archivos en
  `/opt/data/entregables/<cliente>/docs/` respetando la estructura `docs/` y avisar al usuario de copiarlos.