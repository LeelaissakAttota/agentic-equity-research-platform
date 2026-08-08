# Contributing

Thank you for contributing. This repository is phase-gated: a useful change that belongs to a future phase is still out of scope until that phase is authorized.

## Before starting

Read `PROJECT_STATUS.md`, `PROJECT_RULES.md`, `ARCHITECTURE.md`, the active section of `PHASES.md`, `CODING_STANDARDS.md`, `TESTING_STRATEGY.md`, and `GIT_WORKFLOW.md`. Check existing Git changes and avoid modifying unrelated work.

## Propose the change

Describe the problem, owning phase, expected behavior, evidence/source implications, security and cost effects, compatibility/migration impact, tests, and documentation changes. Significant architectural changes require an ADR and owner approval before implementation.

## Implement

- Keep work within the active phase and clean-architecture boundaries.
- Prefer deterministic code and provider-neutral ports.
- Preserve provenance and make uncertainty/conflicts visible.
- Add timeouts, bounds, validation, and structured errors at external boundaries.
- Never add real credentials, mandatory paid providers, paid model fallback, fabricated facts, or direct trade execution.
- Update relevant documentation and changelog entries.

## Test

Run the smallest relevant tests during development and the required phase gate before review. Default tests must work without network or secrets. Include negative/failure cases and report any skipped or live checks explicitly.

```powershell
python -m pytest
```

Formatting, lint, typing, integration, evaluation, build, and security commands will be added as their tooling is approved in later phases.

## Review and Git

Follow `GIT_WORKFLOW.md` and its commit convention. Inspect staged content for secrets and generated data. Do not commit/push unless explicitly authorized. Reviews may block changes that weaken evidence, correctness, source authority, free-cost, security, phase scope, or test guarantees.

## Reporting issues

Include reproducible input, expected/actual behavior, environment/version, safe logs or research-run identifier, source/as-of context for factual defects, and impact. Remove secrets and sensitive/raw copyrighted content.

## Responsible security reporting

Do not publish exploitable details or credentials in a public issue. Use the repository owner's private security channel when established. Until then, notify the owner privately and avoid further access or data exposure.
