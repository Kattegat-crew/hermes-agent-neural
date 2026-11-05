#!/usr/bin/env python3
"""Autotest determinista de la skill memory-compaction (sin red, sin tocar el store real).

Ejecuta fixtures en un HERMES_HOME temporal y comprueba el contrato completo:
inventario -> gate (falla si falta destino) -> apply -> archivo verbatim -> recall ->
protección contra planes obsoletos -> tope de ocupación.

Uso: python3 selftest_memory_compaction.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import memlib as M  # noqa: E402

PY = sys.executable
FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def run(args: list[str], env_home: Path, expect: int | None = 0) -> subprocess.CompletedProcess:
    proc = subprocess.run([PY, *args], capture_output=True, text=True,
                          env={**os.environ, "HERMES_HOME": str(env_home)})
    if expect is not None and proc.returncode != expect:
        print(f"  exit={proc.returncode} (esperado {expect})\n  stdout={proc.stdout[-800:]}\n  stderr={proc.stderr[-1200:]}")
    return proc


ENTRIES = [
    "Regla dura de gasto: nunca ejecutar una generación paga (fal, monid, elevenlabs) sin firma explícita de Plon; el gate vive en spend_gate.py y se verifica antes de cada llamada.",
    "Cliente Golden Game: NIT 830.115.955-4, contrato Coljuegos hasta 2028, 7 sedes, dominio goldengame.com.co, personaje GOLDIE, paleta #DDC316/#AB0F15. Reporte mensual en Sheet 1My1fr2fahAWUpcWQuJhgSGCvm69QktFvmYxIad4vfrI.",
    "Cliente Golden Game (duplicado): NIT 830.115.955-4, contrato Coljuegos hasta 2028, 7 sedes en Cundinamarca, dominio goldengame.com.co, personaje GOLDIE, paleta dorada y roja.",
    "El worker de reels corre como reel-worker.service en el puerto 8090 de DEV con JWT; el render usa CHROMIUM_BIN=/opt/chromium y falla si falta el flag --no-sandbox en el contenedor.",
    "Pendiente 03-nov: revisar si el job b0f1a7318c5b del NCL-DIARIO quedó en verde tras el scp a PROD.",
    "El repo marketing-campaign-generator vive en /opt/marketing-campaign-generator y sus commits requieren el PAT del CLI gh con HOME=/opt/hermes-agent-data/home antes de hacer push.",
]

PLAN_TMPL = {
    "schema": "memory-compaction/plan@1",
    "profile": "default",
    "target": "memory",
    "entries": [],
}


def build_home(root: Path, limit: int = 200000) -> tuple[Path, Path, Path]:
    home = root / "home"
    (home / "memories").mkdir(parents=True)
    (home / "config.yaml").write_text(
        f"memory:\n  memory_enabled: true\n  memory_char_limit: {limit}\n  user_char_limit: 8000\n"
        "  on_demand: true\n  index_char_limit: 0\n", encoding="utf-8")
    store = home / "memories" / "MEMORY.md"
    store.write_text(M.join_entries(ENTRIES), encoding="utf-8")
    brain = root / "brain"
    (brain / "entities").mkdir(parents=True)
    (brain / "ops").mkdir(parents=True)
    brain_note = brain / "entities" / "cliente-golden-game.md"
    brain_note.write_text(
        "---\nid: cliente-golden-game\ntype: cliente\n---\n\n"
        "NIT 830.115.955-4 · Coljuegos 2028 · 7 sedes · goldengame.com.co · GOLDIE · #DDC316 #AB0F15 · "
        "Sheet 1My1fr2fahAWUpcWQuJhgSGCvm69QktFvmYxIad4vfrI\n", encoding="utf-8")
    reel_note = brain / "ops" / "reel-worker.md"
    reel_note.write_text(
        "---\nid: reel-worker\ntype: arquitectura\n---\n\n"
        "reel-worker.service corre en el puerto 8090 de DEV; exige JWT, CHROMIUM_BIN=/opt/chromium y el flag "
        "--no-sandbox dentro del contenedor de render.\n", encoding="utf-8")
    return home, brain_note, reel_note


def make_plan(store_text: str, golden_dest: Path | None, reel_dest: Path | None = None) -> dict:
    entries = M.parse_entries(store_text)
    plan = dict(PLAN_TMPL, entries=[])
    for idx, entry in enumerate(entries, 1):
        item = {"idx": idx, "sha1": M.sha1(entry), "chars": len(entry),
                "summary": M.summarize(entry), "action": "keep", "destination": None,
                "merge_into": None, "reason": "fixture"}
        if idx == 2:
            item["action"] = "keep"
        elif idx == 3:
            item.update(action="merge", merge_into=2)
        elif idx == 4:
            item.update(action="move", destination={"kind": "brain",
                                                    "path": str(reel_dest) if reel_dest else "/ruta/inexistente.md"})
        elif idx in (5, 6):
            item["action"] = "archive"
        plan["entries"].append(item)
    return plan


def main() -> int:
    print("== T1 parseo/unión idempotente ==")
    text = M.join_entries(ENTRIES)
    check("round-trip exacto", M.parse_entries(text) == ENTRIES)
    check("delimitador del runtime", M.ENTRY_DELIMITER == "\n§\n")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        home, brain_note, reel_note = build_home(root)
        store = home / "memories" / "MEMORY.md"
        original = store.read_text(encoding="utf-8")
        archive_dir = root / "archivo"

        print("\n== T2 inventario (solo lectura) ==")
        inv_json = root / "inv.json"
        plan_path = root / "plan.json"
        proc = run([str(HERE / "memory_inventory.py"), "--home", str(home), "--profile", "default",
                    "--brain", str(root / "brain"),
                    "--json", str(inv_json), "--emit-plan", str(plan_path)], home)
        check("inventario exit 0", proc.returncode == 0)
        check("store intacto tras inventario", store.read_text(encoding="utf-8") == original)
        data = json.loads(inv_json.read_text(encoding="utf-8"))
        check("6 entradas detectadas", data["stats"]["entries"] == 6, str(data["stats"]["entries"]))
        check("plan esqueleto emitido", plan_path.is_file() and len(json.loads(plan_path.read_text())["entries"]) == 6)
        check("cada entrada trae propuesta válida",
              all(r["proposed"]["action"] in ("keep", "move", "merge", "archive", "discard") for r in data["entries"]))
        check("duplicado detectado", bool(data["entries"][2]["duplicates"]))

        print("\n== T3 gate: destino inexistente bloquea (RED) ==")
        bad = make_plan(original, None)
        bad_path = root / "plan-malo.json"
        bad_path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        proc = run([str(HERE / "memory_apply.py"), "--plan", str(bad_path), "--home", str(home),
                    "--archive-dir", str(archive_dir)], home, expect=2)
        check("bloqueado con exit 2", proc.returncode == 2)
        check("mensaje nombra la entrada", "#4" in proc.stderr, proc.stderr[-300:])
        check("store intacto tras bloqueo", store.read_text(encoding="utf-8") == original)
        check("no se creó archivo con plan inválido", not archive_dir.exists() or not list(archive_dir.glob("*.jsonl")))

        print("\n== T4 apply con plan válido (GREEN) ==")
        good = make_plan(original, brain_note, reel_note)
        good_path = root / "plan-bueno.json"
        good_path.write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
        proc = run([str(HERE / "memory_apply.py"), "--plan", str(good_path), "--home", str(home),
                    "--archive-dir", str(archive_dir)], home)
        check("apply exit 0", proc.returncode == 0, proc.stderr[-500:])
        new_text = store.read_text(encoding="utf-8")
        new_entries = M.parse_entries(new_text)
        check("quedan keep + puntero", len(new_entries) == 3, f"{len(new_entries)} entradas")
        check("entradas keep byte-idénticas", new_entries[0] == ENTRIES[0] and new_entries[1] == ENTRIES[1])
        check("puntero de recuperación presente", "mem_recall.py" in new_entries[-1] and "verbatim" in new_entries[-1])
        check("store más pequeño", len(new_text) < len(original))
        jsonl = sorted(archive_dir.glob("*.jsonl"))
        check("archivo JSONL creado", len(jsonl) == 1)
        rows = [json.loads(l) for l in jsonl[0].read_text(encoding="utf-8").splitlines() if l.strip()]
        check("4 entradas retiradas archivadas", len(rows) == 4, f"{len(rows)}")
        check("archivo verbatim byte a byte", all(r["text"] == ENTRIES[r["idx"] - 1] for r in rows))
        check("destino registrado en archivo", any(r["destination"] for r in rows))
        backups = list((archive_dir / "backups").rglob("MEMORY.md"))
        check("backup del store original", bool(backups) and backups[0].read_text(encoding="utf-8") == original)
        check("recibo emitido", bool(list(archive_dir.glob("recibo-*.json"))))

        print("\n== T5 recall sobre el archivo verbatim ==")
        proc = run([str(HERE / "mem_recall.py"), "FZY552" if "FZY552" in original else "reel-worker", "--only-archive",
                    "--archive-dir", str(archive_dir), "--json"], home)
        check("recall exit 0", proc.returncode == 0, proc.stderr[-300:])
        hits = json.loads(proc.stdout)["hits"] if proc.stdout.strip() else []
        check("recall encuentra la entrada retirada", bool(hits) and hits[0]["kind"] == "archivo-memoria",
              str(hits[:1]))
        proc = run([str(HERE / "mem_recall.py"), "zzzz-no-existe-1234", "--only-archive",
                    "--archive-dir", str(archive_dir)], home, expect=1)
        check("recall sin resultados devuelve 1", proc.returncode == 1)

        print("\n== T6 plan obsoleto rechazado ==")
        proc = run([str(HERE / "memory_apply.py"), "--plan", str(good_path), "--home", str(home),
                    "--archive-dir", str(archive_dir)], home, expect=2)
        check("re-apply bloqueado por sha1", proc.returncode == 2)
        check("store no se degrada", store.read_text(encoding="utf-8") == new_text)

        print("\n== T7 tope de ocupación ==")
        home2, brain2, reel2 = build_home(root / "c2", limit=2500)
        store2 = home2 / "memories" / "MEMORY.md"
        plan2 = make_plan(store2.read_text(encoding="utf-8"), brain2, reel2)
        plan2_path = root / "plan2.json"
        plan2_path.write_text(json.dumps(plan2, ensure_ascii=False), encoding="utf-8")
        proc = run([str(HERE / "memory_apply.py"), "--plan", str(plan2_path), "--home", str(home2),
                    "--archive-dir", str(root / "archivo2"), "--max-fill", "0.05"], home2, expect=2)
        check("bloqueado por max-fill", proc.returncode == 2 and "tope" in proc.stderr)

    print(f"\n{'TODO OK' if not FAILS else 'FALLOS: ' + ', '.join(FAILS)}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())
