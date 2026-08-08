# Roadmap

The roadmap communicates sequencing and outcomes. Detailed scope and gates are in `PHASES.md`. Dates are not promised until the dependencies and provider constraints of a phase are investigated.

This Phase 0–10 sequence is frozen by the Master Architecture review. Adding, removing, merging or materially reordering phases requires explicit owner approval and a recorded architectural decision.

| Phase | Name | Intended outcome | Depends on |
|---|---|---|---|
| 0 | Project Constitution & Repository Bootstrap | Governed repository, target architecture, policies, phase plan, and health baseline | Owner vision |
| 1 | Core Application Foundation | Runnable skeletal service with configuration, lifecycle, logging, error contracts, composition, security and delivery foundations—without financial intelligence | Phase 0 accepted |
| 2 | Company Resolution & Source Foundation | Provider-neutral identity resolution and authoritative-source acquisition contracts | Phase 1 accepted |
| 3 | Market Intelligence | Traceable price/volume/history/statistics and deterministic market calculations | Phase 2 accepted |
| 4 | Financial & Filing Intelligence | Parsed filings, normalized statements, ratios, trends, and filing evidence | Phase 3 accepted |
| 5 | News, Events, Industry & Regulatory Intelligence | Evidence-backed qualitative research across replaceable sources | Phase 4 accepted |
| 6 | Autonomous Research Planning & Dynamic Orchestration | Intent-driven plans, dependency-aware execution, monitoring, and bounded recovery | Phase 5 accepted |
| 7 | Evidence Graph, RAG & Research Memory | Hybrid retrieval, claim/source relationships, governed memory, and change comparisons | Phase 6 accepted |
| 8 | Verification, Confidence & Reflection | Deterministic verification, conflicts, quality scoring, critic loop, and targeted re-research | Phase 7 accepted |
| 9 | Conversational Research, Multilingual Output & Word Reports | Follow-up research, English/Telugu presentation, visuals, and professional DOCX artifacts | Phase 8 accepted |
| 10 | MCP/API Integration, Evaluation & Production Hardening | Selected MCP exposure, comprehensive evaluation, security/reliability hardening, and deployability evidence | Phase 9 accepted |

## Cross-phase gates

Every phase requires:

- approved scope and architectural decisions;
- automated tests plus documented manual validation where appropriate;
- security, cost, provenance, and observability review;
- updated documentation, status, and changelog;
- no unresolved critical failures;
- explicit owner acceptance before the next phase begins.

## Release posture

Early phases are internal foundations, not production releases. Production-readiness claims require Phase 10 evidence. Provider availability, legal/terms review, and model-free-tier availability remain operational constraints throughout the roadmap.
