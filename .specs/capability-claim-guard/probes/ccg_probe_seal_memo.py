"""Reviewer probe 2: does the S3 seal survive a second text in the SAME turn?

``apply_llm_output_transform`` memoizes per turn_id. The CCG repair nudge re-runs the
model inside the SAME turn, so attempt #2 hits the memo branch and may bypass the seal.
"""
import sys

sys.path.insert(0, "/opt/hermes-agent-data/fleet/worktrees/hermes-agent/capability-claim-guard")

from agent.capability_claim_guard import CapabilityEvidence, scan_published_text
from agent.turn_finalizer import apply_llm_output_transform


class Agent:
    def __init__(self):
        self._ccg_evidence = CapabilityEvidence(
            turn_id="t1", direct=frozenset({"send_message", "send_email"}), holdback_chars=200
        )
        self.session_id = "s"
        self.model = "m"
        self.provider = "p"
        self.platform = "cli"
        self._llm_output_transform = None
        self._ccg_repairs = 0


DENIAL = "No tengo herramientas de mensajería, así que no puedo enviar el mensaje."

agent = Agent()
print("verdict on raw denial:", scan_published_text(agent._ccg_evidence, DENIAL, surface="final").kind)

out1, tr1, pre1 = apply_llm_output_transform(agent, DENIAL, turn_id="t1")
print("\nattempt 1 (cold):")
print("  transformed =", tr1)
print("  sealed?     =", out1 != DENIAL)
print("  tail        =", repr(out1[len(DENIAL):][:120]))

out2, tr2, pre2 = apply_llm_output_transform(agent, DENIAL, turn_id="t1")
print("\nattempt 2 (same turn_id, after a repair nudge):")
print("  transformed =", tr2)
print("  sealed?     =", out2 != DENIAL)
print("  published   =", repr(out2))

print("\nRESULT:", "PASS seal holds" if out2 != DENIAL else "DEFECT: attempt 2 publishes the raw denial")
