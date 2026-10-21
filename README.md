# ⚡ GridShift

using industrial scheduling × mathematical optimization × measurable reliability

A laptop-only factory planning demo that schedules production around electricity
prices and demand-response incentives while enforcing hard production constraints.
Synthetic data throughout; no utility or factory actions are executed.

## Run the dashboard

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m streamlit run app.py
```

Open http://localhost:8501. On this Mac, `./run.command` also launches the app.
Python 3.9+; package versions are pinned. `requirements-lock.txt` records the tested
macOS/Python 3.9 environment; use `pip install .` for compatible cross-platform resolution.

## What works

- **Factory simulator:** 3 machines, 15 jobs, 24 prices; releases, deadlines,
  compatibility, non-preemptive execution, known outages and site power caps.
- **CP-SAT optimizer:** verified schedules with status, bound and absolute gap.
- **Event workflow:** schema validation, tool dispatch, demand-response economics,
  outage replanning, clarification and evidence-based explanations.
- **Runtime-aware planning:** bounded-runtime reservations, scenario-based stochastic CP-SAT,
  paired realized-profit comparisons, and explicit risk gates.
- **Synthetic calibration:** fitted runtime probabilities, disjoint heldout outcomes,
  Brier scores and reliability diagrams.
- **Evaluation lab:** 200 seeded cases, separate development/heldout seeds, full
  scenario traces, two scheduling baselines, injected defects and regression gates.
- **Dashboard:** comparative timelines, prices, demand, event controls, eval inspection
  and downloadable plan/trace/report JSON. Everything works offline by default.
- **CI:** unit/oracle/UI tests plus a fresh 200-case evaluation artifact on push and PR.

The offline event interpreter is a strict parser, not an LLM. Optional Anthropic and OpenAI adapters
use schema-validated extraction; deterministic code owns tools, schedules and claims.

## Verified demo result

| | FCFS | CP-SAT |
|---|---:|---:|
| Energy cost | $151.70 | $110.80 |
| Energy | 1,690 kWh | 1,310 kWh |
| Constraint violations | 0 | 0 |

Savings: **$40.90 / 27.0%**, proven optimal for the discrete demo model. Both time
shifting and lower-power machine selection contribute. These are synthetic results,
not measured industrial savings. Tied optimal schedules can differ across versions.

## Commands

```sh
python -m gridshift                          # terminal schedule comparison
python -m unittest discover -s tests -v      # correctness, tiny oracles, UI flows
python -m gridshift.evaluate --count 200      # offline scenario + parser evals
python -m gridshift.calibration              # synthetic heldout calibration
```

The eval report is `evals/latest.json`. It records inputs, schedules, status, bounds,
revision and dependency version. Baseline failure is counted separately from proven
infeasibility. Savings averages include only cases with both schedules. No regret is
claimed without an exact oracle; optimality gaps come from the solver's bound.

## No API key required

The complete local demo, stochastic planning, calibration experiment, tests and CI
run without model calls. Offline event extraction is a strict documented grammar,
not a local language model. **No paid API calls were made for this audit.**

Optional adapters are available if you choose to use them later. Anthropic mode has
a masked session-only key field; OpenAI uses `OPENAI_API_KEY` in the server environment.
`.env` files are ignored but not automatically loaded. Model names are configurable
with `GRIDSHIFT_ANTHROPIC_MODEL` / `GRIDSHIFT_MODEL`. Only explicitly selecting a live
provider and evaluating an event sends its text to that provider. Never commit keys.

Optional `python -m gridshift.evaluate_llm --provider anthropic` (or `openai`) makes
paid calls against a separate 30-case language corpus. It is never part of offline
CI. Both adapters have mock tests; live model accuracy remains unmeasured.

## Learn and demonstrate

- [Architecture and mathematics](docs/ARCHITECTURE.md)
- [Five-minute demo and interview questions](docs/DEMO.md)
- [Evaluation methodology](docs/EVALUATION.md)
- [Completion audit and evidence](docs/AUDIT.md)

Read `models.py` first, then `scheduling.py`, `optimizer.py`, and `agent.py`. A binary
optimizer variable means “run this job on this machine at this hour.” Exactly one
placement is selected per job. Hourly occupancy and power constraints remain hard.
Cost is kW × hours × the price in each execution hour, using exact Decimal accounting.

A first learning exercise: tighten one deadline, predict which legal placements
vanish, then rerun. The optimum cannot improve when the feasible set shrinks.

## Scope

This is a complete local demonstration, not a production industrial control system.
One-hour resolution, no setups/dependencies/idle power, known outages before planning,
no mid-execution scheduling or live ERP integration. Runtime risk and calibration use
explicit synthetic assumptions, not real factory measurements. Stochastic bounds
apply to the sampled model; tariff-specific settlement remains outside scope.
See architecture for details.
