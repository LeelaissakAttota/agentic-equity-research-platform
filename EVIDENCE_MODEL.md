# Evidence Model

## Purpose

The evidence model makes research claims traceable, time-aware, verifiable, and conflict-preserving. It is a conceptual Phase 0 contract; database tables and graph technology are deferred.

## Core concepts

### Research run

The root audit context for a request. Its canonical `research_run_id` follows the UUIDv4 contract in `ARCHITECTURE.md`; it records the original request, actor/session reference where permitted, language preference, timestamps, state, plan version, budgets, completion quality, and terminal outcome.

### Company identity

A canonical issuer/security context: legal/display name, ticker, exchange, country, security/issuer identifiers where available, currency context, validity dates, and aliases. Ticker alone is not globally unique.

### Source

An acquired item or authoritative reference: source identifier, name, type, authority level, URL/reference, publisher, publication/filing date, retrieval time, content type, integrity hash, storage locator, terms/attribution metadata, and acquisition status.

### Evidence item

A precise excerpt, table cell/range, filing fact, observation, or calculated result that supports or refutes a claim. It links to the source and a reproducible locator, preserves raw/normalized values, units and periods, and records extraction method/version.

### Claim

A normalized assertion with subject/company, claim type, value, currency/unit, reporting period or valid time, qualifiers, and lifecycle state. Narrative and quantitative claims use compatible provenance rules but may require different validators.

### Relationship and contradiction

Typed edges express `supports`, `refutes`, `derived_from`, `supersedes`, `amends`, `duplicates`, `about`, and `compares_with`. A contradiction is a first-class record containing conflicting claim/evidence references, dimension of conflict, status, and any evidence-backed resolution rationale.

### Verification result

An immutable result from a named/versioned check: target, method, outcome, details, timestamps, and relevant thresholds. Examples include source identity, unit, number, date, period, freshness, arithmetic, and cross-source consistency.

## Minimum traceability fields

Future persisted/serialized representations should cover, directly or through references:

```text
research_run_id
company_id, company_name, ticker, exchange, country
claim_id, claim, claim_type, value, unit, currency, reporting_period
source_id, source_name, source_type, source_url_or_reference
source_date, retrieved_at, evidence_id, evidence_locator
confidence_score, verification_status, freshness_status
contradiction_status, created_at, schema_version
```

Not every field belongs in one record. Normalize to avoid duplicating source facts and preserve stable identifiers.

## Quantitative evidence

Store raw text/value, normalized numeric value, scale, unit, currency, sign convention, period start/end, instant-versus-duration semantics, fiscal context, as-of time, restatement/amendment status, and calculation lineage. Derived ratios reference input evidence and formula version.

## Time model

Keep distinct:

- event/valid time: when a fact applied;
- reporting period: the financial interval or instant;
- source publication/filing time;
- retrieval time;
- verification time;
- superseded/amended time.

This separation enables freshness checks and future “what changed?” comparisons without rewriting history.

## Confidence and quality

Confidence must be explainable and computed from factors such as source authority, directness, independent corroboration, freshness, extraction quality, validation outcomes, and unresolved contradictions. It is not the model's subjective probability. Store the score version and contributing factors; “unknown” is preferable to false precision.

## Evidence graph and stores

- PostgreSQL is the planned canonical store for run, claim, source, evidence, relationship, and verification metadata.
- Raw/source content uses a governed source store with integrity hashes.
- pgvector holds embeddings for governed chunks referencing canonical source/evidence records.
- Redis is not a durable evidence store.
- Graph traversal may begin relationally; adopting a separate graph database requires evidence and an ADR.

## Immutability and correction

Raw acquired content and verification events should be append-oriented. Corrections create new versions and `supersedes`/`amends` links instead of destructive replacement. Deletion/retention requirements may remove content while retaining permissible audit tombstones.

## Information classes

The platform must keep these classes distinct in storage, APIs, evaluation, and presentation:

- **Fact:** a normalized quantitative or qualitative assertion directly supported by one or more acquired evidence items. A fact carries source, time, verification, freshness, and contradiction state. “Fact” does not mean infallible; conflicts and amendments remain attached.
- **Model interpretation:** model-assisted analysis derived from identified facts and evidence. It must link to its inputs, identify uncertainty, and never become a source or primary evidence merely because a model generated it.
- **Research Finding:** a verification-aware result that selects or combines Claims and interpretations for a research question while preserving evidence links, conflict state and qualifications.
- **Final synthesis or conclusion:** a user-facing composition of verified facts and clearly labeled interpretations. It inherits citations and qualifications from its inputs and cannot promote an unsupported interpretation into a fact.

These classes require explicit type/provenance metadata. Generated language is never primary evidence, and a final answer or report is not a source for a later run unless the underlying evidence is independently resolved.

## Provenance rules

- Every Evidence item resolves to exactly identified Source content and a reproducible locator or calculation lineage.
- A Claim is an assertion to evaluate; it is neither a Source nor Evidence by itself.
- Derived values reference all input Evidence and a named/versioned deterministic formula.
- Model output may interpret Evidence but cannot manufacture a Source, locator, verification result or authoritative citation.
- Citations resolve through Evidence to the actual Source; citing a prior synthesis without its underlying Evidence is citation laundering and is prohibited.
- Conflicting Evidence remains attached to competing Claims or versions. A selected Finding records why and never deletes the conflict.
- Missing authoritative support, unresolved contradiction, staleness and extraction uncertainty reduce quality/confidence and remain visible.
- Unsupported material is excluded from final conclusions/reports or explicitly labeled unverified; it must never enter silently.

Confidence is a transparent quality/coverage signal, not truth, probability of investment success or permission to trade.

## Synthesis contract

Synthesis consumes verified claim/evidence views, never anonymous prose blobs. Every material statement must resolve to evidence or be labeled as inference. Unsupported, stale, or contradictory claims carry visible qualifiers. Language rendering occurs after canonical evidence normalization.

## Deferred schema decisions

Exact identifiers, SQL tables, JSON schemas, graph queries, evidence excerpt storage, retention periods, score formula, and chunking/embedding details belong to later phases and require migration/versioning plans.
