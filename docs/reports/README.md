# Report Documentation

This directory owns the frozen conceptual contract for future Microsoft Word research artifacts. No renderer or template is implemented in Phase 0.

## Artifact contract

- Primary artifact: `.docx` generated from a versioned report model.
- Every report links to its `research_run_id`, canonical Company Identity, research/as-of date, synthesis version and generation metadata.
- The reporting adapter consumes governed findings/evidence; it never calls source providers directly.
- Charts, tables and images may be embedded where they improve understanding and retain data/evidence lineage.
- Filenames are sanitized and output paths are constrained.

## Planned section structure

1. Cover Page, Research Run ID, Company Identity and Research Date
2. Executive Summary, Company Overview and Business Model
3. Market Performance and Valuation
4. Financial Performance, Income Statement, Balance Sheet, Cash Flow and Financial Ratios
5. Filings, Recent News, Corporate Events and New Projects/Investments
6. Regulatory Developments, Industry Analysis and Competitor Comparison
7. Risk Analysis, Opportunities and evidence-supported Bull/Base/Bear scenarios
8. Key Findings and Research Quality/Confidence
9. Evidence and Sources/Citations

Unsupported sections are omitted or marked unavailable; missing data is never filled with generated facts.

## Content classifications

Reports must visually or semantically distinguish:

- **Fact:** supported by resolvable evidence and verification context.
- **Analysis:** deterministic or model-assisted interpretation derived from cited facts.
- **Opinion / model interpretation:** explicitly labeled reasoning with uncertainty.
- **Unverified information:** visible provisional material that cannot be presented as a conclusion.

Generated `.docx`, charts and derived artifacts belong under ignored output paths unless an explicit, reviewed fixture is required.
