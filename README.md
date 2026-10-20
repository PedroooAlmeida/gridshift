# GridShift

Factory scheduling around electricity prices, with independently verified constraints.
A laptop-only learning project connecting industrial operations, optimization, and agent evals.

## Current milestone: Phase 2

Implemented: 3 machines, 15 deterministic jobs, 24 hourly electricity prices,
release times, hard deadlines, machine compatibility, an FCFS baseline,
an independent schedule validator, and exact decimal energy accounting.

CP-SAT now computes a minimum-cost schedule and reports status, objective bound,
and absolute gap. Demand response, LLM agents, and the dashboard are future milestones.
The baseline makes no optimality claim.

## Run locally

From this repository directory:

```sh
python3 -m venv .venv  # already created during initial setup
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m gridshift
python -m unittest discover -s tests -v
```

Python 3.9+; OR-Tools is pinned in pyproject.toml. The lock file records the tested
Python 3.9/macOS environment; other platforms may need compatible dependency versions.
Expected baseline: 0 validation errors, 1,690 kWh, $151.70.
Expected optimized demo: OPTIMAL, 1,310 kWh, $110.80, $40.90 savings (27.0%),
zero absolute optimality gap. Savings combine shifting execution times and choosing
lower-power eligible machines; they are not a pure measure of time shifting.

## Understand the data flow

1. `gridshift/models.py`: frozen data classes define Machine, Job, Factory, Assignment.
2. `gridshift/scenarios.py`: a fixed synthetic factory; no random or live data.
3. `gridshift/scheduling.py`: FCFS produces assignments; validate checks them independently.
4. `gridshift/optimizer.py`: constructs the CP-SAT model and independently validates output.
5. `gridshift/__main__.py`: compares schedules, economics, solver status and bounds.
6. `tests/test_scheduling.py`: checks feasibility, corrupt schedules, hourly pricing,
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
finishes before it, so its cost should stay unchanged. The optimized comparison
may react differently; check the selected schedule rather than assuming. Then change a price during
an occupied hour and calculate the expected cost difference by hand.

## The optimization model

For each legal job j, eligible machine m, and integer start s, create binary
variable x[j,m,s]. A value of 1 means that placement is selected.

- Exactly one placement per required job: sum(x[j,m,s]) = 1.
- At every machine/hour, sum of placements covering that hour <= 1.
- Only create placements that meet release times, deadlines and compatibility.
- Minimize sum(x[j,m,s] × power[m] × sum(prices[s:s+duration[j]])).

CP-SAT needs integer coefficients. Prices are scaled exactly to integers (up to
six decimal places), with no silent rounding; oversized objectives are rejected.
This time-indexed formulation is intentionally easy to inspect and appropriate
for a small daily model. Finer slots and larger factories may need interval variables.

Solver output is checked by the same independent validator and cost calculator as
the baseline. OPTIMAL means proven optimal for this model; FEASIBLE means a schedule
was found without proof. INFEASIBLE means proven impossible; UNKNOWN means no
conclusion, often because of the time limit. No schedule or cost is invented for
those last two statuses. The default limit is ten seconds with one worker and a
fixed seed; runtime and tied optimal schedules can vary across environments.
Bounds are reported as floating-point dollars; schedule costs use Decimal.

`tests/test_optimizer.py` exhaustively enumerates every placement combination for
30 seeded tiny factories and checks optimal cost or infeasibility. It also checks
improvement on the demo, recovery from a greedy failure, and input guards.

Read the [official CP-SAT status definitions](https://developers.google.com/optimization/cp/cp_solver).

Your next experiment: before changing a deadline, predict which candidate placements
will disappear. Run the tests and demo, then explain why the optimal cost cannot
decrease when you tighten a hard constraint (assuming the problem stays feasible).

## Evaluation roadmap

The current tests are correctness checks, including tiny seeded optimization
oracles, not an agent evaluation suite. Next: larger seeded scenario datasets,
aggregate baseline comparisons, failure traces, and versioned regression artifacts.
Once the agent exists, evaluate extraction, tool calls, and supported explanations
separately from solver correctness. Reserve unseen seeds for held-out evaluation.
