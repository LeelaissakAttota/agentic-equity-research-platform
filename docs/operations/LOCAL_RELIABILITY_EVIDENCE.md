# Local Reliability and Load Evidence

Classification: **LOCAL DEVELOPMENT EVIDENCE ONLY**. This is not a production throughput, latency,
availability, capacity, or internet-scale claim.

## Reproducible budget

`tests/evaluation/test_phase10_local_reliability.py` executes:

- 50 sequential `/v1/health|ready|version` requests: 50 successes, 0 failures, 50 distinct generated
  correlation IDs;
- 32 concurrent Apple/NASDAQ resolutions with eight local worker threads: 32 successes, 0 5xx,
  32 preserved caller correlation IDs, one canonical company ID;
- 20 repeated verified Apple syntheses with a fixed clock/correlation: 20 successes and identical
  structured outputs;
- 12 alternating Apple/Reliance workflow create/execute cycles: 12 unique workflow IDs, 12 completed
  workflows, 0 unexpected failures.

Total representative operations: **114**. The pytest suite passed **4/4** reliability/load tests.
Body-byte/chunk bypass, malformed/oversized input, concurrency, store isolation, and request-state
retention are additionally covered by the Phase 7 and Phase 10 unit/contract suites.

## Limitations

The run uses local in-process TestClient, fixture data, one process, no TLS/proxy/WAF, no external
providers, no network latency, no durable database/cache, and no multi-host workers. It measures
deterministic correctness/isolation under a finite budget, not peak load or a production SLO.
