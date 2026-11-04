# Campañas de difusión WhatsApp por tandas (base de contactos)

Procedimiento verificado en producción (28-oct-2026, recordatorio sorteo Golden/Lucky: 40 envíos planeados, dry-run y cola validados). Para cualquier envío a UNA BASE de contactos (no 1:1), usar este patrón — NO enviar directo con `POST /send` uno por uno a mano.

## Herramienta existente
- `/opt/data/scripts/sorteo/enviar_sorteo.py` + `config.json` (plantillas, links, pacing, alias de sedes) + `cola.db` (sqlite: `envios` con estado por teléfono + `eventos` auditables).
- Comandos: `selftest` · `init --base base.csv` · `stats` · `preview --n N [--marca|--sede]` · `enviar --tanda N` (**dry-run por defecto**; `--enviar` = real) · `export --out envios.csv`.
- Garantías del script: nunca reenvía (estado `enviado` sale de la cola), ventana horaria bloquea fuera de 9–19 h, excluye `consent=false` según config, teléfonos enmascarados en preview.
- El texto vive SOLO en `config.json` (cero texto hardcodeado): editar plantillas/links ahí, no en el .py.

## Consolidación de base (3 fuentes, dedup por teléfono)
1. Leads PG: `golden_game.leads` y leads de paradise_casino (`tel`, `nombre`, `sede`, `consent_marketing`).
2. Hojas «Registro bonos» (XLSX en Drive): teléfonos con formato sucio (`+57`, espacios, guiones) y **enmascarados tipo `573****7470` → descartar**, no adivinar.
3. Twenty: `person.phonesPrimaryPhoneNumber` en los DB `workspace_*` de twenty-db.
- Normalización: quitar no-dígitos, quitar prefijo `57`, aceptar SOLO 10 dígitos empezando en `3`. Dedup por teléfono normalizado; una persona en dos marcas recibe el mensaje de la marca donde se inscribió (ej. Golden por defecto).
- Evidencia: 120 registros crudos → 44 únicos; coincidencia sheet↔Twenty 43/44.

## PITFALL: Twenty tiene fichas DEMO de seed
Los workspaces de Twenty (~99 fichas) están contaminados con ~50 perfiles demo del seed (Brian Chesky, Dario Amodei, Patrick Collison, `createdAt` de la fecha de seed). **NUNCA contar `person` crudo como base real**: filtrar siempre por teléfono CO válido `^3[0-9]{9}$` antes de deduplicar.

## Pitfalls de canal
- El bridge NO expone validación `onWhatsApp`/`/check`: no hay pre-validación de números. Validar formato localmente; los inválidos fallan al enviar y quedan como `fallido` con error en cola.
- `POST /send` es serializado y seguro para tandas; verificar cada envío con HTTP 200 + `messageId` `3EB0...` + `/health` `queueLength:0` (ver sección Envío proactivo de SKILL.md).

## Enrutamiento por marca (flota multi-sesión, verificado 28-oct-2026)
Cuando los contactos están segmentados por marca/cliente, cada marca recibe desde SU propio número oficial (mejor que todo por el central):
- `config.json` admite mapa `"bridges": {"Golden": "http://127.0.0.1:3001/send", "Lucky": "http://127.0.0.1:3002/send"}` — el script elige endpoint por `marca_plantilla` y registra `"<mid> via <marca>"` en `eventos`.
- En PROD los puertos de marca (:3001/:3002) NO están publicados al host: ejecutar el emisor DENTRO del contenedor (`docker exec hermes-agent python3 /opt/data/scripts/sorteo/enviar_sorteo.py ...`).
- Probe de vida sin enviar: `curl -X POST -d '{}' /send` → debe responder `{"error":"chatId and message are required"}`.
- Despliegue DEV→PROD: scp a `/opt/data/scripts/sorteo/` + `chown -R hermes:hermes` (los ficheros llegan root-owned y el cron del perfil corre como hermes → `sqlite` daría EACCES).
- Health por sesión: `docker exec hermes-agent sh -c 'for p in 3000 3001 3002; do curl -s http://127.0.0.1:$p/health; done'`.

## Pacing anti-ban (volúmenes <100)
- Regla general (solo el número central): **NO distribuir una misma campaña entre números arbitrarios** — bajo ~100 envíos no reduce riesgo y multiplica el riesgo operativo.
- Excepción correcta: repartir **por marca** entre los números oficiales de cada marca (cada contacto recibe de SU marca, es su relación real, no dispersión artificial).
- **Sesión recién emparejada = pacing extra conservador:** si el número fue re-vinculado el mismo día (backup `session.retirada-*`/`pair-qr.log` reciente), subir pausas a 60–150 s y tandas de 9–10; nunca mandar toda la base de golpe el mismo día del pairing.
- Pausa aleatoria 45–110 s entre mensajes; tandas de 10–13; ventana 9–19 h; sin imágenes; un solo link; texto personalizado (nombre+sede genera variación natural entre mensajes).
- Riesgo bajo cuando los contactos registraron su número presencialmente en el negocio (señal de relación, no cold outreach).
- Incluir siempre opt-out ("responde BAJA") y procesar las respuestas BAJA antes de la siguiente campaña.
- Cumplimiento Ley 1581 (CO): excluir `consent=false`; los `n/d` con registro presencial de boleta se envían por decisión del Admin.

