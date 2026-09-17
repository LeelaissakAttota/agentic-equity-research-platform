# F06 — Docker Compose Exposed on All Interfaces: Audit & Remediation Plan

**Status: AUDIT ONLY. No source, test, Docker/Compose, or configuration files were modified for this audit.**

## 1. Executive Summary

The project's single `docker-compose.yml` publishes the `api` service's port with `"${API_HOST_PORT:-8000}:8000"` — a short-syntax port mapping with **no host IP specified**. This was independently reproduced, not just read from YAML: `docker compose up` followed by `docker inspect` shows the container's port bound to `HostIp: "0.0.0.0"` and `HostIp: "::"` (all IPv4 and all IPv6 interfaces). A live functional test confirmed the service answers HTTP requests not only on `127.0.0.1:8000` but also on the host's actual Wi-Fi LAN interface address (`10.205.73.233:8000`), including application endpoints (`/research/workflows`, `/companies/resolve`) with **no Authorization header** — because this exact Compose file also sets `APP_ENV=development`, which disables both the API-key authentication dependency and the `ALLOWED_HOSTS` enforcement middleware in this codebase.

This is a real, reproduced network-exposure finding, not a theoretical one: any device that can route to the host's LAN (or VPN mesh — a Tailscale interface was also present and would carry the same exposure) can reach the full unauthenticated API surface for as long as the container runs, subject only to host firewall/NAT policy outside this project's control.

However, per the project's own documentation (`DEPLOYMENT_PLAN.md`, `docs/development/README.md`), this Compose file is explicitly a **local development / release-candidate convenience configuration**, not a production deployment artifact — production hosting is documented as "undecided" and gated behind a separate, not-yet-built deployment path. There is no production or CI Compose variant to compare against, and no evidence the project intends this exact file to be run on a shared or production host. The defect is therefore best characterized as a **local-dev hardening gap with real (not merely theoretical) LAN exposure risk**, not a production misconfiguration — but it is squarely a defect: a project whose own docs say "do not publicly expose the service" ships a compose file that binds the service to every interface by default, with no loopback-restricted alternative offered anywhere.

**Verdict: CONFIRMED.**

## 2. Scope

In scope:
- `docker-compose.yml` (the only Compose file in the repository)
- `Dockerfile` (the only Dockerfile in the repository)
- `src/financial_intelligence/security/auth.py` and `src/financial_intelligence/api/app.py`/`middleware.py` (authentication and host-enforcement behavior, insofar as they determine whether the exposed port is protected)
- `docs/development/README.md`, `DEPLOYMENT_PLAN.md`, `docs/operations/DEPLOYMENT_EVIDENCE.md` (documented intent for this configuration)
- Existing test suite, searched for any Docker/Compose/port-binding coverage

Out of scope / not touched: F01–F05 fixes (verification engine, evidence, cancellation, exception leakage, SEC filing-date handling) — confirmed untouched by this audit (see §3).

## 3. Baseline

- Branch: `main`
- HEAD commit: `d983bcea152488c1005168c22f2766fc9dd24056` ("feat(phase-11.2): implement API key authentication foundation")
- Working tree: identical to the F05 end state — the same pre-existing F01–F05 modified/untracked files, no new modifications from this audit. Verified via `git status --short` before and after.
- Test baseline (re-run at start of this audit): **785 passed, 130 subtests passed**
- Ruff (`src tests`): **All checks passed**
- Docker: available in this environment (`Docker version 29.8.0`, `Docker Compose v5.5.1`) — used for live reproduction (§6–§7), then fully torn down (`docker compose down`) so no container is left running.

## 4. Compose Configuration Inventory

