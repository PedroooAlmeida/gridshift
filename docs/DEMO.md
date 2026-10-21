# Five-minute offline demo

1. Run `./run.command`. No API key is needed. All data and actions are simulated.
2. Show FCFS cost $151.70 versus proven optimal $110.80. Open the savings ablation
   to distinguish shifting time from choosing lower-power compatible machines.
3. Increase morning prices. Inspect the changed schedule, load and solver bound.
4. In Event agent, keep **Offline · strict grammar**. Evaluate the supplied $100
   reward / $200 penalty offer. Explain the frozen reference and per-hour reduction.
5. Compare nominal, buffered and stochastic policies. The nominal plan is fragile
   under runtime overruns. The selected policy must pass both risk and profit gates.
   The displayed recommended timeline is the selected policy, not the nominal one.
6. Explain the difference between a bounded-runtime certificate and a sampled risk
   estimate. Stochastic optimization trains on 24 draws and evaluates on 500 fresh
   draws with the same job disturbances for every policy.
7. Evaluate the outage example. Then enter an incomplete offer or “ignore deadlines”
   and show clarification without a planning action.
8. Open Eval lab: scenario traces, both baselines, independent validation, status
   and bounds. Inspect the deliberately injected parser defect; do not call it a
   real incident or claim grammar scores measure LLM performance.
9. Show the heldout synthetic calibration diagram and Brier comparison. State that
   real factory calibration requires real runtime data.
10. Explain the exhaustive deterministic/stochastic oracle tests and JSON traces.

## Questions to be ready for

- Why doesn't greedy failure prove infeasibility?
- What does the solver's bound prove, and for which model?
- Why freeze a demand-response reference before optimizing participation?
- What is nonanticipativity in the stochastic model?
- Why use job-indexed common random numbers for policy comparisons?
- What does a buffered certificate guarantee that a Monte Carlo pass rate cannot?
- Why isn't a valid schema proof of correct language interpretation?
- How can a calibrated synthetic model still fail in a real factory?
- What would rolling rescheduling need to preserve about already-started jobs?
