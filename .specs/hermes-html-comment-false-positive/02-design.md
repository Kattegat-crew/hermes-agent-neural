# Technical Design: Unicode-Aware HTML Comment Keyword Boundaries

* **Status**: Approved for the scoped correction
* **Approval provenance**: The user authorized “si haz la correccion” on 2026-10-14 for the narrow correction described in `01-spec.md`; no expanded policy or production action is approved.
* **Target**: `tools/threat_patterns.py` and `tests/tools/test_threat_patterns.py`

## Decision

Change only the HTML-comment keyword alternative in `_PATTERNS` to require Python regular-expression word boundaries around each existing trigger word. Python's default Unicode-aware `\b` boundary prevents a match within a larger Unicode word such as `Secretaría`, while retaining matches where punctuation, whitespace, or a line break separates the keyword from adjacent text.

Keep the current comment delimiters, 512-character body bounds, keyword set, pattern ID (`html_comment_injection`), and scope (`all`) unchanged. Use real `scan_for_threats()` calls in the existing test module; do not introduce mocks or alter the scanner API.

## Data Flow and Impact

`scan_for_threats(text, scope="all")` evaluates the bounded HTML-comment pattern. A positive result remains `html_comment_injection`; existing context-file loading continues to block any reported finding. The change affects only whether a keyword embedded inside a larger word counts as a match.

## Trade-offs and Edge Cases

- Unicode `\b` uses Python's Unicode word-character rules. Letters and digits are word characters; underscore is also a word character, so a trigger adjacent to underscore is not considered standalone. This is intentional lexical-boundary behavior.
- Case-insensitive matching, if applied by the shared scanner, remains unchanged; tests cover capitalization.
- The edit does not attempt to disambiguate every benign English use of a standalone keyword.
- Bounded quantifiers remain in place, so the existing input-size and regex-length constraints are preserved.

## Verification and Operations

- Add regression assertions first, run the focused suite to observe the expected failure, then make the minimal regex change and rerun.
- Run `HERMES_PYTHON=/usr/bin/python3 ./scripts/run_tests.sh tests/tools/test_threat_patterns.py` and `git diff --check`.
- No runtime, deployment, service restart, telemetry, dependency, or remote action is necessary.