| File | Present? | Notes |
|---|---|---|
| `docker-compose.yml` | Yes (repo root) | Only Compose file in the repository. Header comment: "Local v1.0.0 release-candidate Compose configuration." Explicitly states PostgreSQL/Redis are absent because those integrations don't exist yet. |
| `compose.yml` / `compose.yaml` | No | Not present. |
| `docker-compose.override.yml` | No | Not present. No dev/prod/test Compose variants exist. |
| `Dockerfile` | Yes (repo root) | Single multi-stage (`builder` → `runtime`) Dockerfile; only one image is built. |
| Deployment configuration | `DEPLOYMENT_PLAN.md` | A **target plan**, not implemented infrastructure. States production hosting is "undecided" and gated behind Phase 10 hardening (already noted elsewhere as incomplete for auth/rate-limiting/TLS). |
| README/docs referencing compose commands | `docs/development/README.md` | Instructs `docker compose build` / `docker compose up`, with an override example (`$env:API_HOST_PORT=18080`) for when port 8000 is already taken locally — no mention of restricting the bind address. |
| CI workflow | `.github/workflows/ci.yml` | Contains **no** Docker/Compose step at all — `docker compose config` is referenced only in prose in various phase-audit Markdown files as a manual pre-release check, not as an automated CI gate. |

Confirmed: exactly one Compose file, one Dockerfile, one service, no environment-specific variants exist anywhere in the repository.

## 5. Published Port Inventory

| Service | Compose binding (as written) | Host IP | Host port | Container port | Protocol | Environment | Externally reachable? | Purpose |
|---|---|---|---|---|---|---|---|---|
| `api` | `"${API_HOST_PORT:-8000}:8000"` | *(unspecified → defaults to all interfaces)* | `8000` (overridable via `API_HOST_PORT`) | `8000` | tcp | `APP_ENV=development` (hardcoded in the compose file) | **Yes — confirmed reachable on all host interfaces, not just loopback** | FastAPI application: health/readiness/version, company resolution, financial/news/industry/regulatory snapshots, research plan/execute/synthesis, workflow create/list, watchlists |

No other services are defined. The compose file's own header comment confirms PostgreSQL and Redis are "intentionally absent: those integrations are not implemented yet" — so there is no database or cache service to audit for unnecessary host exposure in this codebase today. This directly narrows the reported concern (which anticipated DB/Redis exposure) to a single service: the API itself.

## 6. Actual Network Binding Evidence

Static analysis (`docker compose config`) resolves the port entry with **no `host_ip` key**:

```yaml
ports:
  - mode: ingress
    target: 8000
    published: "8000"
    protocol: tcp
```

The absence of `host_ip` in Compose's normalized output means Docker applies its default bind address, which is **all interfaces** (equivalent to `0.0.0.0:8000:8000` for IPv4).

This was then verified against the **actual running container**, not just the resolved config:

```
$ docker compose up -d
$ docker compose ps
NAME                                                       ...   PORTS
agenticfinancialintelligenceequityresearchplatform-api-1   ...   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp

$ docker inspect agenticfinancialintelligenceequityresearchplatform-api-1 \
    --format '{{json .NetworkSettings.Ports}}'
{"8000/tcp":[{"HostIp":"0.0.0.0","HostPort":"8000"},{"HostIp":"::","HostPort":"8000"}]}
```

Confirmed: the container binds to `0.0.0.0` (all IPv4 interfaces) **and** `::` (all IPv6 interfaces). This is not a theoretical reading of YAML — it is the actual kernel-level socket binding Docker created for this exact compose file.

## 7. Reproduction Steps

Non-destructive, using only local inspection and self-directed HTTP requests (no scanning of other hosts, no firewall/network configuration changes):

```
docker compose build
docker compose up -d
docker compose ps                 # -> 0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
docker inspect <container> --format '{{json .NetworkSettings.Ports}}'
curl http://127.0.0.1:8000/health                    # loopback
Get-NetIPAddress ...                                  # enumerate this host's OWN interfaces (no external scan)
curl http://<this-host's-LAN-IP>:8000/health          # same host, non-loopback interface
curl http://<this-host's-LAN-IP>:8000/research/workflows   # unauthenticated app endpoint
curl http://<this-host's-LAN-IP>:8000/companies/resolve?q=Apple
docker compose down               # clean teardown
```

```
docker compose config
        ↓
published port has no host_ip
        ↓
0.0.0.0:8000 (+ [::]:8000)
        ↓
confirmed via docker inspect / docker compose ps
        ↓
confirmed via curl on 127.0.0.1 AND on the host's own non-loopback LAN IP
```

## 8. Reproduction Evidence (captured output)

