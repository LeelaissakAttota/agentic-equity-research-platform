"""Finite local-only Phase 10 reliability and load evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.composition import build_container
from tests.unit.test_phase9_prompt2_hardening import NOW
from tests.unit.test_phase10_prompt2_hardening import _settings
from tests.unit.test_synthesis_api import (
    APPLE_COMPANY_ID,
    APPLE_LISTING_ID,
    APPLE_SECURITY_ID,
    _body,
    _claim,
)


def test_fifty_sequential_foundation_requests_have_zero_failures_and_unique_ids() -> None:
    correlation_ids: set[str] = set()
    with TestClient(create_app(settings=_settings())) as client:
        for index in range(50):
            path = ("/v1/health", "/v1/ready", "/v1/version")[index % 3]
            response = client.get(path)
            assert response.status_code == 200
            correlation_ids.add(response.headers["X-Correlation-ID"])

    assert len(correlation_ids) == 50


def test_thirty_two_concurrent_resolution_requests_are_isolated_and_correct() -> None:
    with TestClient(create_app(settings=_settings())) as client:

        def resolve(index: int) -> tuple[int, str, str]:
            correlation_id = f"local-load-{index}"
            response = client.get(
                "/v1/companies/resolve",
                params={"q": "Apple", "exchange": "NASDAQ"},
                headers={"X-Correlation-ID": correlation_id},
            )
            return (
                response.status_code,
                response.headers["X-Correlation-ID"],
                response.json()["company"]["company_id"],
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(resolve, range(32)))

    assert all(status == 200 for status, _, _ in outcomes)
    assert {correlation for _, correlation, _ in outcomes} == {
        f"local-load-{index}" for index in range(32)
    }
    assert {company_id for _, _, company_id in outcomes} == {APPLE_COMPANY_ID}


def test_twenty_repeated_synthesis_requests_are_deterministically_identical() -> None:
    claim = _claim(
        company_id=APPLE_COMPANY_ID,
        company_name="Apple",
        currency="USD",
        security_id=APPLE_SECURITY_ID,
        listing_id=APPLE_LISTING_ID,
        source_id="SEC-EDGAR",
        provider="SEC EDGAR",
        url="https://www.sec.gov/Archives/apple-fy2026",
    )
    body = _body(q="Apple", country="US", exchange="NASDAQ", ticker="AAPL", claim=claim)
    container = build_container(_settings(), clock=lambda: NOW)
    outputs: list[dict[str, object]] = []
    with TestClient(create_app(container=container)) as client:
        for _ in range(20):
            response = client.post(
                "/v1/research/synthesis",
                json=body,
                headers={"X-Correlation-ID": "reliability-synthesis"},
            )
            assert response.status_code == 200
            outputs.append(response.json())

    assert outputs and all(output == outputs[0] for output in outputs)


def test_twelve_workflow_create_execute_cycles_preserve_state_isolation() -> None:
    container = build_container(_settings(), clock=lambda: NOW)
    workflow_ids: set[str] = set()
    with TestClient(create_app(container=container)) as client:
        for index in range(12):
            company = "Apple" if index % 2 == 0 else "Reliance"
            exchange = "NASDAQ" if company == "Apple" else "NSE"
            created = client.post(
                "/research/workflows",
                json={"q": company, "exchange": exchange, "objective": "market_analysis"},
            )
            assert created.status_code == 200
            workflow_id = created.json()["workflow_id"]
            workflow_ids.add(workflow_id)
            executed = client.post(f"/research/workflows/{workflow_id}/execute")
            assert executed.status_code == 200
            assert executed.json()["workflow"]["status"] == "completed"

    assert len(workflow_ids) == 12
