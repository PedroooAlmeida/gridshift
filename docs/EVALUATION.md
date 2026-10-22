# Evaluation methodology

## Scheduling benchmark

200 seeded factories use three machines, eight jobs and 12 hours, with negative
prices, machine eligibility, known outages and power caps. Every eleventh seed
adds a known resource conflict. Development and heldout seed ranges are separate;
these are synthetic holdouts, not independently collected industrial data.

Each case records inputs, FCFS and price-aware greedy baselines, optimized schedule,
independent accounting/checker results, solver status, bound and elapsed time.
Baseline failure is distinct from proven infeasibility. Savings use only comparable
cases. Dollar savings avoid ambiguous percentages with negative prices. A one-second
limit permits honest FEASIBLE/UNKNOWN results. Dataset SHA-256 and source provenance
support comparisons on identical inputs; runtimes and proof completion can vary.

CI fails on invalid schedules, inconsistent statuses, incorrect accounting,
non-finite/invalid bounds, infeasibility contradicted by a feasible baseline,
claimed optima worse than either baseline, and offline parser regressions.

Independent exhaustive tests cover deterministic tiny problems and stochastic
placements with outages, caps, negative prices and reward/penalty settlement.
Bounded-runtime tests enumerate every overrun pattern for a small buffered plan.
Tests also cover dispatch costs, provider failures and actual Streamlit flows.

## Extraction and decision boundaries

The packaged 15-case offline grammar corpus is distinct from the packaged 30-case
natural-language corpus for optional live adapters. Semantic grading validates the
whole Event schema and compares every semantic field; Decimal formatting differences
are harmless. Unexpected fields, missing penalties and unnecessary clarification
fail. Live model quality is **unmeasured**: live evaluations are opt-in and excluded from CI.

The decision workflow distinguishes nominal profitability from a runtime-aware
recommendation. Production failures and delivery failures are tracked separately;
actual energy and reward/penalty settlement enter paired incremental profit.
Training scenarios for stochastic optimization never overlap evaluation scenarios.

## Synthetic calibration

18 regimes each use 400 training observations, 1,000 probability-estimation draws
and 400 independent test outcomes. A fitted Bernoulli overrun probability is compared
with a fixed p=0.15 prior on the same heldout outcomes. Brier scores are evaluated
per binary outcome. Reliability bins use ten fixed probability intervals, weighted
by their number of test observations. Empty bins are omitted.

The checked-in experiment reports fitted Brier 0.1291 versus fixed-prior 0.2028,
and ECE 0.0196 over 7,200 heldout trials. This demonstrates calibration machinery
under its own synthetic data-generating assumptions. It does not establish real
factory risk accuracy, correlation handling, or robustness to longer overruns.

Policy comparison intervals are approximate and adjusted for three comparisons.
The risk threshold is a demonstration policy, not a contractual service guarantee.
See [architecture](ARCHITECTURE.md) for the precise settlement and uncertainty model.

## Reproduce for free

```sh
python -m unittest discover -s tests -v
python -m gridshift.evaluate --count 200 --output evals/latest.json
python -m gridshift.calibration --output evals/calibration.json
```

Scenario report schema is version 3; calibration schema is version 1. The dashboard
reads these reports. GitHub Actions runs correctness/UI tests and regenerates the
scenario report. Optional paid `gridshift.evaluate_llm --provider anthropic` is
excluded from CI and defaults. Its report is ignored by Git.

Production evidence would require real runtime traces, correlated disruptions,
actual utility settlement, independently labeled language evaluations, rolling
execution tests, and audited integration with the operating systems.