```
NAME  ...  PORTS
agenticfinancialintelligenceequityresearchplatform-api-1  ...  0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp

{"8000/tcp":[{"HostIp":"0.0.0.0","HostPort":"8000"},{"HostIp":"::","HostPort":"8000"}]}

loopback 127.0.0.1:8000/health -> HTTP 200
{"status":"ok","service":"agentic-financial-intelligence","version":"1.0.0"}

Host's own non-loopback interfaces (self-inspection only, no external scan):
  10.205.73.233   Wi-Fi
  169.254.83.107  Tailscale
  172.20.32.1     vEthernet (WSL)

via Wi-Fi interface 10.205.73.233:8000/health -> HTTP 200
{"status":"ok","service":"agentic-financial-intelligence","version":"1.0.0"}

GET /research/workflows (no Authorization header) -> HTTP 200
GET /companies/resolve?q=Apple (no Authorization header) -> HTTP 200
```

The container was stopped and removed (`docker compose down`) immediately after evidence was captured; no service was left running.

## 9. Root Cause

`docker-compose.yml` line 14: `"${API_HOST_PORT:-8000}:8000"` uses Compose's short port-mapping syntax without a `host_ip` prefix (e.g. `127.0.0.1:${API_HOST_PORT:-8000}:8000`). Docker Compose's documented default when no host IP is given is to bind on all interfaces. This is a **configuration omission**, not a logic bug in application code — there is no code path that could "silently" restrict this; the binding is exactly what was written.

This is compounded, not caused, by two independent application-level defaults that are both keyed off the same `APP_ENV=development` value hardcoded in this same compose file:

1. `security/auth.py:_ENFORCED_ENVIRONMENTS = frozenset({"production", "staging"})` — `require_api_key` returns immediately (no check) whenever `app_env` is not `production`/`staging`. `development` bypasses authentication entirely.
2. `api/app.py:72` — `enforce_allowed_hosts=resolved_container.settings.app_env == "production"` — the `ALLOWED_HOSTS` host-header check (`middleware.py`) is only active in `production`; in `development` it is a no-op.

So the same three-line combination (`APP_ENV: development` + unrestricted `ports:` + no override file) simultaneously (a) opens the port to every interface and (b) disables both defenses that would otherwise have mitigated that exposure.

## 10. Intended vs Actual Exposure

Working through the assessment questions from the task:

1. **Is the service intentionally intended to be reachable from other machines?** No evidence of this. `docs/development/README.md` explicitly states: *"Do not publicly expose the service as authenticated, rate-limited, durable, distributed, or SLA-certified; those capabilities remain deferred despite Phase 10 completion."* This is a direct statement against exposing the service beyond the local machine.
2. **Is the service an internal-only component?** The `api` service is the *only* component (no DB/Redis to compare against). It is designed as a single local process for development/demo use, per `DEPLOYMENT_PLAN.md`'s "Local development" section.
3. **Is this development-only configuration?** Yes — explicitly, both in the compose file's own header comment ("Local v1.0.0 release-candidate Compose configuration") and its hardcoded `APP_ENV: development`.
4. **Is this production configuration?** No. `DEPLOYMENT_PLAN.md` states production "hosting remains undecided" and lists TLS/secrets/network-controls as still-required future work — there is no production Compose file in this repository to accidentally break.
5. **Is authentication required?** No — confirmed in §6/§9: `APP_ENV=development` bypasses `require_api_key` entirely. (Phase 11.2's API-key auth foundation exists but is not active for this configuration.)
6. **Does the service expose sensitive functionality?** Yes, functionally: workflow creation/listing, research plan/execute/synthesis, watchlists, and financial/news/regulatory snapshot queries were all reachable in the reproduction — none of it requires secrets, but it is real application functionality, not just a static health page.
7. **Does documentation tell users to expose it publicly?** No — the opposite; see point 1.
8. **Is there a safer loopback-only binding consistent with the project's intended usage?** Yes. Nothing in the documented local-dev workflow requires reaching the API from another machine; a developer runs `docker compose up` and curls `127.0.0.1:8000` from the same machine (confirmed by every example in `docs/API-EXAMPLES.md`, which uses `127.0.0.1` exclusively). A loopback-only bind (`127.0.0.1:${API_HOST_PORT:-8000}:8000`) would satisfy every documented use case with no functional loss.

**Conclusion:** this is not an intentional design choice serving a real requirement — it is an omitted host-IP restriction in a file whose own stated purpose (local development, not-for-public-exposure) is incompatible with binding to all interfaces. It is a genuine **confirmed security exposure** for any host where this compose file is run on a machine reachable by other devices (e.g. a shared LAN, a VPN mesh such as the Tailscale interface observed on this test host, or a cloud VM with a public IP used ad hoc for a demo) — not merely a "documentation/hardening opportunity," because the exposure was functionally reproduced end-to-end.

## 11. Security Impact

**Confirmed behavior (reproduced, not inferred):**
- Any device able to route to the host's non-loopback interfaces (LAN, VPN mesh, or a cloud VM's public interface if this compose file were ever run there) can reach the full FastAPI application surface on port 8000/tcp, with zero authentication and zero host-header validation, for as long as `docker compose up` is running.
- This includes workflow-related endpoints and research/financial/news/regulatory snapshot endpoints — real application functionality, not just `/health`.

