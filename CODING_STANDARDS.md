# Coding Standards

## Python baseline

- Target Python 3.12 and UTF-8.
- Use a `src` layout and absolute package imports.
- Add type hints to public functions, methods, boundaries, and significant internal logic.
- Use concise docstrings for public contracts and non-obvious invariants; do not narrate obvious code.
- Prefer `pathlib.Path`, timezone-aware datetimes, explicit decimal policy for financial values, and enums/literals for closed vocabularies.
- Avoid mutable default arguments, hidden global state, wildcard imports, circular dependencies, and import-time I/O.

## Architecture dependencies

Dependency direction is interface/infrastructure -> application -> domain. Domain code must not import FastAPI, LangGraph, HTTPX, OpenRouter clients, SQL drivers/ORM, Redis, Streamlit, MCP, or provider SDKs.

Define ports near the policy/use case that owns them and adapters near external technology. Avoid generic “utils” dumping grounds; name modules by cohesive responsibility.

## Models and validation

- Use Pydantic v2 for external/configuration boundaries when introduced; keep pure domain value objects framework-neutral where practical.
- Reject invalid or ambiguous input explicitly; do not coerce facts in ways that lose unit, period, currency, exchange, or precision.
- Version externally persisted/serialized schemas.
- Use structured exception types and safe user-facing error mappings; never catch broad exceptions without adding value and preserving cause.

## Financial correctness

- Use `Decimal` or documented integer scaling where binary floating point would alter reported financial values.
- Store units, scale, currency, period, time zone/as-of, and source alongside numbers.
- Centralize formula definitions and version them when outputs are persisted.
- Never ask an LLM to calculate a value that deterministic code can calculate.
- Represent missing, unavailable, zero, and not-applicable distinctly.

## Async and external I/O

- Use async only across actual I/O/concurrency boundaries.
- Require explicit HTTP timeouts, bounded retries, cancellation propagation, concurrency limits, and response-size controls.
- Classify external failures; do not retry permanent/policy/validation errors.
- Make expensive/retriable operations idempotent or protect them with idempotency keys.

## Logging and observability

Use structured events with research-run/task correlation and safe fields. Do not log secrets, authorization headers, DSNs, raw model prompts/responses, or full documents by default. Measure retries, latency, token usage when known, cache results, and terminal error classes.

## Style and tooling

The baseline intends Ruff for formatting/linting, mypy for static checking, and pytest/pytest-asyncio for tests. Exact rule selection may be refined in Phase 1 without weakening core correctness/security rules. Keep lines readable, functions focused, names explicit, and public APIs small.

## Tests

- Mirror package responsibilities under the appropriate test layer.
- Name tests by observable behavior.
- Prefer deterministic fixtures/builders over shared mutable setup.
- Test failure and edge conditions, not only happy paths.
- Do not use live providers in the default suite.

## Dependencies

Minimize dependencies, constrain compatible ranges, review license/security/maintenance, and update lock artifacts when dependency policy is introduced. A package is not justified merely to avoid a small clear function.

## Comments and TODOs

Comments explain why, risk, provenance, or invariant. TODOs must have an owner/tracking reference before production; do not leave dead stubs or pretend-future implementations.
