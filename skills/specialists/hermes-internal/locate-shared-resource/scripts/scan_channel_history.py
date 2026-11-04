#!/usr/bin/env python3
"""Scan Hermes state.db channel sessions for a keyword and print hits.

Usage:
  python3 scan_channel_history.py "<keyword>" [channel_id_fragment]
Example:
  python3 scan_channel_history.py "encuesta" 1003572354527   # Repos Git
  python3 scan_channel_history.py "chucho"                    # all channels, match sessions too
"""
import sqlite3, sys, glob, json, re

DB = "/opt/data/state.db"
KEY = sys.argv[1] if len(sys.argv) > 1 else ""
CHAN_FRAG = sys.argv[2] if len(sys.argv) > 2 else None

# Telegram group channel IDs
CHANNELS = {
    "1003820724234": "Links de X",
    "1003572354527": "Repos Git",
    "1003869738224": "TikToks",
}

def main():
    if not KEY:
        print("Pass a keyword to search.")
        return

    # Locate DB (works from container or host path)
    cands = [DB, "/root/hermes-agent-legacy-docker/data/state.db"]
    db = next((c for c in cands if glob.has_magic(c) or _exists(c)), None)
    if not db:
        print("state.db not found.")
        return
    con = sqlite3.connect("/opt/data/state.db")
    cur = con.cursor()

    channels = CHANNELS if not CHAN_FRAG else {CHAN_FRAG: CHANNELS.get(CHAN_FRAG, CHAN_FRAG)}
    print(f"=== searching '{KEY}' ===")
    for cid, cname in channels.items():
        sids = [r[0] for r in cur.execute(
            "SELECT id FROM sessions WHERE chat_id LIKE ?", (f"%{cid}%",))]
        if not sids:
            continue
        ph = ",".join("?" for _ in sids)
        rows = cur.execute(
            f"""SELECT m.session_id, m.role, m.timestamp, substr(m.content,1,500)
                FROM messages m WHERE m.session_id IN ({ph})
                AND m.content LIKE ? ORDER BY m.id LIMIT 30""",
            [f"%{KEY}%"] + sids).fetchall()
        print(f"\n--- {cname} ({cid}): {len(rows)} hits ---")
        for sid, role, ts, content in rows:
            print(f"  [{sid[:8]}|{role}|{ts}] {str(content).replace(chr(10),' ')[:400]}")

    # session titles too
    print(f"\n=== SESSION TITLES matching '{KEY}' ===")
    for r in cur.execute(
        "SELECT id, title, chat_id, last_activity_at FROM sessions WHERE title LIKE ?", (f"%{KEY}%",)).fetchall():
        print(f"  [{r[0]}] title='{r[1]}' chat={r[2]} last={r[3]}")

    con.close()

def _exists(p):
    try:
        import os
        return os.path.exists(p)
    except Exception:
        return False

if __name__ == "__main__":
    main()