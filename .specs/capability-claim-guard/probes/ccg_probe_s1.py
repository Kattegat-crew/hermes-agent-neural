"""Independent reviewer probe: S1 prefilter (stream anchors) vs detector patterns."""
import sys

sys.path.insert(0, "/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard")

from agent.capability_claim_guard import (
    CapabilityEvidence,
    _STREAM_ANCHORS,
    _NEGATION_PATTERNS,
    scan_published_text,
    stream_gate,
    flush_stream_holdback,
)


class Sink:
    def __init__(self):
        self.parts = []

    def __call__(self, text):
        self.parts.append(text)

    @property
    def text(self):
        return "".join(self.parts)


class Agent:
    def __init__(self, ev):
        self._ccg_evidence = ev
        self._current_turn_id = "t1"
        self._streamed_assistant_text_parts = []
        self._ccg_hold_parts = []
        self._ccg_published_tail = ""
        self._ccg_tainted = None


BENIGN = "Revisé el repositorio y actualicé los dos archivos desactualizados. " * 6

CASES = [
    # (label, denial text, expected detector verdict kind)
    ("es-no-me-es-posible", "No me es posible enviar correos desde aquí.", "contradiction"),
    ("en-we-dont-have-tools", "We don't have any tools for that.", "contradiction"),
    ("es-no-puedo-enviar", "No puedo enviar mensajes en esta sesión.", "contradiction"),
    ("es-no-tengo", "No tengo herramientas de mensajería.", "contradiction"),
]

DIRECT = ("send_email", "send_message", "read_file")


def run_case(label, denial):
    ev = CapabilityEvidence(turn_id="t1", direct=frozenset(DIRECT), holdback_chars=200)
    final_kind = scan_published_text(ev, BENIGN + denial, surface="final").kind
    agent = Agent(ev)
    raw = BENIGN + denial
    for i in range(0, len(raw), 19):
        gated = stream_gate(agent, raw[i:i + 19])
        if gated:
            agent._streamed_assistant_text_parts.append(gated)
    tail = flush_stream_holdback(agent)
    published = "".join(agent._streamed_assistant_text_parts) + (tail or "")
    dumped = denial.strip() in published
    print(
        f"{label:34s} final={final_kind:22s} tainted={agent._ccg_tainted!s:6s} "
        f"denial_published_raw={dumped}"
    )
    return final_kind, agent._ccg_tainted, dumped


print("anchor coverage of each negation pattern (static):")
for pat in _NEGATION_PATTERNS:
    hits = [a for a in _STREAM_ANCHORS if pat.search("no me es posible x") and a in "no me es posible x"]
    # crude: does the pattern's own literal prefix appear in anchors?
print()

results = {}
for label, denial, _ in CASES:
    results[label] = run_case(label, denial)

print()
print("SUMMARY gaps (detector catches, S1 prefilter misses):")
for label, (kind, tainted, dumped) in results.items():
    if kind.startswith("contradiction") and tainted is None and dumped:
        print(f"  LEAK  {label}: detector={kind} but S1 published the raw denial")
