---
name: product-analytics
description: "Use when defining product KPIs, cohorts or metric dashboards"
tags: [product-analytics, kpis, cohorts, retention, aarrr, north-star, dashboards, metrics]
---

# Product Analytics

Define, track, and interpret product metrics across discovery, growth, and mature product stages.

## When To Use

Use this skill for:
- Metric framework selection (AARRR, North Star, HEART)
- KPI definition by product stage (pre-PMF, growth, mature)
- Dashboard design and metric hierarchy
- Cohort and retention analysis
- Feature adoption and funnel interpretation

## Workflow

1. Select metric framework
- AARRR for growth loops and funnel visibility
- North Star for cross-functional strategic alignment
- HEART for UX quality and user experience measurement

2. Define stage-appropriate KPIs
- Pre-PMF: activation, early retention, qualitative success
- Growth: acquisition efficiency, expansion, conversion velocity
- Mature: retention depth, revenue quality, operational efficiency

3. Design dashboard layers
- Executive layer: 5-7 directional metrics
- Product health layer: acquisition, activation, retention, engagement
- Feature layer: adoption, depth, repeat usage, outcome correlation

4. Run cohort + retention analysis
- Segment by signup cohort or feature exposure cohort
- Compare retention curves, not single-point snapshots
- Identify inflection points around onboarding and first value moment

5. Interpret and act
- Connect metric movement to product changes and release timeline
- Distinguish signal from noise using period-over-period context
- Propose one clear product action per major metric risk/opportunity

## KPI Guidance By Stage

### Pre-PMF
- Activation rate
- Week-1 retention
- Time-to-first-value
- Problem-solution fit interview score

### Growth
- Funnel conversion by stage
- Monthly retained users
- Feature adoption among new cohorts
- Expansion / upsell proxy metrics

### Mature
- Net revenue retention aligned product metrics
- Power-user share and depth of use
- Churn risk indicators by segment
- Reliability and support-deflection product metrics

## Dashboard Design Principles

- Show trends, not isolated point estimates.
- Keep one owner per KPI.
- Pair each KPI with target, threshold, and decision rule.
- Use cohort and segment filters by default.
- Prefer comparable time windows (weekly vs weekly, monthly vs monthly).

See:
- `references/metrics-frameworks.md`
- `references/dashboard-templates.md`

## Cohort Analysis Method

1. Define cohort anchor event (signup, activation, first purchase).
2. Define retained behavior (active day, key action, repeat session).
3. Build retention matrix by cohort week/month and age period.
4. Compare curve shape across cohorts.
5. Flag early drop points and investigate journey friction.

## Retention Curve Interpretation

- Sharp early drop, low plateau: onboarding mismatch or weak initial value.
- Moderate drop, stable plateau: healthy core audience with predictable churn.
- Flattening at low level: product used occasionally, revisit value metric.
- Improving newer cohorts: onboarding or positioning improvements are working.

## Anti-Patterns

| Anti-pattern | Fix |
|---|---|
| **Vanity metrics** — tracking pageviews or total signups without activation context | Always pair acquisition metrics with activation rate and retention |
| **Single-point retention** — reporting "30-day retention is 20%" | Compare retention curves across cohorts, not isolated snapshots |
| **Dashboard overload** — 30+ metrics on one screen | Executive layer: 5-7 metrics. Feature layer: per-feature only |
| **No decision rule** — tracking a KPI with no threshold or action plan | Every KPI needs: target, threshold, owner, and "if below X, then Y" |
| **Averaging across segments** — reporting blended metrics that hide segment differences | Always segment by cohort, plan tier, channel, or geography |
| **Ignoring seasonality** — comparing this week to last week without adjusting | Use period-over-period with same-period-last-year context |

## Tooling

### `scripts/metrics_calculator.py`

CLI utility for retention, cohort, and funnel analysis from CSV data. Supports text and JSON output.

```bash
# Retention analysis
python3 scripts/metrics_calculator.py retention events.csv
python3 scripts/metrics_calculator.py retention events.csv --format json

# Cohort matrix
python3 scripts/metrics_calculator.py cohort events.csv --cohort-grain month
python3 scripts/metrics_calculator.py cohort events.csv --cohort-grain week --format json

# Funnel conversion
python3 scripts/metrics_calculator.py funnel funnel.csv --stages visit,signup,activate,pay
python3 scripts/metrics_calculator.py funnel funnel.csv --stages visit,signup,activate,pay --format json
```

**CSV format for retention/cohort:**
```csv
user_id,cohort_date,activity_date
u001,2026-01-01,2026-01-01
u001,2026-01-01,2026-01-03
u002,2026-01-02,2026-01-02
```

