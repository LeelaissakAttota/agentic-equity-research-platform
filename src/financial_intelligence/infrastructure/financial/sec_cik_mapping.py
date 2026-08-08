"""US SEC CIK mapping for canonical company IDs (infrastructure-only)."""

from __future__ import annotations

from financial_intelligence.domain.identity import CompanyId

# Demo-scale mapping: Apple only in Prompt 1. CIK is zero-padded to 10 digits for URLs.
_US_SEC_CIK: dict[str, str] = {
    "22222222-2222-4222-8222-222222222001": "0000320193",  # Apple Inc.
}


def sec_cik_for_company(company_id: CompanyId) -> str | None:
    """Return SEC CIK for a known US issuer, or None when unsupported."""

    return _US_SEC_CIK.get(company_id.as_text())
