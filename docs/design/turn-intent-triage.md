# Turn Intent Triage & Tool Decoupling Guardrails

## Overview

Hermes Agent employs a multi-tier Turn Intent Triage pipeline to differentiate between purely conversational messages (greetings, acknowledgements, latency checks) and operational messages requiring tool execution.

On confirmed conversational turns, the gateway decouples active tool schemas (`tools_for_api = []`), conserving ~13,600 prompt tokens and eliminating 8–10 seconds of LLM inference overhead per turn. On operational turns, tool schemas remain fully coupled to prevent model panic, synthetic tool hallucinations, or DeepSeek Markdown (DSML) format leaks.

---

## Architectural Invariants

1. **Fail-Open Policy**: Any ambiguous, compound, multi-turn, or unclassifiable prompt defaults strictly to `action` (tools remain coupled). Tools are decoupled *only* when high confidence of purely conversational intent is established.
2. **Deterministic Context Overrides**: Explicit technical indicators (URLs, local filesystem paths, attached files, multipart user content) bypass semantic evaluation and immediately evaluate as `action`.
3. **Zero External Latency**: Intent classification runs entirely in-process on CPU with no network requests, third-party API dependencies, or GPU requirements.
4. **Execution Ceiling**: Turn classification overhead is bounded to $<20\text{ ms}$ on standard x86_64/ARM64 CPUs.

---

## Pipeline Architecture

Intent evaluation proceeds sequentially through three distinct tiers:

```
[User Message]
      │
      ▼
┌────────────────────────────────────────┐
│ Tier 0: Fast-Path Deterministic Checks │
│ (URLs, Paths, Pings, Future Intent)    │
└──────────────────┬─────────────────────┘
                   │ Ambiguous
                   ▼
┌────────────────────────────────────────┐
│ Tier 1: Local Semantic ONNX Triage     │
│ (paraphrase-multilingual-MiniLM-L12-v2 │
│  + Calibrated Linear Probe)            │
└──────────────────┬─────────────────────┘
                   │ Model Unavailable / Error
                   ▼
┌────────────────────────────────────────┐
│ Tier 2: Heuristic Fallback             │
│ (RegEx Greeting/Action Directives)     │
└────────────────────────────────────────┘
```

### Tier 0: Deterministic Fast-Path

Evaluates high-priority indicators via compiled regular expressions before invoking semantic models:

- **System Wrappers**: Strips synthetic `<system-metadata>` headers before evaluating raw user intent.
- **Technical Artifacts**: File paths (`/path/to/file`, `./relative/path`), file extensions (`.py`, `.json`, `.yaml`), and URLs (`http://`, `https://`) resolve immediately to `action`.
- **Latency & Ping Tests**: Explicit ping/speed queries (*"test de velocidad"*, *"ping"*, *"latencia"*) resolve immediately to `conversational`.
- **Deferred Future Intent**: Statements of future intention without current imperatives (*"mañana vamos a programar"*, *"luego revisamos"*) resolve to `conversational`.

### Tier 1: Local Semantic ONNX Triage

Implemented in `agent.semantic_triage.SemanticIntentClassifier`.

1. **Text Embedding**:
   - Engine: `fastembed` with ONNX Runtime.
   - Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
   - Vector Dimensionality: 384 dimensions.
   - Language Support: 50+ languages natively supported (including Spanish, English, Portuguese, French, etc.).
   - Model Cache: Stored locally in user cache (`~/.cache/huggingface/hub/` or container volume).

2. **Calibrated Linear Probe**:
   - Model weights: Serialized in `agent/semantic_intent_weights.json` (384 coefficients + scalar intercept).
   - Scoring function:
     $$\text{score} = b + \sum_{i=1}^{384} w_i v_i$$
     $$P(\text{action}) = \frac{1}{1 + e^{-\text{score}}}$$
   - Pure Python dot-product execution time: $<5\ \mu\text{s}$.
   - Classification Threshold:
     $$P(\text{action}) \ge 0.50 \implies \text{action}$$
     $$P(\text{action}) < 0.50 \implies \text{conversational}$$

3. **Compound Utterance Disambiguation**:
   Unlike keyword-matching filters, the linear probe separates greetings from actionable intent even in mixed sentences (e.g., *"Buenas tardes, revisa los logs por favor"* $\to$ `action`).

### Tier 2: Heuristic Fallback

If the ONNX runtime or model weights cannot be loaded (lean environment, missing dependencies):
- Evaluates imperative action verbs (`_ACTION_DIRECTIVES`). If present $\to$ `action`.
- Evaluates pure greetings and conversational acknowledgements (`_GREETING_PATTERN`, `_ACK_WORDS`). If present without action verbs $\to$ `conversational`.
- Evaluates casual inquiries (`_CASUAL_INQUIRY_PATTERN`). If matched $\to$ `conversational`.
- Default: Returns `action` (Fail-Open).

---

## Tool Decoupling Invariants

Tool decoupling (`should_decouple_tools_for_turn`) applies only when all of the following conditions hold:

1. Turn call count $\le 1$ (subsequent turns in multi-tool executions always keep tools enabled).
2. The agent is neither a cron job (`is_cron == False`) nor an autonomous subagent (`_delegate_depth == 0`).
3. The previous message was not generated by a tool (`role not in ('tool', 'function')`) and does not contain pending tool calls.
4. The user message contains no non-text multipart blocks (e.g. image or document attachments).
5. `classify_turn_intent` resolves strictly to `conversational`.

---

## Performance Profile

| Component | Latency | Memory Footprint |
| :--- | :--- | :--- |
| Tier 0 Regex Checks | $<0.1\text{ ms}$ | Negligible |
| Tier 1 ONNX CPU Embedding | $15\text{–}20\text{ ms}$ | ~80 MB RAM (Shared ONNX session) |
| Linear Probe Dot-Product | $<0.005\text{ ms}$ | $<10\text{ KB}$ (JSON weights) |
| Total In-Flight Overhead | $<25\text{ ms}$ | Peak RSS $\sim 80\text{ MB}$ |
