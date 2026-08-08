# Model and Cost Policy

## Policy statement

Development targets **$0 external API and LLM cost**. OpenRouter is the planned LLM gateway, and only models explicitly configured and validated as free may be used. Free availability changes; model identifiers must never be scattered through source code.

```text
ALLOW_PAID_MODELS=false
PRIMARY_FREE_MODEL=<configured at deployment>
FALLBACK_FREE_MODEL_1=<configured at deployment>
FALLBACK_FREE_MODEL_2=<configured at deployment>
```

`ALLOW_PAID_MODELS=false` is a security/cost invariant, not a preference. The router must fail closed if policy or pricing status cannot be established. No provider or model failure may trigger paid escalation.

## Appropriate model use

Models may support research planning, complex document understanding, qualitative event/industry/regulatory/risk reasoning, contradiction reasoning, synthesis, and multilingual explanation.

Models should not perform arithmetic, ratios, ticker normalization, schema/date/number validation, database/cache operations, source metadata handling, chart construction, report formatting, retries, or access-control decisions when deterministic code can do so reliably.

## Planned routing behavior

1. Classify deterministic tasks and route them to software without a model call.
2. For reasoning tasks, validate task suitability, model policy, context/output limits and request budget.
3. Attempt the configured primary free model.
4. For retryable 429, timeout, temporary outage, or provider errors, apply bounded exponential backoff with jitter.
5. Move through configured free fallbacks, each with bounded attempts and suitable context capability.
6. Validate response structure and safety; malformed output may use the next free route within budget.
7. Return a typed degraded/failed result after exhaustion.

Retries must not amplify invalid requests, authentication failures, or policy violations. A total deadline, attempt cap, concurrency cap, and token/output cap bound the route.

## Configuration validation

- Model IDs are environment/config values, never domain constants.
- Empty fallback slots are allowed.
- Duplicate model IDs are rejected or deduplicated visibly.
- A configured paid or unknown-cost route is rejected while paid models are disabled.
- Startup and runtime checks must never print keys.
- A later operational process must revalidate the provider's current free designation; a model name suffix alone is insufficient proof.

## Evidence and output constraints

- Model output is untrusted and schema-validated.
- A model cannot create a source record without an actual acquired source.
- Citations must resolve to evidence identifiers; invented URLs/references are rejected.
- The router records safe metadata: research run, agent/task, configured model identifier, input/output tokens when supplied, latency, retry count, status, estimated cost, cached/not-cached state, validation result, and error category.
- Prompts should minimize source content and tokens while retaining evidence references.
- Retrieved instructions cannot override system, security, source, or cost policy.

Under `ALLOW_PAID_MODELS=false`, estimated model cost is expected to remain `$0`; a non-zero estimate or unknown-price route is a fail-closed policy incident, not an invitation to continue.

## Caching and reuse

Model-result caching is planned only where the request, prompt/template version, configured model, normalized evidence inputs, language, and policy context form a safe deterministic cache key. Cache entries require bounded retention and evidence-freshness invalidation. The system must not reuse results across incompatible users, research runs, source versions, or policy contexts, and a cached interpretation never becomes evidence. Deterministic acquisition and calculation caches remain preferable to repeated model calls.

## Graceful degradation

If all free models are unavailable, deterministic acquisition/analysis may continue where useful. The system returns partial structured results and an explicit synthesis limitation. It never conceals the outage, fabricates an answer, or purchases capacity.

## Change control

Changing gateways, enabling paid models, or changing the fail-closed rule requires explicit owner approval, a security/cost review, and an ADR. Merely editing an environment variable is not sufficient authorization.
