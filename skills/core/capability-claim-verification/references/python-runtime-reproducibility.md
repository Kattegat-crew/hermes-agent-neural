# Runtime reproducible para un servicio/pipeline en Python

Caso trabajado: 11-sep-2026, repo `marketing-campaign-generator`. El servicio (`reel-worker.service`, systemd)
corría `.venv/bin/python`, el operador probaba con `python3`, los crons con el `python3` del contenedor: tres
intérpretes y **tres juegos de dependencias distintos**. Síntoma: «el motor muere a mitad de camino» (el
refiner caía a ffmpeg por falta de PIL; el TTS fallaba por falta de edge_tts en el otro intérprete).

## 1. Diagnóstico: venv real, incompleto o inexistente

```bash
cat .venv/pyvenv.cfg                      # ¿es un venv de verdad? (pyvenv.cfg = sí)
readlink -f .venv/bin/python              # NORMAL: apunta al intérprete base
ls requirements*.txt pyproject.toml setup.py 2>/dev/null   # ¿están declaradas las deps?
for py in python3 .venv/bin/python; do    # matriz de imports por intérprete
  echo "--- $py"; $py -c "import PIL, edge_tts, docx, openpyxl, googleapiclient, numpy, scipy, requests" || true
done
```

**Trampa de diagnóstico (la sufrí):** que `bin/python` sea un symlink al intérprete del sistema **no** significa
que el venv sea falso. Un venv sano se ve exactamente así. La prueba es `pyvenv.cfg` + los imports.
Sin `requirements.txt` no hay forma de saber qué falta: mide la superficie real antes de escribir nada.

## 2. Medir la superficie real de dependencias (AST, sin red)

Recorre los `.py` del repo, recolecta `Import`/`ImportFrom` de nivel 0, resta stdlib (`sys.stdlib_module_names`)
y los módulos locales (por `Path(...).stem`). En el caso real salieron **10 módulos** — mucho menos de lo que
sugería el tamaño del repo — y uno (`fal_client`) estaba instalado sin que nadie lo importara.

Módulos locales con nombre genérico (`output_layout.py`, `spend_gate.py`) hay que excluirlos a mano o aparecerán
como deps fantasma.

## 3. `requirements.txt` fijado

Fija las versiones **que hoy funcionan** en el host; subir de versión debe ser un cambio deliberado. Incluye
`pytest` (la suite se corre desde el venv del repo: el contenedor puede no tenerlo). Documenta en un comentario
de cabecera de dónde salió la lista.

## 4. `scripts/bootstrap.sh` — el contrato

1. **Detecta venv falso/dir vacío** (`[ -e .venv ] && [ ! -f .venv/pyvenv.cfg ]`) y lo **conserva** como
   `.venv.fake-bak-<timestamp>` en vez de borrarlo.
2. Crea el venv real si falta (`python3 -m venv .venv`).
3. `pip install -r requirements.txt`.
4. **Verifica** la lista de imports declarada (bucle, no un solo import) y **falla con exit ≠ 0** si falta algo.
5. **Verifica binarios de sistema** — el pipeline suele depender de más que Python: `ffmpeg`/`ffprobe` (mix,
   concat, refiner) y el navegador headless (drafts/capturas). Que falten no debe descubrirse a mitad de un job.
6. **Modo `--check`**: no instala, solo verifica (para usar en `ExecStartPre` o en CI).
7. Imprime el intérprete resultante y recuerda que el unit systemd ya apunta a `.venv/bin/python`.

Lanzarlo como root deja el venv `root:root` → `chown -R <user>:<gid> .venv requirements.txt scripts/bootstrap.sh`
(el servicio corre con otro uid y necesita escribir/leer su propio venv).

## 5. Efectos colaterales esperados (y cómo tratarlos)

- Un default que cambia (p. ej. dry-run por defecto) **rompe tests existentes**: actualiza los asserts al
  contrato nuevo y añade el caso simétrico (`generate_audio:false` sí pasa el flag), no los borres.
- Un gate nuevo en un cliente de red **rompe los tests de ese cliente**: ábrelo con un fixture `autouse` que
  neutralice `require_gate`, y deja el bloqueo real probado en su propio archivo de test. Así el test dice
  explícitamente qué está neutralizando.
- `find . -name __pycache__ -exec rm -rf {} +` (excluyendo venvs) antes de medir: los `.pyc` conservan la ruta
  de compilación y ensucian tracebacks y conteos.

## 6. Evidencia de cierre

```bash
.venv/bin/python -c "import <todos los módulos>"; bash scripts/bootstrap.sh --check
.venv/bin/python -m pytest tests/ -q      # con el intérprete DEL SERVICIO, no con python3
```

Correr la suite con el venv (no con `python3`) es la única forma de probar lo que el servicio ejecuta de verdad.
