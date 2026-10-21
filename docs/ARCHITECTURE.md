# Architecture and engineering decisions

GridShift is a local planning workflow using synthetic factory data. No business
actions are executed. No paid service is required.

```text
Event text → strict offline grammar (or optional provider extraction)
           → Pydantic event validation → deterministic dispatcher
             ├─ clarification → no solver call
             ├─ outage → add unavailability → optimize + verify
             └─ offer → optimize reference → freeze hourly demand
                      → nominal plan → buffered plan / stochastic plan
                      → paired heldout runtime trials → risk/profit gates
                      → recommendation + complete evidence trace
```

## Deterministic scheduling

Binary x[j,m,s] selects a job, eligible machine and integer start hour. Legal
placements respect release, deadline and outages. Exactly one placement is chosen
per job. Machine occupancy is at most one job per hour; total active power cannot
exceed site caps. The objective integrates each execution hour's kW × price.
Prices scale exactly to integers, with at most six decimals and a conservative
numeric budget. Independent code verifies assignments and Decimal costs.

OPTIMAL proves optimality for this discrete model. FEASIBLE provides an incumbent
and bound. UNKNOWN provides no conclusion; INFEASIBLE proves no legal schedule
exists. One worker and a fixed seed improve repeatability; tied solutions and
wall-time limits can still vary across platforms.

The dashboard's savings ablation first fixes FCFS machine assignments and optimizes
only timing, then frees machine choice. Attribution is sequential and order-dependent;
only proven-optimal subproblems support exact attribution. The benchmark also uses
a price-aware greedy baseline to avoid relying solely on a weak FCFS comparator.

## Demand-response settlement

The no-offer optimized reference is frozen before participation planning. Every
event hour must reduce load by the stated amount from that reference; negative
targets cannot be clipped to zero. Existing site caps also apply. This is a synthetic
contract, not an implementation of a particular utility tariff.

The nominal comparison requires optimal reference and offer solves. Positive nominal
profit triggers further runtime-aware planning, never immediate acceptance. A failed
nominal economic gate declines this conservative workflow; it is not a proof that
all possible stochastic participation policies lose money. A failed/unknown nominal
solve likewise does not prove the stochastic problem infeasible.

Delivered reward is a total payment. Failed delivery forfeits that reward and pays
the stated penalty. Paired simulations subtract actual participation energy cost
from actual no-offer energy cost under the same job disturbances. Deadline and site
cap failures are feasibility gates and are not monetized. No delayed-production
value, demand charges, idle power or tariff-specific settlement is modeled.

## Buffered and stochastic planning

**Buffered:** optimize with each duration increased by one hour, then project back
to nominal durations. Any actual runtime in [d,d+1] occupies a subset of the reserved
interval. With nonnegative machine power, this certifies deadlines, occupancy,
outages and caps for every such realization. The reservation-energy objective is
conservative, not expected realized cost.

**Stochastic:** static sample-average approximation uses 24 independent training
scenarios. Machine/start decisions are shared across all scenarios (nonanticipativity).
Production constraints hold in every training scenario. A scenario delivery indicator
controls its reward or penalty. The objective minimizes average realized energy
minus delivered reward plus failure penalty. Every training scenario and settlement
is independently reconstructed after solving. This is a genuine stochastic program,
with a bound for the finite sampled model; it is not a claim of global population
optimality or a two-stage recourse formulation.

**Out-of-sample assessment:** 500 disjoint evaluation draws compare nominal, buffered
and stochastic policies. Draws are indexed by job ID so moving machines does not
change a job's random disturbance. Dispatch preserves machine order and postpones
starts for overruns or outages. Tail energy beyond the horizon uses the nonnegative
maximum daily price. A policy qualifies only if its upper failure bound is ≤5%
(or it has the bounded-runtime certificate) and its lower mean incremental-profit
bound is positive. The highest sample mean among qualifying policies is recommended.

Profit uses a normal-approximation paired-mean interval. Failure uses a Wilson
interval. Both use z=2.394 for Bonferroni adjustment over up to three policies;
these are approximate simultaneous 95% intervals within each family, not a joint
95% guarantee across all metrics. They account for simulation sampling, not model
misspecification. No factory action occurs on recommendation.

## Calibration and model boundaries

`fit_overrun_probability` fits independent binary observations with a Beta(1,1)
posterior mean. A reproducible experiment spans 18 synthetic runtime regimes and
uses separate training observations, prediction draws and heldout execution draws.
It reports individual-outcome Brier scores and a ten-bin reliability diagram/ECE.
The event demo assumes p=0.15; the calibration experiment separately tests learning
p from data. Neither is calibrated to a real factory. Runtime independence and
one-hour bounded overruns are explicit assumptions, not validated industrial facts.

## Optional model boundary

Offline parsing accepts two documented grammars and clarifies anything else.
Anthropic's Messages tool schema and OpenAI's structured extraction are optional,
explicitly selected adapters. Local validation rejects malformed/multiple/truncated
Anthropic tool calls. The model only extracts one event; Python chooses tools,
schedules, economic decisions and explanations. API errors never silently switch
providers. Keys stay out of traces and exports. Default operation and CI make no
paid calls. Mock adapter tests establish plumbing, not live semantic accuracy.

## Scope

One-hour slots; fixed active power; machine-independent durations; no setups,
job dependencies or rolling execution state. Outages are known before planning.
No ERP, live factory or utility integration. Real runtime data and deployment-specific
validation remain necessary before any operational use.
