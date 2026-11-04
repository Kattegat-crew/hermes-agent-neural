# Unificar DBs de Engram Divergentes (verificado 16/08/2026)

## Síntoma

Después de una actualización mayor de Hermes o de un filesystem drift,
puede haber DOS bases `engram.db` (ej: `/opt/data/.engram/engram.db` de 252K
y `/opt/data/home/.engram/engram.db` de 1.5M + WAL de 4.2M). La memoria queda
PARTIDA: algunos agentes escriben a una, otros a la otra.

## Procedimiento verificado

```bash
# 1. IDENTIFICAR cuál es la más completa (normalmente la más grande, con WAL)
ls -lh /opt/data/.engram/engram.db /opt/data/home/.engram/engram.db

# 2. Checkpoint WAL ANTES de copiar (si no hay sqlite3 CLI en el contenedor,
#    usar Python — el CLI puede no existir)
python3 -c "
import sqlite3
conn = sqlite3.connect('/opt/data/home/.engram/engram.db')
conn.execute('PRAGMA wal_checkpoint(FULL);')
conn.close()
print('WAL checkpoint completo')
"

# 3. Copiar la más completa a la ubicación canónica
cp /opt/data/home/.engram/engram.db /opt/data/.engram/engram.db
chmod 644 /opt/data/.engram/engram.db

# 4. VERIFICAR integridad + conteo ANTES de borrar el duplicado
python3 -c "
import sqlite3
conn = sqlite3.connect('/opt/data/.engram/engram.db')
cur = conn.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')
print('Tablas:', [r[0] for r in cur.fetchall()])
try:
    print('Observaciones:', conn.execute('SELECT COUNT(*) FROM observations').fetchone()[0])
except Exception:
    pass
conn.close()
"

# 5. Eliminar el duplicado SOLO después de la verificación
rm -rf /opt/data/home/.engram/
```

## Lecciones

- **El checkpoint WAL es obligatorio**: copiar la DB sin checkpoint pierde los
  datos que siguen vivos en el archivo `-wal`. Usar `PRAGMA wal_checkpoint(FULL)`.
- **`sqlite3` CLI puede NO existir dentro del contenedor Docker** (comando 127).
  El módulo `sqlite3` de Python siempre está disponible — usarlo como fallback.
- **Nunca borrar el duplicado sin verificar** tablas + COUNT de observaciones
  en la copia (en el caso real: 162 observaciones migradas).
- **Dos ubicaciones canónicas vistas en la práctica**: `/opt/data/.engram/`
  (config del proyecto) y `/opt/data/home/.engram/` (ENGRAM_DATA_DIR del env).
  Unificar hacia una sola y apuntar `ENGRAM_DATA_DIR` a ella en docker-compose.
- Después de unificar, correr `mcp__engram__mem_doctor` para confirmar
  4/4 checks OK (journal_mode=wal, sin lock contention).