**Not confirmed / out of this audit's control:**
- Actual internet-wide reachability depends entirely on the specific host's firewall, NAT, and network placement — this audit did not (and was instructed not to) test reachability from a separate machine or perform any scanning. On a typical home/office NAT router, this would only be reachable from the same local network segment, not the public internet, unless the router or cloud security group additionally forwards/allows the port.
- No credential, PII, or persistent-state compromise is possible today specifically *because* of this finding alone — the in-memory workflow store (per F03/F04 audits) holds no durable secrets, and there is no database. The impact is unauthorized *use* of the service (workflow manipulation, query volume) by anyone on the reachable network segment, not data exfiltration of stored secrets.
- Severity is bounded by the fact this is explicitly non-production, ephemeral (in-memory), and documented as not to be exposed — this is a **defense-in-depth / local-hardening gap**, not a production data breach.

## 12. Existing Security Controls

| Control | Present? | Mitigates this exposure? |
|---|---|---|
| API-key authentication (`security/auth.py`) | Present, Phase 11.2 | **No** — disabled whenever `app_env != production/staging`, which is exactly this compose file's setting. |
| `ALLOWED_HOSTS` host-header enforcement | Present (`middleware.py`) | **No** — only enforced when `app_env == production`; a no-op here. |
| `read_only: true`, `tmpfs: /tmp`, `security_opt: no-new-privileges`, non-root `appuser`, `EXPOSE 8000` container hardening | Present | Reduces container-breakout/filesystem-tamper risk but does **nothing** to restrict network reachability of the exposed port — these are orthogonal controls. |
| Docker network isolation (`networks:`) | Default bridge network only | Irrelevant to host-port publication; `ports:` always creates a host-level forward regardless of the internal Docker network topology. |
| Reverse proxy / firewall assumptions | None documented for this Compose file | No reverse proxy is defined; the exposure is not "assumed mitigated by a proxy in front" — there is no proxy in this configuration at all. |
| Production-specific Compose/deployment file | **Does not exist** | N/A — there is nothing to accidentally regress; production is still "undecided" per `DEPLOYMENT_PLAN.md`. |

**Do not treat authentication as eliminating network exposure, per the task's instruction — and indeed here authentication does not even apply**, since it is switched off in exactly this environment. The container-hardening controls (`read_only`, non-root user, etc.) are real and valuable but address a completely different threat (compromise-containment), not reachability. There is no defense-in-depth layer today that narrows who can *reach* the socket — only the host's own firewall/NAT, which is outside this project's configuration.

## 13. Existing Test Coverage

A repository-wide search for any test referencing Docker, Compose, or port-binding behavior returned **zero results** (`grep -rli "docker\|compose\|0.0.0.0\|port.*bind" tests/`). There is:
- No test that runs or parses `docker-compose.yml`.
- No test that asserts a host-bind-address invariant (e.g. "internal services must not publish 0.0.0.0").
- No test that asserts `docker compose config` succeeds (this is only a manually-invoked step referenced in prose across various Markdown phase-audit files, not automated in `.github/workflows/ci.yml`).
- No test asserting the relationship between `APP_ENV` and auth/host-enforcement bypass is itself validated against the shipped compose file's chosen environment (i.e., nothing catches "the compose file sets development, and development disables the two controls that would matter here").

