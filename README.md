# ⚡ GridShift

**Industrial scheduling × mathematical optimization × measurable reliability.**

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
- **Runtime stress:** seeded Monte Carlo deadline/power-limit failures and sampling intervals.
- **Evaluation lab:** 200 seeded cases, separate development/heldout seeds, full
  scenario traces, historical parser/accounting defects and regression measurements.
- **Dashboard:** comparative timelines, prices, demand, event controls, eval inspection
  and downloadable plan/trace/report JSON. Everything works offline by default.
- **CI:** unit/oracle/UI tests plus a fresh 200-case evaluation artifact on push and PR.

The offline event interpreter is a strict parser, not an LLM. Optional OpenAI mode
uses typed structured extraction; deterministic code owns tools, schedules and claims.

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
```

The eval report is `evals/latest.json`. It records inputs, schedules, status, bounds,
revision and dependency version. Baseline failure is counted separately from proven
infeasibility. Savings averages include only cases with both schedules. No regret is
claimed without an exact oracle; optimality gaps come from the solver's bound.

## Optional live language model

Export `OPENAI_API_KEY` in your shell before launching the dashboard, then select
OpenAI mode in Event agent. Never commit keys. `.env.example` documents variable
names; `.env` is ignored and is not loaded automatically. `GRIDSHIFT_MODEL` optionally
overrides `gpt-4.1-mini`. Clicking Evaluate sends the event text to OpenAI.

```sh
python -m gridshift.evaluate_llm  # opt-in paid API calls; requires a configured key
```

The live extraction report is ignored by Git. Offline benchmark results are not
LLM eval scores. The SDK adapter is unit-tested with mock responses; live API behavior
requires a real configured key and an explicit live evaluation.

## Learn and demonstrate

- [Architecture and mathematics](docs/ARCHITECTURE.md)
- [Five-minute demo and interview questions](docs/DEMO.md)
- [Evaluation methodology](docs/EVALUATION.md)

Read `models.py` first, then `scheduling.py`, `optimizer.py`, and `agent.py`. A binary
optimizer variable means “run this job on this machine at this hour.” Exactly one
placement is selected per job. Hourly occupancy and power constraints remain hard.
Cost is kW × hours × the price in each execution hour, using exact Decimal accounting.

A first learning exercise: tighten one deadline, predict which legal placements
vanish, then rerun. The optimum cannot improve when the feasible set shrinks.

## Scope

This is a complete local demonstration, not a production industrial control system.
One-hour resolution, no setups/dependencies/idle power, known outages before planning,
no mid-execution scheduling or live ERP integration. Runtime risk is an explicitly
synthetic stress model, not calibrated to real factories. Stochastic optimization
and tariff-specific settlement are future extensions. See architecture for details.
