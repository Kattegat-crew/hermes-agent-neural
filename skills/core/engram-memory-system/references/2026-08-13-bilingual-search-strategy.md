# Bilingual Search Strategy for Engram

**Learned:** 2026-08-13 — Session donde el usuario preguntó 4 veces sobre un cambio en modelos de OpenCode.

## El problema

El usuario pregunta en español: "¿qué cambio hicimos con los modelos de OpenCode?"

Yo busco en Engram:
- `mem_search(query="OpenCode modelo cambio")` → 0 resultados
- `mem_search(query="OpenCode agentes modelos cambio")` → 0 resultados  
- `mem_search(query="cambio modelo agente subagentes")` → 0 resultados

Finalmente busco en inglés:
- `mem_search(query="model")` → **Encontrado**: "Switched OpenCode agent models to Xiaomi MiMo V2.5"

## Por qué pasa

Engram memories son guardadas por múltiples actores:
- Subagentes (que operan en inglés)
- El `mem_capture_passive` tool
- Sesiones de otros agentes (OpenCode, Claude Code, etc.)
- Scripts de guardado automático

Todos estos tienden a escribir títulos y keywords en INGLÉS, incluso cuando el usuario habla español.

## Protocolo de búsqueda (cuando usuario pregunta en español)

1. Buscar con términos del usuario en español
2. Si vacío → traducir al inglés el concepto central (buscar UN sustantivo, no frase)
3. Si vacío → buscar término aún más amplio (singleton)
4. Siempre pasar `all_projects=True`
5. No rendirse después de 1 intento — probar al menos 3 variaciones

## Ejemplos reales

| Pregunta usuario (ES) | Search exitoso (EN) |
|---|---|
| ¿cambio modelos OpenCode? | `"model"` |
| configuración Twenty CRM | `"Twenty CRM"` |
| plan despliegue agentes | `"deployment"` o `"production"` |