# Perfil de identidad en Hermes Desktop — profile.yaml (26/08/2026)

## Hallazgo clave

El sidebar de Hermes Desktop NO lee `agent.name` del `config.yaml` de un perfil.
`hermes config set agent.name "..."` se guarda pero con warning *"'agent.name' is not a
recognized config key — saved anyway, Hermes may not read it"*. **No es eso lo que
pinta el Desktop.**

El mecanismo CANÓNICO para mostrar "Hermóðr (Connect)" + descripción es
`<perfil>/profile.yaml`:

```yaml
display_name: "Hermóðr (Connect)"
description: "Hermóðr — El Mensajero Veloz · Comunicación multicanal, voz, atención y escalamiento. 'Llego primero y conecto lo correcto.'"
description_auto: false
```

## Dónde vive en el código (verificado en /opt/hermes 0.20.x)

- `hermes_cli/profiles.py`:
  - `read_profile_meta(profile_dir)` → lee `<dir>/profile.yaml`, devuelve
    `{description, description_auto, display_name}` (nunca lanza).
  - `write_profile_meta(...)` → actualiza solo los campos pasados.
  - `format_profile_label(name, display_name)` → renderiza `"DisplayName (canonical_id)"`.
  - `set_profile_display_name(profile_name, display_name)`.
- `hermes_cli/web_routers/profiles.py`:
  - `GET/PUT /api/profiles/{name}/soul`
  - `PUT /api/profiles/{name}/description` → escribe `description=...`, `description_auto=False`.
  - `_profile_to_dict` incluye `display_name` y `description` en el payload del sidebar.

## Procedimiento

1. Escribir/actualizar `profile.yaml` con yaml.safe_dump (allow_unicode=True,
   sort_keys=False), **preservando `ui_meta`** si ya existe (lo crea el gateway).
2. `chown hermes:hermes <perfil>/profile.yaml` si quedó root-owned (mismo fix que
   assets/: `docker exec -u root hermes-agent chown hermes:hermes <file>`).
3. Sin reinicio necesario: el sidebar re-escanea (TLL ~5s en web_server).
4. Fallback vía API: `PUT /api/profiles/{name}/description` con body `{"description": "..."}`.

## Notas

- `agent.name` en config.yaml no rompe nada (key custom) pero no es lo que muestra el Desktop.
- `description_auto: false` evita que el sistema sobreescriba con una descripción generada.
- Formato preferido por el negocio: `"<Nombre> (<Módulo>)"` → `Brokkr (Web)`, `Sindri (Producer)`.