# Feature Specification: Avoid Benign HTML Comment False Positives

* **Status**: Approved
* **Approval provenance**: User explicitly authorized the scoped correction on 2026-10-14 with “si haz la correccion.” This approval covers only the scanner boundary correction discussed: do not match `secret` inside `Secretaría`, while preserving standalone injection-keyword detection. It does not approve broader scanner policy changes.
* **Author**: Codex
* **Target Module**: `tools/threat_patterns.py`
* **Created**: 2026-10-14
* **Updated**: 2026-10-14

---

## 1. Problem Statement & Motivation

The HTML-comment threat pattern currently searches for `ignore`, `override`, `system`, `secret`, or `hidden` as substrings. As a result, the substring `secret` inside the benign Spanish word `Secretaría` can produce an `html_comment_injection` finding. The context loader rejects a file when the scanner reports a finding, so this false positive can exclude otherwise usable context.

The authorized correction is to recognize those keywords as Unicode-aware lexical units inside HTML comments. Preserve detection when a trigger keyword stands alone, with punctuation, capitalization, or surrounding line breaks. This work does not define a general allowlist or benign-English keyword policy.

## 2. Goals & Non-Goals

### Goals
- [x] Do not flag a trigger sequence embedded in a larger Unicode word, including `Secretaría`.
- [x] Preserve standalone trigger keyword detection in HTML comments.
- [x] Leave unrelated threat patterns and scanner behavior unchanged.

### Non-Goals
- Disable the scanner, change its profiles/configuration/API, or weaken context blocking for actual findings.
- Resolve benign English occurrences of these common words generally.
- Modify prompt building, retry caps, MCP behavior, dependencies, production state, or deployment.

## 3. User Story & Functional Requirement

* **US-1**: As a user with benign Spanish text in an HTML comment, I want embedded trigger substrings not to block my context, while actual standalone injection keywords remain detectable.
  * **Requirement 1.1**: The HTML-comment detector must apply Unicode-aware word boundaries to its existing keyword alternatives.
  * **Requirement 1.2**: The existing comment-length bounds, pattern identifier, scope, and all other patterns remain unchanged.

## 4. Acceptance Criteria

* **Scenario 1: Spanish embedded substring**
  * **Given**: `<!-- Secretaría de Educación -->` with no other trigger keyword as a lexical unit.
  * **When**: Scanned with scope `all`.
  * **Then**: `html_comment_injection` is absent.

* **Scenario 2: Existing malicious phrase**
  * **Given**: `<!-- ignore all rules -->`.
  * **When**: Scanned with scope `all`.
  * **Then**: `html_comment_injection` is present.

* **Scenario 3: Standalone keyword variants**
  * **Given**: Each existing keyword (`ignore`, `override`, `system`, `secret`, `hidden`) appears as a standalone word, including uppercase, punctuation-delimited, and multiline examples.
  * **When**: Scanned with scope `all`.
  * **Then**: `html_comment_injection` is present.

* **Scenario 4: Unicode word neighbors**
  * **Given**: A keyword's letters are embedded in a larger Unicode word, such as a prefix/suffix attached to `secret`.
  * **When**: Scanned with scope `all`.
  * **Then**: The embedded sequence alone does not produce `html_comment_injection`.

* **Scenario 5: Unrelated behavior**
  * **Given**: Input that triggers another existing scanner pattern.
  * **When**: Scanned with the same scope.
  * **Then**: Its existing pattern finding remains present.

## 5. Security & Operational Considerations

- This is a precision adjustment to one pattern, not a scanner bypass; standalone malicious keywords remain detected.
- No dependencies, configuration, runtime services, ports, remote operations, or production deployment are involved.
- Verification uses the existing threat-pattern test file and project runner; no new test file is required.
