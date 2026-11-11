# Plugin pagos-gate — registro determinista antes del LLM

## Qué es
Plugin de perfil en `/opt/data/profiles/<nancy|yulieth>/plugins/pagos-gate/` que registra el hook `pre_llm_call` vía `ctx.register_hook(...)`. Cuando un mensaje entrante de WhatsApp parece respuesta a la pregunta de pagos (contiene números + una categoría reconocida), ejecuta `respuestas_marca.py --marca X` y devuelve `{"context": ...}` para que el LLM SOLO confirme (prohibido re-ejecutar scripts → evita dobles escrituras en el journal).

- `config.json`: `{"marca": ..., "db": ...}` — Nancy=Golden, Yulieth=Paradise, ambos a `golden.db`.
- Guards del hook (cualquiera retorna None = silencio total): platform distinta de `'whatsapp'` (comparación EXACTA), texto >500 chars, empieza por `/`, sin números, sin categoría reconocida, o dry-run sin aplicables.
- `_contexto()` inyecta la lista de pagos clasificados + reglas del turno (no re-ejecutar, preguntar solo dudosos).

## Estado verificado (re-auditar antes de confiar)
- Activo en logs (`pagos_gate: activo`) en cada arranque, PERO cero filas del gate en `clasificacion_journal` pese a respuestas reales registradas por script manual → el hook nunca dispara en producción.
- Verificado en aislamiento: `on_pre_llm_call(...)` retorna None incluso con `platform='whatsapp'` y texto válido → la causa NO está solo en el guard de platform; instrumentar antes de culpar a un guard puntual.
- Hipótesis abiertas (confirmar, no asumir): (a) el valor real de `platform` que inyecta el gateway trae sufijo de JID y el `==` exacto corta todo; (b) el `subprocess` de `_run` falla dentro del contenedor aunque el script funcione desde el host shell (otro python/env).
- Pin por marca verificado funcionando: `respuestas_marca.py --marca Paradise --texto '...' --dry-run` resuelve al pago correcto sin tocar Golden.

## Cómo probarlo en aislamiento (verificado)
```bash
# dentro del contenedor de runtime de PROD:
docker exec hermes-agent python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('pg', '/opt/data/profiles/yulieth/plugins/pagos-gate/__init__.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m.on_pre_llm_call(user_message='1 proveedores', platform='whatsapp', sender_id='x'))
"
# dry-run del gate sin escribir:
cd /opt/data/scripts/finanzas && python3 respuestas_marca.py --db /opt/data/finanzas-casinos/golden.db --marca Paradise --texto '1 proveedores' --dry-run
# evidencia de si el gate corrió alguna vez:
sqlite3 /opt/data/finanzas-casinos/golden.db "SELECT * FROM clasificacion_journal WHERE despues LIKE '%gate%' ORDER BY rowid DESC LIMIT 10;"
```

## Trabajo abierto (plan propuesto, pendiente de aprobación)
1. Instrumentar 1 línea de log por guard y disparar con un mensaje real; si el hook no corre en el gateway, migrar a `post_gateway_admission` (se dispara en cada mensaje entrante, fail-open).
2. Unificar los `AGENTS.md` de ambos perfiles a `respuestas_marca.py --marca X`.
3. Agrupación de pagos en la pregunta (por beneficiario normalizado, 15 pagos → ~7 líneas) y respuesta por número de grupo.
4. Poblar `recurrentes` (0 filas hoy; 22 reglas ya en `conceptos_aprendidos`) para pre-clasificar y preguntar solo lo genuinamente nuevo.
5. Resolver el desfase pregunta 16:00 / ingesta 20:00 con un segundo toque vespertino o aceptando el desfase de 1 día.
