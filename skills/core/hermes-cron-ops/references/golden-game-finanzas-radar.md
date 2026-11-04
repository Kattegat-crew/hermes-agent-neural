# Radar Financiero Golden Game / Lucky — Operación (03-nov-2026)

Skill dedicada pendiente: el hook `guard_autoskill_create.py` falla cerrado ('unparseable stdout') y bloquea TODO `skill_manage create` — crear la skill propia cuando el guard esté reparado, con el contenido de este archivo.

Sistema de pagos de casinos (Golden Game = marca Golden; The Grand Paradise Club = marca Lucky/Paradise). Spec: `Kattegat-crew/Golden-Game-Casinos` → `.specs/SPEC-clasificador-obligaciones.md`.

## Topología (verificada en vivo)

- **Repo:** DEV host `/opt/golden-game-landing/` (propietario `orca`). Escribir via scratch + instalar como root; commit como `Jemadiar1 <Jemadiar1@gmail.com>` con `HOME=/opt/hermes-agent-data/home git -c user.name=... -c user.email=...`; el hook graphify imprime ruido en el push (no es error). El fetch desde el contenedor usa la deploy key equivocada — verificar estado del repo por root.
- **Despliegue:** copiar a PROD host `/opt/hermes/data/scripts/finanzas/` (chown 10000:10000) → `docker cp` a `hermes-agent:/opt/data/scripts/finanzas/` (chown 10000 dentro).
- **DB:** `golden.db` en `/opt/data/finanzas-casinos/` (contenedor PROD). Tabla `pagos` (categoria/concepto/duplicado_de), `clasificacion_journal` audita cambios, `conceptos_aprendidos` = reglas beneficiario→categoría.
- **Módulos (stdlib puro):** `etiquetas.py` (motor "Pago-Arriendo Cachipay / Pago-Coljuegos..."), `preguntas.py` (pregunta diaria numerada, `--marca Golden|Paradise`, excluye duplicados), `respuestas.py` (parser respuesta libre/audio, escribe + journaliza + aprende regla), `informe_diario.py` (informe 20:00), `actualizar_sheet.py` (Sheet diario, Drive de Golden con secret `golden`, NO en carpeta de jonathaun124 → 403), `dedupe.py`.
- **Tests:** suite en `finanzas/tests/`, DB temporal por test (no reusar archivo entre tests).

## Criterio de dedupe conservador (dedupe.py)

- **Marca, nunca borra**: `duplicado_de` apunta a la fila conservada; log en `dedupe_log`. Toda consulta de informe/pregunta lleva `duplicado_de IS NULL`.
- **Casos demostrados**: (1) mismo monto(±1)+fecha+fuentes DISTINTAS (avalpay+aval+pse = mismo pago por 3 correos) → conservar la fuente más rica (avalpay>aval>ecollect>placetopay>netcash>pse); (2) GOU PAYMENTS es pasarela que replica el pago real (ENEL/Calera) → la fila GOU cede si existe no-GOU del mismo monto/fecha.
- **NO dedupe misma fuente**: dos pagos PSE iguales el mismo día pueden ser reales → "ambiguos" para el humano.

## Loop de clasificación conversacional

- Cron 20:15 perfil `nancy` (Golden, WhatsApp 573214094625), 20:16 perfil `yulieth` (Lucky, 573107864877). Wrappers con `--marca` + `|| true`; entrega `whatsapp:<num>@s.whatsapp.net` (receta en hermes-cron-ops §25).
- El humano responde libre ("1 arriendo cachipay, 2 servicios") o con audio; el AGENTS.md del perfil ordena transcribir y correr `respuestas.py --texto "..."`, reenviando solo la salida.
- "no sé" queda pendiente sin inventar. Máximo 1 pregunta + 1 recordatorio/día; silencio si no hay pendientes.
- **Decisión del Admin (03-nov): NO sembrar el catálogo de supuestos** — clasificar todo desde cero; el catálogo de Bob son hipótesis a validar por la realidad, no reglas precargadas.

## Lecciones

- BBVA Net Cash: el «BBVA Ref» NO es clave única (dos archivos de firma comparten Ref) — la clave es el archivo .PAP.
- Contacto externo nuevo → mensaje de contexto en lenguaje llano ANTES del primer cron.
- Métrica: semana 4 la pregunta diaria debería cubrir <30% de los pagos (solo lo nuevo).