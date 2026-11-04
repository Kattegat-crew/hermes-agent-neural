# Registro de descartes — ático `/opt/data/home/.hermes/skills` (2026-09-20)

Contexto: el ático se archivó en `data/archive/attic_home_hermes_skills_20260920.tar.gz`
(544 skills, 66,5 MB) y el canon absorbió 288. Tras la promoción, el contraste
**ático vs canon** deja **7 nombres** sin equivalente canónico. Se revisaron uno por uno
y **se decide NO promoverlos**: son cáscaras vendor del pack de `opencode`
(246–291 B, `compatibility: opencode`, una línea de prosa y ninguna procedimiento),
y sus dominios ya están cubiertos por skills canónicas reales.

| Nombre en el ático | Tamaño | Dominio | Decisión | Equivalente canónico |
|---|---|---|---|---|
| `op-cli` | 275 B | 1Password CLI / inyección de secretos | descartar | `specialists/monitoring-security/1password` |
| `improve` | 277 B | mejora iterativa de código | descartar | `specialists/hermes-internal/skill-improver` |
| `tiltup` | 246 B | arranque de stacks con Tilt | descartar | `devops/tilt` |
| `spanish-deliverable-proofreadig` | — | corrección de entregables en español | descartar | `specialists/media-video/spanish-deliverable-proofreading` (la buena; la del ático lleva **typo en el nombre**) |
| `impeccable` | 291 B | pulido de código / builds sin warnings | descartar | parcial vía la familia `anti-slop*`; el ático solo aporta una línea |
| `axe-ios-simulator` | 258 B | auditoría de accesibilidad en simulador iOS | descartar | sin equivalente: **toolchain iOS no aplica** a una flota Linux |
| `ios-device-screenshot` | 271 B | capturas de dispositivos iOS | descartar | sin equivalente: idem anterior |

## Criterio aplicado

1. **Contenido real = procedimiento verificable.** Una cáscara de < 300 B con `compatibility: opencode`
   no enseña ningún flujo; promoverla solo infla el catálogo y ensucia la búsqueda semántica.
2. **Un dominio, una skill.** Si ya existe canónica que cubre el dominio, no se promueve el duplicado
   (regla del protocolo de 4 vías: *nutrir* lo existente > crear).
3. **Aplicabilidad a la flota.** Las herramientas iOS/macOS no son ejecutables en los contenedores Linux
   de la flota; se descarta por inaplicable, no por calidad.

## Trazabilidad

- Origen íntegro: `data/archive/attic_home_hermes_skills_20260920.tar.gz` (restaurable con `tar -xzf`).
- Promoción previa: commit `1797ced130` (288 skills del backup de perfiles + ático).
- Para rehabilitar cualquiera de los 7: extraer del tar, endurecer el `SKILL.md` con procedimiento real
  y abrir un commit en `skills/`.