## 14. Test Gaps

1. No automated check that `docker-compose.yml` parses (`docker compose config`) — currently manual/prose-only.
2. No automated check of the resolved `ports:` mapping's host-IP binding for the `api` service (e.g., asserting it is loopback-restricted, or explicitly documenting/allowing an all-interfaces bind if that is ever intentionally chosen for a specific scenario).
3. No static test that flags a *new* service being added to the compose file with an unrestricted port publish (regression protection against this exact class of defect recurring, e.g. if PostgreSQL/Redis are added later per `DEPLOYMENT_PLAN.md`'s "Target components").
4. No test tying together "compose file's `APP_ENV` value" and "the auth/host-enforcement bypass conditions in `security/auth.py`/`api/app.py`" — i.e., nothing would fail today if someone accidentally shipped a compose file with `APP_ENV=development` AND an unrestricted bind (which is exactly today's state) versus a safer combination.

## 15. Recommended Remediation (NOT implemented — plan only)

Smallest architecture-consistent fix, informed by the intended-use analysis in §10:

1. **Bind the local/dev preset to loopback.** Change `docker-compose.yml`'s port mapping from `"${API_HOST_PORT:-8000}:8000"` to `"127.0.0.1:${API_HOST_PORT:-8000}:8000"`. This satisfies every documented use case (`docs/API-EXAMPLES.md` uses `127.0.0.1` exclusively; `docs/development/README.md`'s only network-exposure requirement is "reachable from the same machine that ran `docker compose up`") with zero functional loss, and directly closes the reproduced exposure.
2. **No new Compose files or profiles are required** for this specific fix — there is currently exactly one Compose file, explicitly local-only, and no production Compose configuration exists to preserve a different behavior for. Introducing a separate `docker-compose.prod.yml` (or Compose `profiles`) would only be justified once actual production deployment work begins (per `DEPLOYMENT_PLAN.md`, still "undecided"); doing so now would be scope creep beyond this defect and risks the task's "do not introduce unnecessary infrastructure" constraint.
3. **Do not change `APP_ENV`, the auth bypass, or the host-enforcement bypass logic.** Those are intentional, documented development conveniences (§10) and are not part of this finding's minimal fix — narrowing the network bind address is sufficient and does not require touching `security/auth.py` or `api/app.py`. (A future, separate hardening item could consider whether local dev should still enforce *some* minimal host check even off loopback, but that is out of scope for F06's "smallest correct fix.")
4. **Update `docs/development/README.md`** to note the loopback-only bind explicitly (one line), so a developer who genuinely needs LAN reachability (e.g., testing from a phone on the same network) understands why `docker compose up` no longer answers on their LAN IP and how to deliberately override `API_HOST_PORT`'s binding if they accept that risk themselves (e.g., documenting that changing the bind address is a conscious, individual choice, not the shipped default).
5. Re-run `docker compose config` after the change to confirm the resolved binding shows `host_ip: 127.0.0.1` and re-run the exact reproduction in §7/§8 to confirm the LAN-interface curl now fails (connection refused/timeout) while loopback continues to work.

This keeps the fix to a single line in `docker-compose.yml` plus a documentation note — no application code changes, no new files, no new dependencies, consistent with "the smallest architecture-consistent remediation."

## 16. Regression Test Plan

