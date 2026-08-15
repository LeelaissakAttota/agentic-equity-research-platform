# Demo Playbook

This playbook is written for the validated deterministic Apple demo path. It intentionally distinguishes what is implemented, what is fixture-backed for demo purposes, and what is planned but not currently live.

## A. 2-minute recruiter demo

### Objective

Show that the project is a serious, evidence-first, deterministic research platform rather than a chatbot that invents answers.

### Flow

1. Project purpose
   - “This is an agentic equity research platform designed around evidence, company identity, verification, and deterministic synthesis.”

2. Architecture
   - “The system separates API, application logic, domain rules, and providers. It does not pretend live data unless explicitly supported.”

3. Company resolution
   - “The app resolves Apple cleanly in the supported fixture-backed catalog. Company identity is normalized before any research begins.”

4. Research planning
   - “It builds a bounded research plan using the supported Apple objective and time horizon.”

5. Synthesis
   - “The system produces structured evidence-linked outputs with explicit stale/insufficient semantics instead of fabricated certainty.”

6. API/OpenAPI
   - “The project exposes a real OpenAPI document at /openapi.json. The Swagger UI route /docs is not currently exposed.”

### Talking points

- The project emphasizes traceability over fluent guessing.
- The demo uses deterministic fixture-backed Apple data.
- The app is honest about stale or insufficient evidence rather than inventing analysis.
- This is a strong portfolio project in platform engineering, research orchestration, and evidence-first design.

## B. 5-minute technical interview demo

### Objective

Walk through the actual engineering depth: architecture, data flow, verification, API contracts, and product honesty.

### Flow

1. Project purpose
   - “The goal is not to generate convincing prose. The goal is to produce traceable research outputs grounded in source metadata, verification, and structured evidence.”

2. Architecture
   - “The design keeps domain logic separate from framework concerns. The app uses FastAPI, deterministic domain contracts, and explicit composition rather than hidden global state.”

3. Company resolution
   - “Apple resolves through the project’s identity catalog. The same flow is designed for Indian and US entities with exchange and country constraints.”

4. Research planning
   - “The planner builds a bounded objective and creates a research run with resolved company identity and time horizon.”

5. Multi-domain research
   - “The system supports market, financial, news/events, industry, and regulatory snapshot APIs with fixture-backed evidence.”

6. Evidence and verification
   - “Material claims carry evidence, source metadata, provenance, and freshness semantics. The system explicitly marks stale or insufficient claims instead of pretending certainty.”

7. Synthesis
   - “The final synthesis is deterministic and structured, with sections, claims, citations, confidence context, contradictions, and missing-data handling.”

8. API/OpenAPI
   - “The project exposes /openapi.json. The Swagger UI route /docs is not currently enabled, so the demo should not describe Swagger as available.”

9. Automated testing
   - “The project maintains a strong automated regression baseline. The final verified baseline is 658 passing tests.”

10. Limitations
   - “This demo path uses deterministic fixture data and does not claim live market or financial data. The architecture is ready for future live-provider integration but does not claim that capability today.”

### Interview-ready talking points

- “This project focuses on evidence-first research infrastructure, not prompt-only output.”
- “The product treats stale or insufficient evidence as a first-class signal.”
- “The research flow is bounded, deterministic, and traceable.”
- “The project is designed for future provider integration without hiding the difference between demo fixtures and real-time data.”

## Capability classification

### IMPLEMENTED

- Company resolution for supported deterministic identities
- Market, financial, news, industry, and regulatory snapshot APIs
- Research planning and execution contracts
- Evidence-aware synthesis with explicit stale/insufficient status
- OpenAPI specification exposure at /openapi.json
- Automated regression testing with the validated baseline

### DEMO / FIXTURE-BACKED

- Apple research flow used in the current demo
- Deterministic market and financial snapshots
- Forecast-free fixture-backed event and industry context
- Synthesis examples using supported fixture claim data

### FUTURE / PLANNED

- Live market and filing provider integration
- Durable persistence beyond in-memory demo flows
- Streamlit or richer portfolio UX
- Full report generation beyond the current deterministic structured outputs
- Broader real-world research coverage and provider expansion

## Demo summary

The strongest recruiter/interviewer story is this: a deterministic, evidence-first research platform that resolves companies, plans bounded research tasks, verifies claims, and synthesizes honest structured findings without pretending live financial data is being used.
