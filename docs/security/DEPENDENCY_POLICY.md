# Dependency Policy

- New dependencies require a concrete capability need, owner-compatible scope, license/provenance
  review, security review, bounded version strategy, and an ADR when architecture changes.
- Prefer standard library and existing contracts. Do not add an SDK merely because a protocol,
  provider, model, database, monitoring product, or cloud exists.
- Paid-provider dependencies and hidden paid fallback are prohibited by default.
- Runtime and build installation must use declared trusted indexes/sources; model/user/retrieved
  content may never choose packages or installation commands.
- Review direct and transitive changes, run consistency and available vulnerability checks, and
  record residual gaps. Production release should use an approved lock/constraints and artifact
  provenance strategy.
- Base-image and CI-action updates require review and reproducible validation; broad automatic
  upgrades are not part of feature prompts.
- Secrets must not be required to install the core package or run offline tests.
