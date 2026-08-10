# Phase 10 Threat Model

## Scope and method

This STRIDE-informed review covers the current modular FastAPI service, selected `/v1` aliases,
in-process MCP facade, deterministic research/evaluation/report paths, container foundation, and
local operations. It does not certify a public cloud, multi-tenant system, durable database,
distributed workers, external identity provider, or production network.

## Assets

- canonical company/security/listing identity;
- source evidence, citations, verification/confidence/conflict state, and research-run traceability;
- workflow/memory/watchlist state (currently process-local);
- report content and filename/base64 artifact integrity;
- credentials/configuration, paid-model prohibition, logs/correlation data, source code, build
  inputs, and release artifacts.

## Trust boundaries and entry points

1. Client → ASGI boundary: Host, headers, query, JSON body, and correlation metadata are untrusted.
2. REST/MCP delivery → application: only typed/allowlisted commands may cross.
3. External source/provider → adapters: optional content is untrusted, bounded, and not control.
4. Verification → synthesis/report: only typed Phase 8 results may become qualified output.
5. Process → filesystem/container/operations: reports remain in memory; environment and image inputs
   are deployment-controlled.
6. Build/CI → artifact: registries, base images, packages, and Actions are supply-chain inputs.

Threat actors include unauthenticated/malicious clients, compromised sources, malicious retrieved
content, accidental operators, compromised dependencies/build services, and clients attempting
identity or investment-policy manipulation.

## Threat/control mapping

| Threat / abuse case | Current control | Test/evidence | Residual risk |
|---|---|---|---|
| Host spoofing, duplicate/ambiguous headers | Exact production allowlist; duplicate Host/Content-Length rejection; bounded exact parsing | Prompt 2–3 header tests | Proxy trust is undefined; direct Host must be preserved. |
| Oversized/malformed bodies and chunk exhaustion | Declared/actual byte limit, 1024-chunk limit, strict Content-Length, safe JSON errors | Prompt 1–3 boundary tests and evaluation | Request-rate DoS is not controlled. |
| Correlation/log injection | Exact bounded correlation syntax, UUID replacement, route templates, static messages, secret-key redaction | Prompt 1–3 logging/correlation tests | External log transport/retention/access is undeployed. |
| Secret leakage | Blank examples, `SecretStr`, safe log context/errors/MCP status, no exception message/stack | Settings, logging, MCP negative and credential-signature scans | Operator environment and future external tooling remain deployment risks. |
| Path traversal/arbitrary report writes | Report API accepts no path; sanitized deterministic filename; in-memory/base64 artifacts | Phase 9 report and Phase 10 path-injection tests | Future durable artifact storage needs a new boundary review. |
| Prompt/tool injection | Retrieved strings stay data; static MCP allowlist and explicit dispatch; no dynamic tool discovery | Phase 8–10 injection/evaluation tests | Future model/tool integrations would add a new boundary. |
| Company/listing confusion | Canonical issuer/security/listing contracts and explicit exchange constraints | Apple, Reliance NSE/BSE, GOOG/GOOGL evaluations | Reference catalog is intentionally limited/demo-scale. |
| Verification/confidence bypass | Phase 8 recomputation and verified-claim gate; conflicts/stale/missing preserved | Phase 8–9 contract suites and Phase 10 evaluations | Typed claim production is supplied by caller; broader live-source evaluation is limited. |
| Workflow abuse/auto-approval | Typed transitions and explicit approval policy; MCP exposes no workflow mutation | Phase 7 suites and MCP negative tests | REST authentication/authorization is deferred; public exposure is prohibited. |
| MCP capability escalation | Two-tool immutable allowlist; bounded arguments; read-only/offline descriptors; no server/SDK | Prompt 3A interface/source audit | Facade is in-process contract, not remotely authenticated protocol exposure. |
| Unsafe file/network/command execution | MCP and report paths contain no eval/exec/shell/subprocess/open/fetch; optional providers use bounded adapters | AST/runtime primitive scans | Existing opt-in provider network risks remain governed by adapter controls. |
| Paid-model bypass | Settings reject `ALLOW_PAID_MODELS=true`; no LLM/OpenRouter runtime call | Settings/repository/Phase 10 scans | Future model integration requires a separate cost/security gate. |
| Denial of service | Byte/chunk/collection/pagination bounds and finite request-local buffers | Boundary and local-load tests | No request-rate limiter, autoscaling, WAF, or public-edge protection. |
| Unsafe deployment configuration | Production host/log/provider/paid policy fails closed; non-root/read-only/no-new-privileges container foundation | Config tests and local container smoke | TLS, proxy, secrets, auth, network policy, and cloud topology are undecided. |
| Dependency/build compromise | Minimal constrained manifest, no new dependency, `pip check`, reviewed Docker/CI inputs | Supply-chain review | No lock/SBOM/CVE/container scan; base/Actions are not digest/commit pinned. |

## Security acceptance and residual risks

Current deterministic controls mitigate the tested boundary and research-integrity threats. They do
not make an unauthenticated public deployment acceptable. Before public exposure, approve and test
an identity/authorization model, request-rate controls, TLS/proxy/network policy, managed secrets,
monitoring/retention, and incident ownership. Before release, resolve the recorded supply-chain
scanner limitation or explicitly accept it with owner/security approval.
