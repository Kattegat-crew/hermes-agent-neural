# Ejemplo real: casillas de consentimiento «Ruleta Golden Game» (golden-game-landing, 2026-08-20)

Caso de uso completo del patrón SPEC+PROMPT. Repo: `/opt/repos/golden-game-landing` (read-only en el contenedor),
rama `jemadiar`. El cambio lo implementó un editor externo (AGY) a partir de:
- `docs/SPEC-CASILLAS-CONSENTIMIENTO-RULETA-2026-08-20.md` (permanente)
- `docs/PROMPT-AGY-CASILLAS-CONSENTIMIENTO-2026-08-20.md` (temporal, el editor lo borra al final)

## Requisito legal (origen)
4 consentimientos SEPARADOS, ninguno premarcado (Ley 1581/2012 datos, Ley 2300/2023 comunicaciones, Ley 643 +18):

| # | Casilla | Obligatoria | Enlace |
|---|---------|-------------|--------|
| Cb1 | «Declaro que soy mayor de 18 años.» | SÍ | — |
| Cb2 | «He leído y acepto los Términos y Condiciones de la promoción «Ruleta Golden Game», publicados en www.goldengame.com.co.» | SÍ | `/terminos` |
| Cb3 | «Autorizo de manera libre, revia, expresa e informada a GOLDEN GAME S.A.S. el tratamiento de mis datos personales, de acuerdo con su Política de Tratamiento de Datos Personales, publicada en www.goldengame.com.co.» | SÍ | `/politica-datos` |
| Cb4 | «Autorizo el envío de comunicaciones comerciales y breves por SMS, correo electrónico, WhatsApp y llamadas telefónicas. Puedo revocar esta autorización en cualquier momento a tiendes de los canales de contacto del Organizador.» | NO | — |

## Mapa auditoría (archivo ~líneas)
- `src/components/InteractiveWheel.jsx` ~593-606: 1 sola casilla combinada (`acceptedTerms`) → reemplazar por 4 estados separados (NUNCA premarcados, reset tras envío).
- `src/pages/Bono.jsx` ~270-435: formulario sin casillas y sin campo cédula → añadir cédula (validación 6-12 dígitos) + 4 casillas.
- `src/components/Footer.jsx` ~98-107: 3 enlaces a `/documentos` → T&C → `/terminos`, Política → `/politica-datos`, Juego responsable → `/documentos`.
- `src/App.jsx` ~160-167: añadir rutas lazy `/terminos` y `/politica-datos` (páginas `pages/Terminos.jsx`, `pages/PoliticaDatos.jsx`).
- `server/webhook-server.js` `sanitizeLead()` ~113-133 y INSERT ~171-174: validar consent y ampliar columnas.
- `golden-game-backend/`: nueva migración (versionada, NO ejecutar desde el repo).

## Payload de evidencia
```json
{
  "consent_age18": true,
  "consent_terms": true,
  "consent_data": true,
  "consent_marketing": false,
  "consent_version": "3.0-2026-08-20",
  "consent_at": "2026-08-20T15:30:00.000Z"
}
```
- `consent_at` lo genera el frontend; `IP` la captura el servidor (el frontend NO envía IP).
- Backend rechaza 400 si faltan `consent_age18/consent_terms/consent_data === true`. `consent_marketing` default false.

## SQL migración
```sql
ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS consent_age18     BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS consent_terms     BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS consent_data      BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS consent_marketing BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS consent_version   VARCHAR(100),
  ADD COLUMN IF NOT EXISTS consent_at        TIMESTAMPTZ;
```
> La migración se versa en el repo para auditoría pero se aplica aparte (PostgreSQL `golden_game`, host `10.0.1.3`).

## Tips del caso
- Las páginas legales nuevas usan Header/Footer existentes; contenido íntegro copiado del doc legal v3 (si no está en el repo, el PROMPT ordena NO inventar y reportar pendiente).
- `AgeVerification.jsx` (puerta +18 con localStorage) NO se toca: es la puerta del sitio; las casillas del formulario son el consentimiento por reclamación.
- Checklist de aceptación de 10 items (frontend no-premarcado, Cb4 no bloquea envío, enlaces `target=_blank`, footer rutas, backend 400, INSERT columnas, ActivePieces, SQL versionado, `npm run build`).