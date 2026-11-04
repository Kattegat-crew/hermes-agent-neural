"""Reviewer probe 3: candidate fix for the S1 anchor gap + bare English variant.

Usage: python .specs/capability-claim-guard/probes/ccg_probe_fix.py [repo_root]
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from agent import capability_claim_guard as ccg


class Sink:
    def __init__(self):
        self.parts = []

    def __call__(self, t):
        self.parts.append(t)

    @property
    def text(self):
        return "".join(self.parts)


class Agent:
    def __init__(self, ev):
        self._ccg_evidence = ev
        self._current_turn_id = "t1"
        self._ccg_hold_parts, self._ccg_published_tail, self._ccg_tainted = [], "", None
        self._ccg_repairs, self._ccg_repair_turn = 0, "t1"


BENIGN = "Revisé el repositorio y actualicé los dos archivos desactualizados. " * 6
DIRECT = ("send_email", "send_message", "read_file")
CASES = [
    ("es: no me es posible enviar correos", "No me es posible enviar correos desde aquí."),
    ("en: We don't have tools", "We don't have tools."),
    ("en: We do not have any tools", "We do not have any tools."),
]


def run(denial):
    ev = ccg.CapabilityEvidence(turn_id="t1", direct=frozenset(DIRECT), holdback_chars=200)
    agent = Agent(ev)
    raw = BENIGN + denial
    published = []
    for i in range(0, len(raw), 17):
        published.append(ccg.stream_gate(agent, raw[i:i + 17]))
    published.append(ccg.flush_stream_holdback(agent))
    text = "".join(published)
    detector = ccg.scan_published_text(ev, BENIGN + denial, surface="final").kind
    return detector, agent._ccg_tainted, denial.strip() in text


print("== CURRENT anchors ==")
for label, denial in CASES:
    d, t, dumped = run(denial)
    print(f"  {label:38s} detector={d:20s} tainted={t!s:6s} RAW_PUBLISHED={dumped}")

ccg._STREAM_ANCHORS = ccg._STREAM_ANCHORS + ("no me es posible", "we don't", "we do not")
print("\n== WITH proposed anchors (+ 'no me es posible', 'we don't', 'we do not') ==")
for label, denial in CASES:
    d, t, dumped = run(denial)
    print(f"  {label:38s} detector={d:20s} tainted={t!s:6s} RAW_PUBLISHED={dumped}")