**CSV format for funnel:**
```csv
user_id,stage
u001,visit
u001,signup
u001,activate
u002,visit
u002,signup
```

## Cross-References

- Related: `product-team/experiment-designer` — for A/B test planning after identifying metric opportunities
- Related: `product-team/product-manager-toolkit` — for RICE prioritization of metric-driven features
- Related: `product-team/product-discovery` — for assumption mapping when metrics reveal unknowns
- Related: `finance/saas-metrics-coach` — for SaaS-specific metrics (ARR, MRR, churn, LTV)


<!-- absorbido de software-development/cs-product-analyst (censo 2026-09-24) -->
## Purpose


The cs-product-analyst agent turns product questions into measurable answers. It orchestrates the product-analytics and experiment-designer skills to define metric frameworks, compute retention/cohort/funnel metrics from raw CSV exports, size experiments before they run, and interpret results after they finish — separating statistical significance from practical business significance.

Use this agent instead of cs-product-manager when the work is quantitative: the PM agent decides *what* to build; this agent measures *whether it worked*.

## Skill Integration


**Skill Locations:**
- `../../product-team/skills/product-analytics/` ([SKILL.md] ⚠️ FALTA: ../../product-team/skills/product-analytics/SKILL.md)
- `../../product-team/skills/experiment-designer/` ([SKILL.md] ⚠️ FALTA: ../../product-team/skills/experiment-designer/SKILL.md)

### Python Tools


1. **Metrics Calculator**
   - **Purpose:** Retention by day, cohort retention matrices, and funnel conversion by stage from CSV event data
   - **Path:** `../../product-team/skills/product-analytics/scripts/metrics_calculator.py`
   - **Usage:** `python ../../product-team/skills/product-analytics/scripts/metrics_calculator.py retention events.csv` (subcommands: `retention`, `cohort`, `funnel`)

2. **Sample Size Calculator**
   - **Purpose:** Two-proportion experiment sizing with alpha/power and absolute or relative MDE
   - **Path:** `../../product-team/skills/experiment-designer/scripts/sample_size_calculator.py`
   - **Usage:** `python ../../product-team/skills/experiment-designer/scripts/sample_size_calculator.py --baseline-rate 0.12 --mde 0.02 --mde-type absolute --daily-samples 800`

### Workflow 1: Metric Framework and KPI Definition


**Goal:** Define the decision metric, supporting metrics, and guardrails for a feature before any analysis runs.

**Steps:**
1. **Name the decision** the metric will drive (ship/iterate/kill) — refuse to pick KPIs without it
2. **Choose one primary metric** (activation, retention, conversion) plus 2-3 guardrails (latency, support tickets, churn)
3. **Specify the dashboard**: data source, granularity, owner, and review cadence

**Expected Output:** A one-page metric spec with primary KPI, guardrails, and dashboard layout.

### Workflow 2: Retention / Cohort / Funnel Analysis


**Goal:** Quantify how users actually behave from raw event exports.

**Steps:**
1. Export events to CSV (user_id, timestamp, event)
2. Run `metrics_calculator.py retention|cohort|funnel` on the export
3. Annotate the output: where the curve flattens, which cohort improved, which funnel stage leaks most

**Expected Output:** Retention curve / cohort matrix / funnel table with a written interpretation and one recommended action.

### Workflow 3: Experiment Design and Result Interpretation


**Goal:** Size a test before launch; judge the result after.

**Steps:**
1. State hypothesis and minimum detectable effect worth acting on
2. Run `sample_size_calculator.py` to get required n and runtime at current traffic
3. After the test, compare observed lift against the MDE; check guardrails; pair statistical significance with practical significance before recommending ship/iterate/kill

**Expected Output:** Pre-registered test plan, then a decision memo with effect size, confidence, guardrail status, and recommendation.

## Usage Notes


- Define decision metrics before analysis to avoid post-hoc bias.
- Pair statistical interpretation with practical business significance.
- Use guardrail metrics to prevent local optimization mistakes.

## Related Agents


- [cs-product-manager] ⚠️ FALTA: cs-product-manager.md - Prioritization and PRDs; hands measurement questions to this agent
- [cs-ux-researcher] ⚠️ FALTA: cs-ux-researcher.md - Qualitative evidence to explain the "why" behind metric movements

## References


- [Product Analytics Skill] ⚠️ FALTA: ../../product-team/skills/product-analytics/SKILL.md
- [Experiment Designer Skill] ⚠️ FALTA: ../../product-team/skills/experiment-designer/SKILL.md
