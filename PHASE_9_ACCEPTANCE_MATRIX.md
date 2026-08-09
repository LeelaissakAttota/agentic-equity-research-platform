# Phase 9 Acceptance Matrix

This matrix records the Prompt 3 audit against the owner-authorized Phase 9 implementation. `PARTIAL / DOCUMENTED` and `DEFERRED BY DESIGN` are not represented as completed production capabilities.

| Capability | Classification | Acceptance evidence and limitation |
|---|---|---|
| Verified synthesis | IMPLEMENTED | Typed Phase 8 results are revalidated through the canonical deterministic engine; unsupported, contradicted, conflicting, stale, and low-authority material claims cannot silently become facts. |
| Citations and provenance | IMPLEMENTED | Claim/evidence/source IDs, provider, authority, origin, URL/locator when supplied, publication/retrieval/as-of time, company/security/listing, and reference ID survive synthesis and every report format. |
| Conflicts | IMPLEMENTED | Supporting and contradicting evidence remain visible across sections, summary context, JSON, Markdown, and DOCX; no last-write-wins or authority erasure. |
| Confidence | IMPLEMENTED | Phase 8 score/version/factors are preserved per claim; no report-wide aggregate or evidence-duplication uplift is introduced by Phase 9. |
| Stale and missing data | IMPLEMENTED | Market currentness, historical financial periods, Phase 8 stale status, and seven distinct missing states remain separate; missing is never rendered as zero. |
| Section taxonomy | IMPLEMENTED | Stable bounded ordering covers company, market, financial, news/events, industry, competition, regulatory, and risk; absent sections are explicitly unavailable in reports. |
| Executive summary | IMPLEMENTED | Bounded deterministic selection, claim/citation traceability, conflict/absence visibility, and no advice/guarantee/target language. |
| Structured JSON | IMPLEMENTED | Stable semantic metadata, synthesis, sections, omissions, citations, as-of context, and per-claim verification/confidence. |
| Markdown | IMPLEMENTED | Stable readable hierarchy with inert HTML/Markdown escaping, unavailable sections, conflicts, missing data, and sources. |
| DOCX | IMPLEMENTED | Deterministic minimal OOXML package with cover metadata, sections, evidence linkage, confidence/conflicts/missing/sources, safe filename, base64 transport, and no file writes. Package/XML validity is tested; advanced visual template testing is deferred. |
| Language preferences | PARTIAL / DOCUMENTED | English/Telugu/Hindi code and locale contracts are preserved. Narrative translation is explicitly `not_applied`; no translated narrative quality is claimed. |
| Apple and Reliance goldens | IMPLEMENTED | Semantic—not whitespace—goldens preserve Apple/AAPL/NASDAQ/USD and Reliance/NSE/BSE/INR/India authority; Reliance/NASDAQ fails safely. |
| Identity and share classes | IMPLEMENTED | Canonical Phase 2 company/security/listing identity is reused; GOOG and GOOGL remain distinct securities/listings under one issuer. |
| Prompt injection and hostile content | IMPLEMENTED | Evidence remains inert; HTML/scripts are escaped; unknown policy/verification fields are rejected; no tool, command, secret, or investment action can be invoked. |
| API | IMPLEMENTED | Exactly one bounded POST synthesis endpoint, canonical resolution, correlation ID, safe errors, stable response, and optional in-memory report artifact. |
| Architecture | IMPLEMENTED | Domain → application/ports → infrastructure → API/composition direction is preserved; domain has no FastAPI/report/provider SDK dependency. |
| Security | IMPLEMENTED | No arbitrary execution, fetching, output paths, or report file writes; URLs remain validated source metadata; filenames are sanitized. |
| Cost and dependencies | IMPLEMENTED | Runtime LLM/OpenRouter/paid/external calls: 0; mandatory external cost: $0; DOCX adds no dependency. `ALLOW_PAID_MODELS=false` remains fail-closed. |
| Determinism | IMPLEMENTED | Stable synthesis IDs, ordering, JSON, Markdown, DOCX bytes, ZIP entry order/timestamps, and semantic goldens. |
| Report readiness | IMPLEMENTED | JSON, Markdown, and minimal professional DOCX are structurally valid and evidence-linked. Advanced branding, charts, and visual Word-render regression remain deferred enhancements. |

## Cross-phase reuse audit

| Prior phase | Phase 9 reuse status |
|---|---|
| Phase 2 identity | IMPLEMENTED — canonical issuer/security/listing contracts; no parallel identity model. |
| Phase 3 market | PARTIAL / DOCUMENTED — Phase 9 presents verified typed market claims and applies presentation freshness; it does not query providers or recalculate market metrics. |
| Phase 4 financial/filing | PARTIAL / DOCUMENTED — verified values/units/currencies/periods are preserved; Phase 9 does not recalculate ratios or parse filings. |
| Phase 5 qualitative/regulatory | PARTIAL / DOCUMENTED — typed verified claims map to bounded sections; Phase 9 does not reacquire or reinterpret source corpora. |
| Phase 6 orchestration | PARTIAL / DOCUMENTED — research-run identity is preserved; automatic plan-to-synthesis conversion remains deferred until upstream tasks emit complete typed claim bundles. |
| Phase 7 workflows/memory | PARTIAL / DOCUMENTED — run/company continuity is preserved; durable artifact/workflow integration is not required for in-memory report correctness. |
| Phase 8 verification | IMPLEMENTED — canonical Claim, EvidenceBundle, VerificationResult, confidence, contradiction, and source vocabularies are reused; Phase 9 does not duplicate scoring formulas. |

## Deferred by design

- Arbitrary conversational follow-up, pronoun/reference resolution, and automatic “what changed?” synthesis.
- Evaluated Telugu/Hindi narrative translation; language preferences remain metadata only.
- Streamlit UI, interactive charts/tables, and visual-report goldens.
- Advanced branded DOCX templates, charts/images, visual Word/LibreOffice render regression, PDF output, and arbitrary user templates.
- Durable artifact registry/storage, database-backed synthesis/report history, distributed workers, and notifications.
- Automatic Phase 3–7 snapshot/workflow-to-typed-claim conversion and report-side provider acquisition.
- Broader live provider/corpus coverage and production provider legal/terms review.
- LLM/OpenRouter synthesis or translation, LangGraph, embeddings, RAG/vector memory, and model-based sentiment.
- MCP production exposure, deployment hardening, load/soak testing, auth/rate limiting, operational SLOs, and other Phase 10 work.

## Blocking determination

There is no blocking gap in the owner-authorized Phase 9 closure boundary. DOCX was required by the frozen phase definition and is implemented minimally and deterministically. The listed partial/deferred capabilities must not be presented as implemented. Prompt 4 pre-release validation and documentation gates passed; Git staging/commit/push remain separately owner-gated.
