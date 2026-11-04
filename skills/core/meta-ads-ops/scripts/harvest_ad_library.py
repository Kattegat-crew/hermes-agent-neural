# Cuerpo listo para browser_exec: cosecha Meta Ad Library (scroll + parse + dedupe + ranking).
# Requiere pestaña YA NAVEGADA a la URL de la libreria (abrir con new_tab en un paso
# previo, MISMA sesion/default que este codigo).
import re, json, time
from collections import Counter

chunks = []
js("window.scrollTo(0,0)"); time.sleep(1)
for i in range(10):
    chunks.append(js("document.body.innerText"))
    js("window.scrollBy(0, 1600)")
    time.sleep(1.4)
txt = "\n".join(chunks)
blocks = re.split(r"Activo\s*\n", txt)
ads = {}
for b in blocks:
    m_id = re.search(r"Identificador de la biblioteca:\s*(\d+)", b)
    m_date = re.search(r"En circulación desde el ([^\n]+)", b)
    m_adv = re.search(r"\n([^\n]{2,60})\nPublicidad\n", b)
    if not (m_id and m_adv):
        continue
    lib = m_id.group(1)
    if lib in ads:  # primera aparicion gana (mas completo al inicio del bloque)
        continue
    after = b.split("Publicidad", 1)[1] if "Publicidad" in b else ""
    head = re.split(r"(?:FB\.COM|FACEBOOK\.COM|WWW\.|HTTPS?://|INSTAGRAM\.COM|[A-ZÁÉÍÓÚÑ]{4,}\.(?:COM|GO\.COM|US))", after, maxsplit=1)[0]
    ads[lib] = {
        "lib_id": lib,
        "advertiser": m_adv.group(1).strip(),
        "since": m_date.group(1).strip() if m_date else None,
        "copy_head": re.sub(r"\s+", " ", head)[:300].strip(),
    }

# dias_running (fechas ES) contra hoy
from datetime import datetime
MONTHS = {"ene":"01","feb":"02","mar":"03","abr":"04","may":"05","jun":"06","jul":"07","ago":"08","sep":"09","oct":"10","nov":"11","dic":"12"}
today = datetime.now()
for a in ads.values():
    s = a.get("since") or ""
    m = re.search(r"(\d{1,2})\s+(\w+)\.?\s+(\d{4})", s)
    if m and MONTHS.get(m.group(2)[:3].lower()):
        d = datetime(int(m.group(3)), int(MONTHS[m.group(2)[:3].lower()]), int(m.group(1)))
        a["days_running"] = max(0, (today - d).days)
    else:
        a["days_running"] = None

rows = sorted(ads.values(), key=lambda r: -(r["days_running"] or 0))
with open("ads_library.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print("UNICOS:", len(rows))
for name, n in Counter(r["advertiser"] for r in rows).most_common(15):
    print(f"  {n:>2}  {name}")
print("TOP LONGEVO:")
for r in rows[:8]:
    print(f"  {r['days_running'] or 0:>4}d  {r['advertiser'][:32]:<32} {r['copy_head'][:60]}")
