# API Examples

This document captures the validated deterministic demo path for the project. All examples below use the project’s supported Apple fixture-backed flow and are intended for demonstration, not claims of live market data.

## Important API notes

- `/openapi.json` is available and returns the live API schema for the app.
- `/docs` currently returns 404 and should not be described as enabled.
- The validated demo path is deterministic and fixture-backed.
- Live external financial data is not being claimed in the current demo.

## Health

- Method: GET
- Endpoint: `/health`
- Sample request: `curl http://127.0.0.1:8000/health`
- Expected status: `200`
- Example response:

```json
{
  "status": "ok",
  "service": "agentic-financial-intelligence",
  "version": "0.1.0"
}
```

Explanation: Confirms the application process is live.

## Readiness

- Method: GET
- Endpoint: `/ready`
- Sample request: `curl http://127.0.0.1:8000/ready`
- Expected status: `200`
- Example response:

```json
{
  "status": "ready",
  "service": "agentic-financial-intelligence",
  "version": "0.1.0",
  "checks": [
    { "name": "application", "ready": true, "detail": "application foundation loaded" },
    { "name": "configuration", "ready": true, "detail": "development_configuration_validated" }
  ]
}
```

Explanation: Confirms the app and configuration are ready for the validated local demo path.

## Version

- Method: GET
- Endpoint: `/version`
- Sample request: `curl http://127.0.0.1:8000/version`
- Expected status: `200`
- Example response:

```json
{
  "service": "agentic-financial-intelligence",
  "version": "0.1.0",
  "environment": "development"
}
```

Explanation: Returns application metadata.

## Company resolution

- Method: GET
- Endpoint: `/companies/resolve?q=Apple`
- Sample request: `curl "http://127.0.0.1:8000/companies/resolve?q=Apple"`
- Expected status: `200`
- Example response:

```json
{
  "query": { "raw_query": "Apple", "country": null, "exchange": null, "ticker": null },
  "status": "RESOLVED",
  "matched_by": "exact_alias",
  "confidence": "exact",
  "normalized_query": "apple",
  "message": "company resolved",
  "company": {
    "company_id": "22222222-2222-4222-8222-222222222001",
    "legal_name": "Apple Inc.",
    "display_name": "Apple",
    "country": "US",
    "sector": "Information Technology",
    "industry": "Consumer Electronics"
  }
}
```

Explanation: Resolves the deterministic Apple identity using the project’s supported fixture-backed company catalog.

## Market snapshot

- Method: GET
- Endpoint: `/market/snapshot?q=Apple&exchange=NASDAQ`
- Sample request: `curl "http://127.0.0.1:8000/market/snapshot?q=Apple&exchange=NASDAQ"`
- Expected status: `200`
- Example response:

```json
{
  "status": "degraded",
  "message": "market observations are stale",
  "data_origin": "fixture",
  "provider_name": "fixture",
  "resolution": {
    "status": "RESOLVED",
    "company_id": "22222222-2222-4222-8222-222222222001"
  }
}
```

Explanation: Demonstrates the deterministic market snapshot path and explicitly exposes stale fixture status instead of pretending live market accuracy.

## Financial snapshot

- Method: GET
- Endpoint: `/financials/snapshot?q=Apple&exchange=NASDAQ`
- Sample request: `curl "http://127.0.0.1:8000/financials/snapshot?q=Apple&exchange=NASDAQ"`
- Expected status: `200`
- Example response:

```json
{
  "status": "ok",
  "message": "financial snapshot computed",
  "provider_name": "fixture",
  "data_origin": "fixture",
  "package": {
    "company_id": "22222222-2222-4222-8222-222222222001",
    "currency": "USD"
  }
}
```

Explanation: Returns a deterministic financial summary with fixture provenance, not current live financial data.

## News/events snapshot

- Method: GET
- Endpoint: `/news/events/snapshot?q=Apple&exchange=NASDAQ`
- Sample request: `curl "http://127.0.0.1:8000/news/events/snapshot?q=Apple&exchange=NASDAQ"`
- Expected status: `200`
- Example response:

```json
{
  "status": "ok",
  "message": "news/event snapshot computed",
  "provider_name": "fixture",
  "data_origin": "fixture",
  "package": {
    "company_id": "22222222-2222-4222-8222-222222222001",
    "events": [
      { "event_type": "earnings", "title": "Apple reports fiscal Q4 results" }
    ]
  }
}
```

