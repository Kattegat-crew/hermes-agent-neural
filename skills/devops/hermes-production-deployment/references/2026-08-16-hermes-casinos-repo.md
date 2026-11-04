# Hermes-Casinos Repo — Construcción y Trampas de GitHub (16/08/2026)

## Contexto

Se construyó el repositorio `Kattegat-crew/Hermes-casinos-` para versionar los perfiles Hermes de Golden Game y Lucky Club. El repo es PRIVADO y pertenece a la org `Kattegat-crew`.

## Estructura validada (20 archivos, 1,034 líneas, commit acc26b9)

```
Hermes-casinos-/
├── README.md                     # Descripción + tabla de perfiles
├── LICENSE                       # MIT
├── .gitignore                    # Secrets, .env, tokens, __pycache__
├── docs/ARCHITECTURE.md          # Diagrama multi-tenant + modelos + memoria
├── profiles/
│   ├── golden-game/
│   │   ├── config.yaml           # deepseek-v4-flash + qwen3.6 smart routing
│   │   ├── SOUL.md               # Asistente gerencial Golden Game (es-CO)
│   │   ├── AGENTS.md             # NIT 830.115.955-4, sedes, pipeline, contactos
│   │   ├── MEMORY.md             # Preferencias, proyectos, recordatorios
│   │   └── cron/                 # (reporte diario, recordatorios)
│   └── lucky-club/               # Misma estructura (Paradise Club)
├── templates/
│   ├── config.yaml               # Plantilla base con <CLIENTE> placeholder
│   └── SOUL.md                   # Plantilla con [NOMBRE]/[CARGO]/[EMPRESA]
├── scripts/
│   ├── onboard-agent.py          # Autoconfiguración interactiva (argparse)
│   └── validate-profile.sh       # Verifica config/SOUL/AGENTS/MEMORY existan
└── shared/cron-templates/
    ├── reporte-diario-leads.md   # 9AM, estructura de reporte
    ├── recordatorio-citas.md     # 24h antes
    └── followup-post-visita.md   # Día siguiente
```

## Trampas de GitHub privado (todas experimentadas 16/08)

1. **Nombre con guion final:** `Hermes-casinos-` (NO `Hermes-casinos`). `git ls-remote` da
   "Permission denied" sin aclarar que el nombre es incorrecto. **Verificar con API:**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" https://api.github.com/user/repos \
     | python3 -c "import sys,json; [print(r['full_name']) for r in json.load(sys.stdin)]"
   ```
2. **Deploy key aceptada ≠ acceso al repo:** `ssh -vT git@github.com` mostraba
   "Server accepts key" pero `git clone` fallaba → la key estaba registrada en
   otro repo o sin "Allow write access". No basta con generar la key y pedir
   que la agreguen; hay que verificar el push real.
3. **403 en push a org:** El commit local funciona, el push da
   "Write access to repository not granted" → el token/deploy key no tiene
   `Contents: Write` en el repo de la org.
4. **HERMES_WRITE_SAFE_ROOT=/opt/data:** `write_file`/`patch` rechazan
   escribir fuera de /opt/data (ej: `/tmp/repo/README.md` → "Write denied").
   Clonar el repo dentro de `/opt/data/` (ej: `/opt/data/hermes-casinos-repo/`).
5. **Sin credenciales por defecto en contenedor:** no hay `~/.ssh/` ni `gh` CLI.
   Para deploy key: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_github -N ""`,
   configurar `~/.ssh/config` con IdentityFile, y pedir al usuario que agregue
   la pública en Settings → Deploy keys con "Allow write access".

## Autenticación con PAT (funcionó)

```bash
git clone "https://x-access-token:${TOKEN}@github.com/Kattegat-crew/Hermes-casinos-.git"
git remote set-url origin "https://x-access-token:${TOKEN}@github.com/Kattegat-crew/Hermes-casinos-.git"
```
El PAT del usuario `Jemadiar1` listó el repo vía API pero no tenía push access
a la org (403). Solución pendiente: dar write access al token/key.

## Script de autoconfiguración (patrón reutilizable)

`onboard-agent.py` — CLI con argparse:
- `python3 onboard-agent.py golden-game --company "Golden Game" --user "Helmer Parra" --role "Gerente" --yes` (no interactivo)
- Sin `--yes` → pregunta interactiva: empresa, usuario, cargo, tono
- Genera config.yaml (reemplaza `<CLIENTE>`), SOUL.md (reemplaza placeholders), AGENTS.md y MEMORY.md mínimos si no existen
- Próximo paso documentado: completar AGENTS.md, agregar cronjobs, `hermes profile use <cliente>`
