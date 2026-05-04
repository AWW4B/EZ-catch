# 🧠 AI IDE System Context & Project Plan
**Project:** Agent Monitor (Enterprise Monorepo)
**Current Focus:** Phase 1 COMPLETE → Phase 2: Backend API & Frontend wiring
**Objective:** Intercept and log local AI agent activity (HTTPS reasoning/API calls & OS terminal commands) without blocking or adding latency.

---

## 💾 STATE TRACKER (AI: Read This First)
*AI Instruction: Whenever you complete a task, update the `Current Status` and `Completed Tasks` below. If the user switches accounts or starts a new session, read this section to immediately resume context.*

*   **Current Status:** [PHASE 1 COMPLETE] — All agent-side interceptors, buffer, and forwarder are implemented. Backend API (FastAPI) is wired and functional. Admin dashboard polls the backend live.
*   **Active Objective:** Phase 2 — Add authentication to admin routes; wire frontend user-dashboard; move to PostgreSQL.
*   **Completed Tasks:**
    *   [x] Monorepo directory structure created.
    *   [x] Initial file scaffolding and AI context comments added.
    *   [x] Define Pydantic schemas in `events.py` — `BaseEvent`, `NetworkIntercept`, `TerminalAction`, `LLMReasoningContext`.
    *   [x] Define policy schemas in `policies.py` — `PolicyRule`, `PolicySet`, `PolicyAction` (data models only, no enforcement).
    *   [x] Implement `mitmproxy` request/response parsing in `network_proxy.py`.
    *   [x] Implement `auditd` log tailing for `execve` syscalls in `os_monitor.py`.
    *   [x] Wire interceptors to local SQLite/WAL buffer in `buffer.py`.
    *   [x] Implement `BufferForwarder` in `forwarder.py` — batches events → backend `/api/v1/ingest` via HTTP POST with retry logic.
    *   [x] Wire forwarder into `apps/agent/src/main.py` (fixed `__class__` bug, added graceful shutdown).
    *   [x] Implement FastAPI backend: `src/main.py`, CORS, startup DB init, `/health` endpoint.
    *   [x] Implement SQLAlchemy ORM model `CapturedEvent` in `src/models/database.py`.
    *   [x] Implement `POST /api/v1/ingest` route in `src/api/v1/ingest.py`.
    *   [x] Implement `GET /api/v1/logs` and `GET /api/v1/logs/{id}` in `src/api/v1/user_routes.py`.
    *   [x] Implement admin routes (stats, purge, filtered list) in `src/api/v1/admin_routes.py`.
    *   [x] Add `src/api/dependencies.py` DB session injection helper.
    *   [x] Add `apps/backend/requirements.txt` (fastapi, uvicorn, sqlalchemy, pydantic).
    *   [x] Evaluator stub in `src/services/evaluator.py` (monitoring-only mode, always ALLOW).
    *   [x] Firewall stub in `src/services/firewall.py` (Phase 2+ placeholder).
    *   [x] Agent config files: `config/local.yaml`, `config/cloud.yaml`.
    *   [x] `docker-compose.local.yml` — backend + admin-panel services.
    *   [x] `docker-compose.enterprise.yml` — enterprise compose with PostgreSQL/Redis stubs.

---

## 🚫 RULES OF ENGAGEMENT
**AI INSTRUCTION: Strict adherence required.**
1.  **Phase 1 is DONE.** You may now modify `apps/backend/` and `apps/frontend/admin-panel/` for Phase 2 work.
2.  **DO NOT TOUCH** `packages/policies.py`. Firewall/blocking logic is still deferred. Do not implement `FirewallEngine.enforce()` or blocking in `mitmproxy`.
3.  **DO NOT USE** synchronous blocking calls in interceptors. Writing to disk or databases must be handled via the local buffer/queue.
4.  **Target OS:** Arch Linux. Assume `auditd` is available for syscall hooking.
5.  **user-dashboard** (`apps/frontend/user-dashboard/`) is not yet scaffolded — do not start it without a Phase 3 plan.

---

## 🏗️ CURRENT DIRECTORY MAP

