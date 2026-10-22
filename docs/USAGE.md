# Usage

Start the dashboard with `streamlit run app.py`. The production view compares FCFS
and optimized schedules; its price control changes the 08:00–11:00 tariff. Expand
the timing ablation to separate time shifting from machine selection.

## Events

Offline mode accepts these two formats, with different numbers or machine IDs:

```text
Reduce 20 kW between 8 and 10 for $100 reward and $200 penalty
Machine mill unavailable between 4 and 8
```

Hours are integer boundaries in a single day. Rewards and penalties are total USD
amounts, not hourly rates. An incomplete or unsupported event returns clarification.
Outages are known before planning; the system does not reschedule work in progress.

For a profitable nominal offer, the workflow compares nominal, buffered and
stochastic plans using paired execution simulations. The displayed recommendation
must pass both risk and profit thresholds. Download the trace to inspect the parsed
event, frozen reference, solver results, candidate schedules and policy statistics.

## Optional language-model extraction

Installations include Anthropic and OpenAI adapters. Select one in Event agent to
use natural-language extraction. Anthropic accepts a session-only masked key or
`ANTHROPIC_API_KEY`; OpenAI reads `OPENAI_API_KEY` from the server environment.
`.env.example` lists supported variables. `.env` is ignored and is not auto-loaded.

| Provider | Model variable | Default |
|---|---|---|
| Anthropic | `GRIDSHIFT_ANTHROPIC_MODEL` | `claude-sonnet-4-6` |
| OpenAI | `GRIDSHIFT_MODEL` | `gpt-4.1-mini` |

Selecting a provider and evaluating an event sends that event to its API and incurs
provider charges. Errors and refusals stop the workflow; there is no silent fallback.
Keys are not included in application traces. Default operation and CI use no APIs.

To evaluate a configured provider against the separate language corpus:

```sh
python -m gridshift.evaluate_llm --provider anthropic
# or: python -m gridshift.evaluate_llm --provider openai
```

The report at `evals/llm-local.json` is ignored by Git. Grammar regression scores and
mock adapter tests do not measure live model accuracy.