Explanation: Demonstrates the project’s news/event layer using fixture data and source-backed event metadata.

## Industry context

- Method: GET
- Endpoint: `/industry/context/snapshot?q=Apple&exchange=NASDAQ`
- Sample request: `curl "http://127.0.0.1:8000/industry/context/snapshot?q=Apple&exchange=NASDAQ"`
- Expected status: `200`
- Example response:

```json
{
  "status": "ok",
  "message": "industry context snapshot computed",
  "provider_name": "fixture",
  "data_origin": "fixture",
  "package": {
    "company_id": "22222222-2222-4222-8222-222222222001",
    "industry": {
      "canonical_label": "Consumer Electronics",
      "taxonomy_source": "reference"
    }
  }
}
```

Explanation: Shows deterministic industry classification plus evidence-aware catalog structure.

## Regulatory events

- Method: GET
- Endpoint: `/regulatory/events/snapshot?q=Apple&exchange=NASDAQ`
- Sample request: `curl "http://127.0.0.1:8000/regulatory/events/snapshot?q=Apple&exchange=NASDAQ"`
- Expected status: `200`
- Example response:

```json
{
  "status": "ok",
  "message": "regulatory snapshot computed",
  "provider_name": "fixture",
  "data_origin": "fixture",
  "package": {
    "company_id": "22222222-2222-4222-8222-222222222001",
    "events": [
      { "regulator": "SEC", "jurisdiction": "US", "status": "alleged" }
    ]
  }
}
```

Explanation: Demonstrates the regulatory snapshot path while keeping the content clearly fixture-backed and not mistaken for current legal reporting.

## Research plan

- Method: POST
- Endpoint: `/research/plans`
- Sample request:

```json
{
  "q": "Apple",
  "country": "US",
  "exchange": "NASDAQ",
  "ticker": "AAPL",
  "objective": "comprehensive_equity_research",
  "objective_text": "Evaluate Apple fundamentals, risks, and catalysts.",
  "jurisdiction": "US",
  "time_horizon_days": 365
}
```

- Expected status: `200`
- Example response:

```json
{
  "status": "ok",
  "message": "research plan created (not executed)",
  "objective": "comprehensive_equity_research",
  "resolution": {
    "status": "RESOLVED",
    "company_id": "22222222-2222-4222-8222-222222222001"
  }
}
```

Explanation: Plans a deterministic, bounded research path for the validated Apple company without executing the full research loop.

## Research execution

- Method: POST
- Endpoint: `/research/execute`
- Sample request: same as the research plan request above
- Expected status: `200`
- Example response:

```json
{
  "status": "partial",
  "message": "required tasks finished with PARTIAL capability results and/or optional task failures",
  "objective": "comprehensive_equity_research",
  "completed_count": 5,
  "failed_count": 0,
  "partial_count": 1,
  "warnings": [
    "task ... completed with PARTIAL result (downstream deps may proceed; completeness not claimed)"
  ]
}
```

Explanation: Demonstrates the bounded execution model. The partial status is a valid, honest result and should be presented as such in the demo.

## Research synthesis

- Method: POST
- Endpoint: `/research/synthesis`
- Sample request: see [examples/sample_research_request.json](../examples/sample_research_request.json) and the Apple synthesis sample in the same examples folder.
- Expected status: `200`
- Example response: see [examples/sample_research_response.json](../examples/sample_research_response.json)

Explanation: The synthesis endpoint verifies the supplied claim evidence and returns a deterministic structured research synthesis with citations and explicit stale/insufficient semantics when a claim is older than the supported fixture context.

## Controlled validation/error examples

### Empty company query

- Method: GET
- Endpoint: `/companies/resolve?q=   `
- Expected status: `400`
- Example response:

```json
{
  "error": {
    "code": "invalid_company_query",
    "message": "query is empty"
  }
}
```

### Invalid objective

- Method: POST
- Endpoint: `/research/execute`
- Sample request:

```json
{
  "q": "Apple",
  "objective": "not_a_real_objective"
}
```

- Expected status: `400`
- Example response:

```json
{
  "error": {
    "code": "invalid_research_execution_query",
    "message": "'not_a_real_objective' is not a valid ResearchObjective"
  }
}
```

Explanation: Control failure cases are deterministic and intentionally surface validation errors rather than fabricating a result.