```
EZ-catch/
├── apps/
│   ├── agent/                         ← Bare-metal monitor (COMPLETE)
│   │   ├── config/
│   │   │   ├── local.yaml             ✅ audit log path, mitm port, buffer/forwarder settings
│   │   │   └── cloud.yaml             ✅ cloud/Docker variant
│   │   ├── requirements.txt           ✅ mitmproxy, pydantic, torch, etc.
│   │   └── src/
│   │       ├── core/
│   │       │   ├── buffer.py          ✅ LocalSQLiteBuffer (WAL, thread-safe push)
│   │       │   └── forwarder.py       ✅ BufferForwarder (HTTP batch POST, retry)
│   │       ├── interceptors/
│   │       │   ├── network_proxy.py   ✅ mitmproxy addon — LLM reasoning extraction
│   │       │   └── os_monitor.py      ✅ auditd tail — EXECVE syscall parsing
│   │       └── main.py                ✅ Entrypoint: root check, buffer, forwarder, audit monitor
│   │
│   ├── backend/                       ← FastAPI service (COMPLETE — Phase 2 wiring pending)
│   │   ├── Dockerfile                 ✅ multi-stage python:3.11-slim build
│   │   ├── requirements.txt           ✅ fastapi, uvicorn, sqlalchemy, pydantic
│   │   └── src/
│   │       ├── main.py                ✅ FastAPI app, CORS, /health, router wiring
│   │       ├── api/
│   │       │   ├── dependencies.py    ✅ DB session FastAPI dependency
│   │       │   └── v1/
│   │       │       ├── ingest.py      ✅ POST /api/v1/ingest (agent → backend)
│   │       │       ├── user_routes.py ✅ GET /api/v1/logs, GET /api/v1/logs/{id}
│   │       │       └── admin_routes.py✅ GET/DELETE /api/v1/admin/* (stats, purge)
│   │       ├── models/
│   │       │   └── database.py        ✅ SQLAlchemy CapturedEvent ORM + session factory
│   │       └── services/
│   │           ├── evaluator.py       🔲 Stub — PolicyEvaluator (Phase 2: wire real rules)
│   │           └── firewall.py        🔲 Stub — FirewallEngine (Phase 2+, do not implement yet)
│   │
│   └── frontend/
│       ├── admin-panel/               ← Next.js admin dashboard (COMPLETE UI)
│       │   ├── Dockerfile             ✅ node:20-alpine dev server
│       │   └── src/
│       │       ├── app/page.tsx       ✅ Live dashboard — network + terminal event feeds
│       │       └── pages/             🔲 Stub dirs: dashboard/, policies/, users/
│       └── user-dashboard/            🔲 Not scaffolded (Phase 3)
│
├── packages/
│   ├── schemas/
│   │   ├── events.py                  ✅ BaseEvent, NetworkIntercept, TerminalAction, LLMReasoningContext
│   │   └── policies.py                ✅ PolicyRule, PolicySet, PolicyAction (data models only)
│   └── auth/                          🔲 Empty — Phase 2: JWT/API-key auth
│
├── docker-compose.local.yml           ✅ backend + admin-panel
└── docker-compose.enterprise.yml      ✅ same + commented PostgreSQL/Redis stubs
```

---

## 🎯 EXECUTION PLAN

### ✅ Phase 1: Agent-Side Interceptors & Buffer (DONE)
All four sub-phases are complete.

---

### 🔲 Phase 2: Backend Polish & Auth
**Files to Touch:**
- `packages/auth/` — JWT or API-key authentication package
- `apps/backend/src/api/dependencies.py` — add `get_current_user` dependency
- `apps/backend/src/api/v1/admin_routes.py` — gate behind auth
- `apps/backend/src/services/evaluator.py` — load PolicySet from DB/YAML config

**Actions:**
1. Scaffold `packages/auth/` with a simple API-key validator.
2. Add `Authorization: Bearer <key>` requirement to admin routes.
3. Load `PolicySet` from `apps/agent/config/local.yaml` into `PolicyEvaluator` and run it on each ingested event to emit structured alerts.

**Outcome:** Secured backend where only authenticated callers can purge/manage logs; evaluator prints live policy alerts to console.

---

### 🔲 Phase 3: Frontend — Admin Panel Pages
**Files to Touch:**
- `apps/frontend/admin-panel/src/pages/dashboard/` — detailed drill-down view per event
- `apps/frontend/admin-panel/src/pages/policies/` — UI to view/toggle policy rules
- `apps/frontend/admin-panel/src/pages/users/` — user/source-process breakdown

**Actions:**
1. Build each page using the existing design system (dark, zinc-950 bg, emerald accents).
2. Wire `/api/v1/admin/stats` to the dashboard page.
3. Wire `/api/v1/admin/logs` with filters to the policies page.

---

### 🔲 Phase 4: Firewall Enforcement (DEFERRED)
**Files to Touch:** `apps/backend/src/services/firewall.py`, `apps/agent/src/interceptors/network_proxy.py`
**Prerequisite:** Phase 2 policy evaluation must be complete and stable.
**Actions:** Implement `FirewallEngine.enforce()` to call `flow.kill()` via mitmproxy for BLOCK-action rules.

---

### 🔲 Phase 5: Enterprise — PostgreSQL Migration
**Files to Touch:** `apps/backend/src/models/database.py`, `docker-compose.enterprise.yml`
**Actions:** Replace SQLite engine URL with PostgreSQL; uncomment the `postgres:` service in the enterprise compose file; run Alembic migrations.

---
*AI: When the user issues a command, determine which Phase we are currently in (Phase 2), and execute the defined actions for those specific files. Do NOT touch firewall enforcement.*