Given this is infrastructure configuration rather than Python application logic, the most direct and reliable regression coverage is **configuration-level validation**, with an optional live-binding check gated by Docker availability (matching how `docker compose config --quiet` is already used as a manual quality gate per the project's own release documentation). Pure unit tests cannot fully substitute for this because the defect lives in YAML/Docker semantics, not in importable Python — but a lightweight parser-based check can still run in CI without Docker.

**Configuration-only validation (recommended primary layer, no Docker required):**
- A new test (e.g. `tests/unit/test_docker_compose_config.py`) that loads `docker-compose.yml` with `yaml.safe_load` (already a project dependency — `pyyaml` appears in the build output) and asserts, for the `api` service's `ports` entries:
  1. Each port mapping is either the long form with an explicit `host_ip` key, or the short-form string contains a leading IP segment (i.e., matches `^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:` or an env-var-prefixed loopback form like `127.0.0.1:${...}:...`) — rejecting the bare `"${VAR:-PORT}:PORT"` short form that binds all interfaces.
  2. The specific `api` service's resolved host IP is `127.0.0.1` (or another explicitly intended non-wildcard address), not absent and not `0.0.0.0`.
  - This test is not vacuous: run against the current, unmodified `docker-compose.yml`, it fails today (the mapping has no host IP) — providing a concrete before/after signal for the fix.
- A second test asserting the Compose file remains syntactically valid, e.g. by shelling out to `docker compose config --quiet` when Docker is available, skipped (not failed) when it is not — mirroring the project's existing practice of treating this as an optional but valuable gate rather than a hard CI dependency. This also directly covers regression item 5 ("Docker Compose remains valid").

**Regression scenarios to cover, mapped to the task's checklist:**
1. *Intended host bindings are explicit* — assert `ports:` entries always specify a host IP (test above); no service may rely on Docker's implicit all-interfaces default.
2. *Internal services are not unnecessarily published* — currently vacuous (no DB/Redis exist yet), but write the assertion generically over "all services" so it automatically covers PostgreSQL/Redis the moment `DEPLOYMENT_PLAN.md`'s target components are added, preventing this exact defect class from recurring.
3. *API/dashboard exposure matches documented intent* — assert the bound host IP is `127.0.0.1` for the `api` service, matching `docs/API-EXAMPLES.md`'s exclusive use of `127.0.0.1` and the "do not publicly expose" statement in `docs/development/README.md`.
4. *Production configuration is not accidentally broken* — not directly testable today because no production Compose file exists; note this explicitly in the test module's docstring so the gap is visible rather than silently assumed away, and revisit when a production Compose/deployment artifact is introduced.
5. *Docker Compose remains valid* — the `docker compose config --quiet` skip-if-unavailable test above.
6. *`docker compose config` succeeds* — same test as (5).

**Where to add this coverage:** `tests/unit/test_docker_compose_config.py` (new file) is the natural location — it fits the existing `tests/unit/` convention used throughout the project for configuration/contract-style tests (e.g. `test_phase4_contract_freeze.py`), needs no fixtures beyond `pathlib`/`yaml`, and (per the config-only assertions) does not require Docker to run in CI, while still supporting an optional Docker-gated liveness check for local/manual verification.

## 17. Development vs Production Considerations

- **Development / local demo:** the only environment this compose file currently targets. The recommended fix (loopback bind) directly serves this environment and matches every documented usage example.
- **Testing / CI:** no Compose usage exists in `.github/workflows/ci.yml` today; the recommended regression tests are pure config/YAML checks that can run in CI without Docker, and an optional Docker-gated check for environments where Docker is available (mirroring local developer machines and the manual release checklist).
- **Staging / Production:** explicitly "undecided" per `DEPLOYMENT_PLAN.md` — no existing artifact to protect or regress. The recommended fix does not need to special-case a production path because none exists yet; when production deployment work begins, it will need its own network/TLS/reverse-proxy design (already flagged as required in `DEPLOYMENT_PLAN.md`'s "Production" section) rather than reusing this local Compose file's port binding at all. This audit does not recommend building that production configuration now — doing so would be out of scope and would guess at requirements (load balancer? reverse proxy? cloud provider?) that the project has not yet decided.

## 18. Final Audit Verdict

**CONFIRMED.**

The `docker-compose.yml`'s `api` service publishes port 8000 without a host-IP restriction, and this was reproduced at the Docker-engine level (`docker inspect` shows `HostIp: "0.0.0.0"` and `HostIp: "::"`) and functionally (the running service answered unauthenticated application requests on the host's real LAN interface address, not just loopback). This occurs in a file whose own stated purpose and accompanying documentation is local-development-only and explicitly says not to expose the service publicly, and the exposure is not mitigated by any currently-active control: authentication and host-header enforcement are both disabled under this exact file's `APP_ENV=development` setting. There is no production Compose variant to protect, and no database/cache service exists to separately audit. The smallest correct fix is a one-line change to bind the published port to `127.0.0.1`, with a short documentation note; no evidence supports building new production infrastructure as part of this fix.
