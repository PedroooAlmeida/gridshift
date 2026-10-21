# Architecture and engineering decisions

GridShift is a bounded planning workflow with an optional LLM event interpreter.
It runs entirely on synthetic factory data. It does not execute business actions.

```text
Natural-language event
    │
    ├─ Offline full-match grammar (default, deterministic)
    └─ OpenAI structured extraction (explicit opt-in)
    │
Pydantic Event validation
    │
Deterministic tool dispatcher
    ├─ clarify → no optimizer call
    ├─ outage → add unavailability → optimize
    └─ demand response → optimize reference → freeze hourly demand
                         → enforce per-hour reduction → optimize candidate
    │
Independent schedule checker + Decimal cost accountant
    │
Status-aware economic policy → explanation from verified values → trace
```

## Scheduling mathematics

Binary x[j,m,s] chooses job j on eligible machine m at integer hour s. Only legal
placements inside the release/deadline window, outside known outages, are created.
Each job chooses exactly one placement. For each machine/hour, at most one selected
placement may cover it. For capped hours, sum(power[m] × covering x) ≤ cap[h].
The objective sums power × hourly price over selected placements. Prices scale
exactly to integers (at most six decimal places); oversized coefficients are rejected.
The time-indexed formulation is readable for daily models but grows with jobs,
machines and time slots. Interval variables are a logical next step at larger scale.

OPTIMAL is a proof for this model, FEASIBLE is an incumbent without proof, UNKNOWN
is no conclusion, and INFEASIBLE is a proof of impossibility. An independent checker
verifies every returned schedule, including energy costs. No fake answer is returned
on timeout. Single-worker fixed-seed solving supports repeatable comparisons; tied
schedules and runtimes can vary with dependency versions and hardware.

## Demand-response contract

The reference is the optimized no-offer schedule, frozen before adding the offer.
This prevents deliberately inflating a baseline to manufacture savings. It is a
synthetic contractual convention, not an implementation of a real utility tariff.
For every event hour: cap[h] = reference_load[h] − promised_reduction. A negative
cap immediately declines the offer; it cannot be clipped to zero to fake delivery.
Existing site caps remain binding. Participation is accepted only when both solves
prove optimality and reward exceeds incremental energy cost. Otherwise it is declined
or escalated for review. The reward is a total payment, not a per-hour payment.
Under nominal execution, the full reduction is hard, so nominal penalty is zero.
If delivery fails, the modeled sensitivity forfeits the reward and adds the stated
penalty. Hard job deadlines are never priced away.

## Event and LLM boundary

The offline parser accepts two documented grammars and asks for clarification for
anything else. It is not advertised as language understanding. OpenAI mode extracts
one typed event with Responses structured outputs. It cannot supply schedules,
change solver tools, waive constraints, or author economic claims. Deterministic
Python routes the validated event and writes the explanation from solver evidence.
This is deliberately a bounded workflow, not an autonomous general-purpose agent.
Schema validation does not prove semantic extraction accuracy; run the separate
live eval when an API key is configured. Refusals/errors stop execution visibly.
The default model is configurable through GRIDSHIFT_MODEL; availability depends
on the user's API account. No API key is required for the offline demo or CI.

Implementation reference: [official structured outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

## Uncertainty

The runtime simulator independently adds one hour to each job with probability p.
Jobs keep their assigned machine and order, waiting if earlier work runs long or
an outage intersects execution. Trials count deadline and power-cap failures.
A Wilson interval describes Monte Carlo sampling uncertainty, not real-world model
accuracy. The UI's reward/penalty sensitivity uses nominal energy costs, excluding
actual overrun energy and delay penalties. It is explicitly not expected profit.
There is no calibrated risk forecast, stochastic optimizer, or real tariff settlement.

## Known scope limits

One-hour slots; fixed machine power and machine-independent runtimes; no idle power,
setup costs, dependencies or demand charges. Outages are known before planning;
there is no rolling execution state or preservation of already-started jobs.
Synthetic currency is USD. No live ERP, electricity market, factory or utility APIs.
These are intentional demo boundaries, not production readiness claims.