## Verificación antes de enviar (obligatoria)
1. `selftest` (normalización + render + placeholders sin `{}`).
2. `init` + `stats`: revisar pendientes vs omitidos_consent.
3. `preview` con teléfonos enmascarados y aprobación del Admin del TEXTO.
4. `enviar` en dry-run, luego `--enviar` por tandas; `export` al cierre como registro.

## Cierre de campaña: cron programado + informe automático (verificado 28-oct-2026)
- **Cron en el host PROD** (`/etc/cron.d/sorteo-recordatorio`): entradas `tanda.sh <marca> <n>` con **guard de fecha** — si `date +%F` != fecha del evento, loguea `skip ... fecha X != Y` en `/var/log/sorteo-recordatorio.log` y sale sin enviar. Probar el guard el día ANTERIOR (debe imprimir skip: valida el cron end-to-end con riesgo cero).
- El cron del host corre como root y llama `docker exec hermes-agent python3 <RUTA_ABSOLUTA>/enviar_sorteo.py ...`: la cwd por defecto del contenedor es `/opt/hermes`, la ruta relativa al script falla con "can't open file".
- **Informe de cierre al Admin**: `informe_envio.py` lee `cola.db` y arma resumen por marca (enviados/fallidos/pendientes + ventana real de envío, cada fallido con nombre+sede+últimos dígitos+error, excluidos a propósito con motivo) + CSV completo (`reporte_envio_29oct.csv`). Con `--enviar-a <num>` el informe sale por el bridge central :3000 al WhatsApp del Admin a hora fija (ej. 10:45, después de la última tanda) vía `informe.sh` con el mismo guard de fecha.
- **PITFALL selftest vs copy del Admin**: las aserciones del selftest NO deben hardcodear decisiones de copy (ej. exigir "BAJA" en el texto). Si el Admin ajusta la plantilla a última hora, el selftest rompe en falso. Verificar render y placeholders, no decisiones de contenido.
- **Nota opt-out (29-oct, sorteo Golden/Lucky)**: el Admin ordenó QUITAR la línea "responde BAJA" — para recordatorios a inscritos presenciales del negocio el mensaje cierra con el link. Mantener la recomendación de opt-out para cold outreach; seguir la instrucción del Admin en cada campaña.
- **Prueba end-to-end pre-vuelo**: antes del envío masivo, renderizar la plantilla con datos reales y enviar UNA muestra desde el número de la marca (bridge :3001/:3002) al WhatsApp del Admin → él confirma el render en su teléfono (HTTP 200 + `messageId 3EB0...`). No vale solo el dry-run: valida tipografía, saltos y link en el cliente real.
- **Ajustes de última hora** (quitar/añadir líneas, incluir contactos puntuales): tocar SOLO `config.json`/plantillas y regenerar el plan; nunca el `.py`.

## Base viva: sincronizar leads antes de cada tanda
Los leads siguen entrando (formularios de Meta) mientras se planifica el envío. **Nunca congelar la lista con un `init` único.**
- `sync_leads.sh` corre en el HOST de PROD: vuelca `golden_game.leads` y `paradise_casino.leads` con `copy (...) to stdout with csv` vía `docker exec infra-postgres psql`, y `sync_leads.py` hace upsert contra `cola.db`.
- Reglas del upsert: nuevo + móvil válido → `pendiente`; `consent_marketing=false` → `excluido_consent`; un `enviado` JAMÁS se toca; un excluido se reactiva solo si el consent pasa a `true`.
- Correr el sync ~15 min antes de CADA tanda (ej. 08:45 / 09:40 / 10:25) y dar a cada tanda un tope ("hasta N", ej. 20) en vez de un número exacto: así los leads nuevos entran sin re-editar el cron.
- Un lead que llega después del último barrido no entra en la ola; preguntar al Admin si se agrega una pasada rezagada, no asumirlo.

## Higiene del repo
- Código versionado en el repo `Hermes-casinos` (`scripts/sorteo/` + `docs/recordatorio-sorteo-<fecha>.md`); el repo guarda proceso, no datos.
- NUNCA versionar `cola.db`, `base*.csv`, `plan*.csv`, `reporte*.csv`: son datos personales de cliente.
- El número del Admin NO se hardcodea: `informe.sh` exige `ADMIN_WA_NUM` y el cron lo pasa (`... root ADMIN_WA_NUM=<num> /opt/.../informe.sh`); `docker exec -e ADMIN_WA_NUM=...` lo propaga al contenedor.
- `python3 -m py_compile` deja `__pycache__` dentro del repo: borrarlo antes del `git add`.
