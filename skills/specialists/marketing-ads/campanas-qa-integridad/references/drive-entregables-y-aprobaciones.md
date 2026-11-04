# Drive: estructura de entregables + registro de aprobaciones (26/08/2026)

Estructura canónica acordada con el equipo para TODAS las campañas. Anclada a la
carpeta raíz de personajes/material del cliente (ej. `1SBBnc8gFqsTq-DN21-f7Hxxg-DwUHqPd`),
no a una carpeta global "Campañas".

## Árbol canónico por empresa

```
Marketing {Golden|Lucky}/          ← carpeta real de cada empresa en Drive
└── Campañas/
    └── <slug>/                    ← slug del campaign.yaml
        ├── 00-contrato/           ← campaign.yaml + estado.json + QA-INTEGRIDAD
        ├── 01-docs/               ← los 5 .docx de la fábrica + QA-INTEGRIDAD.md/.json
        ├── 02-guiones/            ← guiones v1 (plan) + v2 (Bragi), para aprobación
        ├── 03-piezas/             ← posters, carruseles, stories, banners, tapas (+ assets/)
        └── 04-aprobadas/          ← SOLO lo aprobado, nombre con versión y firma
```

- `<slug>` en minúsculas separado por guiones, ej. `bingo-millonario-sep2026`.
- `assets/` dentro de `03-piezas/` para overlays/PNG con alpha (contador, balota53),
  variante por marca (anillo dorado #DDC316 Golden / #C9A227 Lucky).

## Puente manifest → Drive (Fase E)

`scripts/manifest-estado.py` acepta `--drive-aprobadas <folder_id>` y escribe en el
`estado.json` un bloque `drive: {aprobadas, estructura}` para que cualquier bot sepa
a dónde va cada cosa sin buscarla. Schema v2 agrega `aprobada_por` por pieza.

```bash
python3 scripts/manifest-estado.py <campaign.yaml> --output <out> --etapa bragi \
  --drive-aprobadas "<id de 04-aprobadas/>"
```

## Registro de aprobación (trazabilidad en 3 lugares)

El chat de grupo (Hermes Desktop) NO distingue autores → convención de firma:

1. **Chat**: quien aprueba firma ("Aprobado P3 —Jesús" / "Aprobado G1 —Jonathan").
2. **Manifest `estado.json`**: `aprobada_por` + `aprobada_en` (timestamp) + versión
   del contrato. Social/Ads solo publican piezas `estado: aprobada`.
3. **Drive `04-aprobadas/`**: archivo con nombre `_APROBADA-v<N>` + nombre del
   aprobador; Bragi además sella el doc de guiones con fecha.

## Pitfalls operativos

- **Subidas a Drive SIEMPRE con `HERMES_HOME` raíz** (`export HERMES_HOME=/root/hermes-agent-legacy-docker/data`),
  NO el del perfil: `google_api.py` busca el token OAuth en esa ruta. Con HERMES_HOME
  de perfil el upload falla silenciosamente ("no token").
- Antes de crear la estructura, confirmar con el cliente/Admin la carpeta raíz real
  (puede tener `Marketing Golden` / `Marketing Lucky` separadas) — no asumir una global.
- El mapa de carpetas se registra en `brain/folder-maps/<campaña>-campanas.md` con los
  IDs de cada subcarpeta para que el pipeline los jale sin re-buscar.

## Lección: el contrato es la única fuente de verdad de tiempos

Cuando cambian los T&C (caso real: horario 7PM → "Viernes desde 5PM (17:00), escalonado
en tandas"), actualizar el `campaign.yaml` en TODAS las referencias antes de regenerar:
- `campaign.promotion.description` (menciona la hora)
- `campaign.events[].time` (cada evento, incluida la gran final)
- `campaign.piezas[].tema` de story/banner que llevan la hora en el texto

Verificación post-cambio: `grep -nE "7PM|19:00" <campaign.yaml>` debe dar 0. Si el
contrato queda con la hora vieja, las piezas autogeneradas (docs, calendario, posters
paramétricos) heredan el dato equivocado — los bots visuales lo detectan y bloquean.
