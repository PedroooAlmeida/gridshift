# Completion audit — 20 October 2026

The local demonstration now includes deterministic and scenario-based stochastic
optimization, bounded-runtime planning, realized-profit risk gates, a reproducible
synthetic calibration experiment, and separate offline/live extraction corpora.
Everything demonstrated and tested here runs without paid model calls.

## Material findings and repairs

| Finding | Repair / evidence |
|---|---|
| Nominal positive profit could appear as acceptance despite high execution risk | Distinct nominal state; compare three policies and require risk/profit gates |
| Random disturbances changed when a policy changed machine assignments | Job-indexed common random numbers for paired comparisons |
| Financial sensitivity omitted realized overrun energy | Actual dispatch energy, reward forfeiture and penalty included in paired profit |
| FCFS savings mixed timing and machine efficiency | Fixed-machine timing ablation and price-aware greedy comparator |
| Regression report did not gate all claimed invariants | Explicit status, accounting, bound, dominance and infeasibility gates |
| Live language eval reused strict grammar cases | Separate 30-case natural-language corpus; no live score claimed |
| Evaluation data absent from installed package | Package resources included; wheel tested outside the source checkout |
| Browser retained old Decision objects during hot reload | Discard obsolete session results; rerun and verify current UI |

## Observed evidence

- 34 tests pass across the full initial suite and targeted reruns after the final additions.
  Coverage includes Streamlit flows, provider mocks, independent exhaustive deterministic
  and stochastic oracles, and all bounded overrun patterns in a small certified plan.
- The final local 200-case report has 168 proven optima, 32 proven infeasible cases,
  zero invalid returned schedules, and no regression failures. FCFS and price-aware
  greedy each return 121 comparable schedules. Mean savings versus price-aware greedy
  are $9.06 on its comparable subset. Time-limited results can vary by hardware.
- The default offer's nominal plan fails 66.4% of 500 synthetic runtime trials and
  has mean incremental profit −$97.64. The buffered plan has 0 observed failures and
  +$60.06; the selected stochastic plan has 0 observed failures and +$67.94. Zero
  observed failures is not zero population risk: the adjusted upper bound is 1.1%.
- Synthetic calibration uses 7,200 training observations and 7,200 separate heldout
  trials. Fitted Brier score is 0.1291 versus 0.2028 for the fixed prior; ECE is 0.0196.
- A built wheel successfully loads both event corpora and evaluates scenarios from
  outside the repository. Dependency consistency check passes.
- The actual browser shows the selected stochastic timeline and the policy comparison.

## Explicit limits

No paid API calls were made. Anthropic and OpenAI adapters are mock-tested, with live
quality unmeasured. Offline parsing remains a documented grammar. All savings and
risk evidence is synthetic. Real factory calibration, real tariff settlement,
rolling execution, and integration with factory systems are outside this local
project's scope. A sampled stochastic optimum is not a population-optimality claim.

Reproduction commands and statistical assumptions are in [Evaluation](EVALUATION.md)
and [Architecture](ARCHITECTURE.md). The checked-in scenario report includes source
and dataset hashes; its dirty-tree marker honestly reflects generation before commit.
