# Fix de provider — custom:nan-builders → NaN-Builders (Hermes serve v0.20.4)

## Síntoma
El Desktop / serve lanza:

```
Unknown provider 'custom:nan-builders'. Check 'hermes model' for available providers, or run 'hermes doctor' to diagnose config issues.
```

## Causa raíz
- El config principal del serve (host) tenía `model.provider: custom:nan-builders` — alias heredado.
- El perfil (ej. `profiles/ragnarcho/config.yaml`) ya usaba `provider: NaN-Builders` (correcto).
- Hermes serve v0.20.4 ya no resuelve el alias `custom:nan-builders`.

## Fix validado (20/08/2026)
1. Backup del config: `cp config.yaml config.yaml.bak-<fecha>`.
2. Reemplazar la línea: `sed -i "s/custom:nan-builders/NaN-Builders/g" config.yaml`.
3. Reiniciar el serve: `systemctl restart hermes-serve` (bajo systemd en el host; ~20s de caída).
4. Verificar: `systemctl is-active hermes-serve` + `netstat -tlnp | grep <port>` (serve escucha en 9112) + `grep "provider:" config.yaml | head -1` → `NaN-Builders`.

## Pitfalls asociados
- El `.env` del perfil ya no lee `LLM_MODEL` (línea de referencia únicamente) — el cambio va en `config.yaml`.
- Después del reinicio, el Desktop puede cachear el provider viejo: cerrar app completa (bandeja → Salir) y relanzar.
- `hermes gateway status` "running" no garantiza que la API HTTP escuche; verificar puertos con `ss -tlnp`.
- `hermes gateway status --verbose` no existe — no inventar flags.

## Comandos útiles de diagnóstico
```bash
hermes config get model.provider
hermes model
hermes gateway status
ss -tlnp | grep -E '9112|8642|8645'
grep "^  provider:" <config-dir>/config.yaml | head -1
```
