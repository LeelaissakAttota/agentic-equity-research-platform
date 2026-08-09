# Phase 9 Prompt 1 Scope Contract

## Status

- **Phase:** 9 — Conversational Research, Multilingual Output & Word Reports
- **Prompt:** 1 — Conversational Research Synthesis & Reporting Foundation
- **Authorization:** Owner authorized
- **Delivery state:** In progress; local and uncommitted until owner review

## Objective

Establish a deterministic synthesis boundary that converts Phase 8 verified claim artifacts into structured, evidence-linked research output without weakening identity, provenance, verification, confidence, conflict, freshness, uncertainty, or missing-data semantics.

## In scope

- typed synthesis, section, research-claim, citation, confidence, contradiction, and missing-data contracts;
- an explicit gate from Phase 8 `VerificationResult` objects to presentation-safe research claims;
- stable section ordering and a bounded, traceable executive-summary foundation;
- canonical company/security/listing preservation, including dual listings and share classes;
- English-default language/locale preferences that are ready for Telugu and Hindi renderers later;
- structured JSON/Markdown report-generation contracts behind a port;
- a minimal synthesis application use case and one `POST /research/synthesis` endpoint;
- offline Apple, Reliance, GOOG/GOOGL, hostile-content, architecture, and API tests.

## Explicitly out of scope

- polished DOCX or PDF rendering, Streamlit, charts, and report layout;
- translation APIs, LLM translation, arbitrary conversational agents, or autonomous follow-up research;
- new planners, calculations, providers, live-data expansion, RAG, vectors, embeddings, LangGraph, or distributed workers;
- MCP production exposure, notification channels, trading, investment recommendations, and Phase 10 work.

## Foundation rules

- Phase 8 verification output is required; synthesis never self-asserts verification.
- Unverified, stale, contradicted, and conflicting claims remain explicitly qualified.
- Every material output item retains claim and evidence identifiers.
- Missing values are never converted to zero or fabricated prose.
- External evidence text remains inert data and cannot change policy or invoke behavior.
- Runtime OpenRouter calls, LLM calls, paid calls, and mandatory external API cost remain zero.
- Prompt 1 is not a Git checkpoint: no staging, commit, or push.
