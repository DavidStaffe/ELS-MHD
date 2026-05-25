# Project Overview: ELS-MHD

Last updated: 2026-04-25

## 1) Executive Summary

ELS-MHD is a production-oriented web application for medical event operations management (incident command, patient tracking, transport coordination, resource allocation, communications, conflicts, sections, and treatment beds).

The codebase is split into a FastAPI + MongoDB backend and a React 19 frontend. The overall architecture is modular and domain-driven, with clear route/service separation in backend and page/context separation in frontend.

Current implementation appears feature-rich and mature (steps 01-13 from project history), with extensive backend API tests and a broad operational workflow.

## 2) Architecture and Structure

## Backend

- Entry point: backend/server.py
- Framework: FastAPI + Motor (async MongoDB)
- Key structure:
  - backend/core: infrastructure helpers (db, time, shared types)
  - backend/models.py: Pydantic models and request/response contracts
  - backend/routes: domain APIs (incidents, patients, transports, resources, messages, abschnitte, betten, analytics)
  - backend/services: shared business logic (analytics, demo seeding, data seeding)

Design characteristics:

- Thin bootstrap in server.py and logic pushed to routes/services.
- Startup migration mechanism is present and idempotent-focused.
- Domain endpoints are organized by bounded context.

## Frontend

- Entry point: frontend/src/App.js
- Framework: React 19 + React Router 7 + CRACO + Tailwind + Radix/shadcn component stack
- App wiring:
  - Context providers for role/incident/patient/transport/ops state
  - Route-driven modules (incident list, archive, Lage, patients, transports, resources, sections, beds, communication log, conflicts, closure)

Design characteristics:

- Strong modular page-level decomposition.
- Central API abstraction in frontend/src/lib/api.js mapped closely to backend endpoints.
- Operational UI scope is broad and aligned with backend domains.

## 3) Feature Coverage Observed

Observed implemented domains include:

- Incident lifecycle (create, update, archive/delete patterns)
- Patient workflow (triage, status progression, reopen logic)
- Transport lifecycle with resource coupling
- Resource CRUD and assignment
- Communication/funktagebuch workflow (including confirm/finalize style transitions)
- Conflict detection and analytics blocks
- Sections (abschnitte) and bed (betten) management, including assignment/release
- Report generation/versioning endpoints for closure workflows

Overall, backend and frontend naming and route mappings are consistent.

## 4) Data and Runtime Assumptions

## Environment/config dependencies

Backend requires at least:

- MONGO_URL
- DB_NAME

Frontend API base requires:

- REACT_APP_BACKEND_URL

Operational implications:

- Missing frontend backend URL env will make API base invalid.
- No default/fallback API origin is defined in frontend/src/lib/api.js.

## Persistence model

Mongo collections (from project docs and code paths) include incidents, patients, transports, resources, messages, abschnitte, betten, report_versions.

Deletion behavior in incident routes cascades manually across dependent collections.

## 5) Testing and Quality Signals

Positive signals:

- Large backend pytest suite exists (grep found 155 test functions across domain-focused test modules).
- Tests are organized by feature milestones and include regression-style scenarios.
- Multiple saved test reports are present under test_reports/.

Caveats:

- test_result.md currently contains protocol/instruction scaffolding rather than actionable test outcomes.
- Some test names indicate legacy version assertions (for example, expecting 0.x style versions) while current API metadata in code is 1.0.0.

## 6) Key Strengths

- Clear domain decomposition in backend routes/services.
- Good separation between transport/resource/patient business rules and API entrypoints.
- Feature set covers full incident operations lifecycle, not a toy/demo-only subset.
- Frontend route map mirrors operational modules cleanly.
- Existing regression intent is strong due to broad backend test inventory.

## 7) Key Risks and Gaps

## Medium risk

- Documentation drift:
  - frontend/README.md is still generic Create React App text and does not describe actual project workflows.
  - Some historical references in root README/testing narrative appear out of sync with current API version values.

- Version-contract drift:
  - Code exposes API version 1.0.0, while several legacy test names indicate earlier expected versions.
  - This can cause brittle CI or confusion if assertions were not fully updated.

- Config fragility:
  - frontend/src/lib/api.js has no fallback when REACT_APP_BACKEND_URL is unset.
  - Local setup errors may fail late at runtime.

## Low-to-medium risk

- Dependency surface in backend/requirements.txt is broad relative to observed core runtime paths.
- Potential for maintainability/security overhead if unused packages are kept unreviewed.

## 8) Recommended Next Actions (Prioritized)

1. Align version contracts across API metadata, tests, and docs.
2. Replace frontend/README.md with project-specific setup and architecture notes.
3. Add explicit startup guard for missing REACT_APP_BACKEND_URL (or provide safe default).
4. Create a concise backend/frontend runbook at repo root (env vars, startup order, seed/demo flow, test commands).
5. Audit and trim unused backend dependencies to reduce maintenance and security exposure.

## 9) Overall Assessment

This is a capable, near-production operations platform with strong domain coverage and a reasonably clean architecture. The main improvements needed are not core functionality, but consistency and operational hardening: documentation accuracy, version-contract alignment, and safer configuration defaults.
