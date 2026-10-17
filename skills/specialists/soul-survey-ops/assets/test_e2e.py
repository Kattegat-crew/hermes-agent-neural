"""E2E simulado del plugin soul_survey v2 (sin WhatsApp real)."""
import asyncio, json, sys, time, shutil
from pathlib import Path

BASE = Path("/tmp/opencode/soul_survey")
PKG = Path("/tmp/opencode/soul_survey_testpkg/soul_survey")
PKG.mkdir(parents=True, exist_ok=True)
(PKG / "__init__.py").touch()
for f in ("questions.py", "survey_engine.py"):
    shutil.copyfile(BASE / f, PKG / f)
sys.path.insert(0, str(PKG.parent))
import soul_survey.survey_engine as se

TMP = Path("/tmp/opencode/soul_survey_test")
shutil.rmtree(TMP, ignore_errors=True)
se.CACHE_DIR = TMP / "cache"
se.PROFILES_DIR = TMP / "profiles"

class Src:
    def __init__(self):
        self.chat_id = "57300111222@s.whatsapp.net"
        self.chat_type = "dm"
        self.platform = "whatsapp"
        self.profile = "testprof"
class Ev:
    def __init__(self, text):
        self.text = text; self.source = Src(); self.user_id = None
class Res:
    def __init__(self): self.success = True
class Adapter:
    def __init__(self): self.sent = []; self.polls = []
    async def send(self, chat_id=None, content=None, **kw): self.sent.append(content)
    async def send_poll(self, chat_id=None, question=None, options=None, selectable_count=1, **kw):
        self.polls.append((question, options)); return Res()
class GW:
    def __init__(self): self.adapters = {"whatsapp": Adapter()}
    def _adapter_for_source(self, s): return self.adapters["whatsapp"]

ANSWERS = ["Sara", "Jefe", "A", "Ninguna", "A y B", "organizar la agenda"]
PROFILE = "testprof"

def soul_file():
    return se.PROFILES_DIR / PROFILE / "SOUL.md"

async def run(gw, text):
    ev = Ev(text)
    await se.handle_survey_message(ev, gw)
    return gw.adapters["whatsapp"]

async def main():
    ok = lambda name, cond: print(("PASS" if cond else "FAIL"), "-", name) or (_ for _ in ()).throw(AssertionError(name)) if not cond else print("PASS -", name)

    # (1) Crear desde cero
    gw = GW()
    await run(gw, "/soul")
    a = gw.adapters["whatsapp"]
    ok("bienvenida + Q1 enviada", len(a.sent) == 2 and "6 preguntas" in a.sent[0] and "Q1" in a.sent[1])
    for ans in ANSWERS:
        await run(gw, ans)
    a = gw.adapters["whatsapp"]
    last = a.sent[-1]
    ok("resumen 6/6 con IDs nuevos", "(6/6)" in last and "Aquí está el resumen de tu perfil" in last)
    st = se.load_state(f"{Src().chat_id}")
    ok("estado awaiting_confirmation", st and st["status"] == "awaiting_confirmation")

    # corrección: volver a Q3
    await run(gw, "corregir Q3")
    st = se.load_state(f"{Src().chat_id}")
    ok("jump a Q3", st["status"] == "in_progress" and st["current_step"] == 2)
    for ans in ["B", "Ninguna", "A y B", "organizar la agenda"]:
        await run(gw, ans)
    st = se.load_state(f"{Src().chat_id}")
    ok("re-summary tras corregir", st["status"] == "awaiting_confirmation")

    await run(gw, "confirmar")
    sf = soul_file()
    content = sf.read_text(encoding="utf-8")
    ok("SOUL creado", sf.exists())
    ok("marcador nuevo presente", se.SURVEY_SECTION_MARKER in content)
    ok("respuestas mapeadas", "**Nombre del asistente:** Sara" in content and "Trato a su persona:** Jefe" in content)
    ok("reglas duras dentro de sección", "Alcance Exclusivo" in content and ".env" in content)
    ok("estado limpio tras guardar", se.load_state(f"{Src().chat_id}") is None)

    # (2) Re-run sobre SOUL con contenido custom SIN marcador -> append, conserva custom
    custom = "# Instrucciones propias\n\nReglas del banco de pruebas."
    sf.write_text(custom, encoding="utf-8")
    gw2 = GW(); await run(gw2, "perfilame")
    for ans in ANSWERS: await run(gw2, ans)
    await run(gw2, "sí")
    c2 = sf.read_text(encoding="utf-8")
    ok("custom conservado al fusionar", c2.startswith(custom))
    ok("sección agregada una vez", c2.count(se.SURVEY_SECTION_MARKER) == 1)

    # (3) Re-run con marcador VIEJO -> migración in-place al nuevo
    legacy_section = "## 📋 Encuesta /soul — Perfil Operativo (6 bloques)\n\n### vieja info\n- **Viejo:** dato caducado"
    sf.write_text(custom + "\n\n" + legacy_section, encoding="utf-8")
    gw3 = GW(); await run(gw3, "/soul")
    for ans in ANSWERS: await run(gw3, ans)
    await run(gw3, "confirmar")
    c3 = sf.read_text(encoding="utf-8")
    ok("marcador viejo migrado (no queda)", legacy_section.splitlines()[0] not in c3)
    ok("custom intacto tras migración", c3.startswith(custom))
    ok("sección nueva única", c3.count(se.SURVEY_SECTION_MARKER) == 1)
    ok("info nueva incluida", "organizar la agenda" in c3)

    # (4) texto vacío NO avanza
    gw4 = GW(); await run(gw4, "/soul"); await run(gw4, ANSWERS[0])
    n_polls_antes = len(gw4.adapters["whatsapp"].polls)
    await run(gw4, "")
    st = se.load_state(f"{Src().chat_id}")
    ok("vacío no avanza", st["current_step"] == 1)

    # (5) TTL expira estado (escribir timestamp viejo directo al archivo)
    key = f"{Src().chat_id}"
    spath = se.get_state_file(key)
    data = json.loads(spath.read_text(encoding="utf-8"))
    data["updated_at"] = time.time() - 3600
    spath.write_text(json.dumps(data), encoding="utf-8")
    ok("TTL expira", se.load_state(key) is None)

    print("\nTODO OK ✔")

asyncio.run(main())
