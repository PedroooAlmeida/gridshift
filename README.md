# GridShift

[![CI](https://github.com/PedroooAlmeida/gridshift/actions/workflows/checks.yml/badge.svg)](https://github.com/PedroooAlmeida/gridshift/actions/workflows/checks.yml)

Production scheduling under time-varying electricity prices and uncertain job
runtimes. GridShift uses OR-Tools CP-SAT to assign jobs to machines, evaluate
demand-response offers, and compare the resulting schedules under runtime overruns.

**Simple English version:** It plans when and where factory jobs should run to
reduce electricity costs while meeting deadlines. It also checks what happens
if jobs take longer than expected.

## Run

Python 3.9+:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
streamlit run app.py
```

Open [localhost:8501](http://localhost:8501). No API key is required.
`python -m gridshift` runs the scheduling example without the dashboard.

## Design

- **Scheduling:** binary job/machine/start decisions with release times, deadlines,
  machine eligibility, outages and hourly power caps. Costs use exact integer
  coefficients in the solver and independent Decimal accounting afterward.
- **Uncertainty:** compare nominal schedules, bounded-runtime reservations, and a
  sample-average stochastic program. Machine/start decisions are shared across
  training scenarios; separate simulation draws measure execution risk and profit.
- **Decisions:** freeze the no-offer reference before evaluating a demand-response
  contract. Require both positive estimated profit and an acceptable failure bound
  before recommending participation. Event parsers supply data, not decisions.
- **Validation:** check returned schedules independently; compare small problems
  with exhaustive enumeration. Report incumbents and bounds separately so a timeout
  cannot be mistaken for an optimality or infeasibility proof.

The included 3-machine, 15-job example costs **$110.80**, versus **$151.70** for FCFS.
The $40.90 difference includes both timing and machine selection; the dashboard
provides a fixed-machine ablation. These are synthetic results.

## Development

```sh
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
python -m gridshift.evaluate --count 200
python -m gridshift.calibration
```

CI runs the tests and 200 seeded scheduling cases. Reports contain both FCFS and
price-aware greedy baselines, solver bounds, per-case failures, and source/data hashes.
Calibration is a separate experiment with disjoint synthetic training and test data.

## Documentation

- [Model, settlement rules and statistical assumptions](docs/ARCHITECTURE.md)
- [Benchmarks and validation methodology](docs/EVALUATION.md)
- [Event syntax and optional model adapters](docs/USAGE.md)

The model uses one-hour slots, constant active power and independent bounded runtime
overruns. It does not model setup costs, job dependencies or rolling execution.
No factory or utility system is connected. Optional Anthropic/OpenAI adapters are
mock-tested; live extraction accuracy has not been measured.
