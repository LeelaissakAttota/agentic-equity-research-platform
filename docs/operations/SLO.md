# Initial Service-Level Objective Foundation

These are **unevaluated production targets**, not historical guarantees. Current measurements are
local deterministic evidence only and cannot establish an internet-scale SLA.

| Signal | Initial target | Measurement/qualification |
|---|---|---|
| Availability | 99.5% monthly for an approved single-region deployment | Requires deployment uptime monitor; not currently measured. Planned maintenance and dependency-wide outages need an approved policy. |
| Unexpected 5xx rate | <1% over a rolling 5-minute window and <0.1% monthly | Count server-error telemetry by static route; client/validation rejections are separate. No production metrics backend exists. |
| Correctness release gate | 100% required deterministic tests/evaluations pass; zero unexplained critical skips | Measured locally/CI before every release. A passing suite is not an availability measurement. |
| Readiness correctness | `/ready` returns ready only when registered required checks pass | Current application/configuration checks are tested. Deployment dependencies must be registered when introduced. |
| Request isolation | Zero correlation/body/workflow cross-request leakage in accepted regression/load evidence | Locally tested; distributed multi-tenant isolation is not claimed. |
| Recovery target | Restore the previous known-good stateless application release within 15 minutes after a declared bad deployment | Target only; requires an environment-specific rollback rehearsal. |
| Data recovery | No durable RPO is claimed | Workflow/memory/watchlist/notification state is in-memory and is lost on restart. Durable recovery remains deferred. |

## Alert/runbook mapping

Future deployment alerts should cover readiness failure, sustained unexpected 5xx, startup failure,
paid-model policy rejection, repeated invalid-host/body abuse, and report/workflow failure rates.
Current structured logs and correlation IDs support investigation, but no dashboard, alert transport,
retention, distributed trace, or production paging system is installed.
