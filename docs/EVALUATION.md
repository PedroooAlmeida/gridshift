# Evaluation methodology

## What is measured

The offline benchmark runs 200 seeded factories with three machines, eight jobs,
12 hours, variable prices (including negatives), machine compatibility, optional
outages and optional site caps. Every eleventh seed adds a known resource conflict.
One hundred development cases and one hundred separately ranged heldout seeds are
reported. These are synthetic holdouts, not external validation of a learned model.

Every case stores the complete factory, FCFS assignments/cost when available,
optimized assignments, solver status, bound, elapsed time, and independent validation
errors. A greedy failure is not treated as factory infeasibility. Feasibility rate
counts returned schedules separately from status; UNKNOWN cannot be silently counted
as a proof. Baseline savings average only cases where both methods returned a plan.
Negative prices make percentage savings ambiguous, so aggregate savings use dollars.
A one-second per-case limit keeps runs laptop-friendly; timeouts are reported honestly.

Correctness tests independently enumerate all placements for 30 tiny seeded problems,
compute resource use and objective without the optimizer's candidate builder, then
compare the exact optimal cost or infeasibility. This oracle provides a stronger
check than simply asking the same solver to validate its own output. Bounds and
gaps are reported for larger cases; no exact decision regret is invented.

## Extraction and workflow evals

Fifteen manually labeled event cases cover complete offers, outages, missing
penalties, malformed/contradictory hours, multiple events and trailing injected
instructions. The field grader compares expected fields exactly. Clarification is
correct only when the expected outcome is clarification; a valid event that is
unnecessarily rejected fails. This is a small grammar regression corpus, not a
broad natural-language benchmark. Optional live OpenAI extraction uses the same
labels and produces a separate report with the model name and per-case output.

Workflow tests independently verify economic acceptance/decline/ties, unknown
machines, impossible outages, no tools on ambiguous instructions, rejection of
reductions larger than reference load, per-hour caps, and escalation on UNKNOWN
or unproven economic comparisons. Explanations are deterministic templates using
solver outputs; the LLM cannot invent savings in a free-form explanation.

## Eval-driven development examples

The quarantined `legacy_parse` in the eval module reproduces an intentionally
permissive first version: it accepts a prefix, defaults a missing penalty to zero,
and does not validate the event window. It passes 5/15 examples. The shipped strict
parser passes 15/15. This is a reproducible engineered regression example, not a
claim of a historical deployed incident. Do not tune the examples and claim the
result generalizes to arbitrary language.

A second defect bills every execution hour at the start-hour price. In the checked-in
200-case benchmark it misprices 120 of 121 schedulable FCFS plans. The fixed accountant
integrates hourly load × each actual hourly price and agrees with an independent
assignment-by-hour calculation in all cases. The two errors show why schema checks
and numerical graders must be separate.

## Runtime stress

The dashboard runs 500 seeded trials with an explicit probability that each job
runs one hour long. It measures deadline failures, power-cap failures and their
union, with a Wilson sampling interval. Trials preserve machine ordering and wait
out outages. Zero and certain-overrun tests verify extreme behavior. This is a
sensitivity analysis, not a trained or calibrated risk estimator. The optional
financial sensitivity uses nominal energy cost; it is not expected realized profit.

## Reproduce and inspect

```sh
python -m unittest discover -s tests -v
python -m gridshift.evaluate --count 200 --time-limit 1 --output evals/latest.json
# Optional paid calls, only with a configured API key:
python -m gridshift.evaluate_llm
```

Inspect `evals/latest.json` or the dashboard's Eval lab. The report records source
revision, dirty-working-tree flag, solver version, seeds and time limit. Runtimes
vary by machine. CI stores a fresh report as an artifact. Preserve old reports to
compare revisions on identical seeds; do not compare different datasets as if
only the implementation changed. The JSON schema version is currently 1.

## Remaining evidence needed for production

Real factory runtime distributions and correlated outages; actual utility baseline
and settlement rules; a larger independently labeled language corpus; live-model
prompt/model regression runs; rolling execution tests; human approval and audited
ERP actions. None is implied by the synthetic pass rates.
