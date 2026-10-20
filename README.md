# GridShift

Factory scheduling around electricity prices, with independently verified constraints.
A laptop-only learning project connecting industrial operations, optimization, and agent evals.

## Current milestone: Phase 1

Implemented: 3 machines, 15 deterministic jobs, 24 hourly electricity prices,
release times, hard deadlines, machine compatibility, an FCFS baseline,
an independent schedule validator, and exact decimal energy accounting.

Optimization, demand response, LLM agents, and the dashboard are future milestones.
The baseline makes no optimality claim.

## Run locally

From this repository directory:

```sh
python3 -m venv .venv  # already created during initial setup
source .venv/bin/activate
python -m gridshift
python -m unittest discover -s tests -v
```

Python 3.9+; Phase 1 has no third-party runtime dependencies.
Expected demo: 0 validation errors, 1,690 kWh, $151.70.

## Understand the data flow

1. `gridshift/models.py`: frozen data classes define Machine, Job, Factory, Assignment.
2. `gridshift/scenarios.py`: a fixed synthetic factory; no random or live data.
3. `gridshift/scheduling.py`: FCFS produces assignments; validate checks them independently.
4. `gridshift/__main__.py`: runs the fixture and prints the schedule and economics.
5. `tests/test_scheduling.py`: checks feasibility, corrupt schedules, hourly pricing,
   and a feasible case where the greedy baseline fails.

A Machine has power in kW. A Job has a duration, release time, deadline,
and eligible machines. An Assignment records a job's chosen machine and start/end.
The Factory combines jobs, machines, and prices.

## Explicit assumptions

- One day with 24 one-hour slots; times are offsets, not timezone timestamps.
- Intervals are [start, end): finishing at 3 and starting at 3 do not overlap.
- Jobs run continuously on one machine; duration does not depend on machine.
- Active machine power is constant. Idle power is zero.
- No setups, ramping, dependencies, outages, demand charges, or uncertainty yet.
- All jobs are mandatory; deadlines are hard.
- Prices are dollars per kWh; negative electricity prices are supported.
- Cost = sum over hours of (active kW × 1 hour × that hour's $/kWh).
  Decimal avoids binary floating-point rounding; round only when displaying dollars.
- FCFS orders jobs by release hour, preserving input order for ties. It chooses the
  earliest finish among eligible machines, breaking ties by machine ID. It appends
  jobs to each machine's queue without backtracking or filling earlier gaps.
- Input validation checks schema consistency, not global feasibility.
- Type annotations describe the Python API; these are not yet external JSON schemas.

## Your first experiment

Before editing code, predict what happens if the 17:00 price doubles. Run the demo
and inspect which assignments actually execute during that slot. The baseline
finishes before it, so its cost should stay unchanged. Then change a price during
an occupied hour and calculate the expected cost difference by hand.

Next, we'll formulate CP-SAT decision variables and hard constraints together,
then compare its output with this baseline using the same independent validator.
We will report solver status and bounds rather than label every solution optimal.

## Evaluation roadmap

The current tests are correctness checks, not an agent evaluation suite. Next:
small hand-solvable optimization fixtures, seeded scenario datasets, baseline
comparisons, proven bounds and gaps, infeasible cases, and regression artifacts.
Once the agent exists, evaluate extraction, tool calls, and supported explanations
separately from solver correctness. Reserve unseen seeds for held-out evaluation.
