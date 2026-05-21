# EZ-Catch

An open-source observability and governance layer for AI agents. EZ-Catch monitors AI IDE sessions (Cursor, VS Code + Copilot, and similar tools), capturing terminal commands, API calls, reasoning traces, and context — then surfaces insights to team admins on what's happening, what's failing, and why.

> **Status: Active Development** — Current version monitors terminal command activity. The full agent observability suite and policy firewall are on the roadmap.

[![License](https://img.shields.io/badge/License-View_License-blue?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active_Development-orange?style=flat-square)]()
[![Python](https://img.shields.io/badge/Python-3.10-blue?logo=python&logoColor=white&style=flat-square)](https://python.org)
[![JavaScript](https://img.shields.io/badge/JavaScript-TypeScript-3178C6?logo=typescript&logoColor=white&style=flat-square)](https://typescriptlang.org)

---

## The Problem

When developers use AI IDEs — Cursor, GitHub Copilot, or any LLM-backed coding assistant — the AI reasons, calls APIs, and executes commands. But to team leads and engineering managers, that process is a black box.

Questions that currently have no good answer:
- Is my team's AI agent hallucinating and running bad commands?
- Which developers are using the AI effectively, and which are running into dead ends?
- Are there API calls being made that shouldn't be (rate limits, policy violations, cost overruns)?
- When something breaks, was it a developer decision or an AI reasoning failure?

EZ-Catch answers these questions by making AI agent behaviour observable and auditable.

---

## What It Does (Current Version)

EZ-Catch currently hooks into AI IDE sessions and captures:

- **Terminal commands** executed by the AI agent or the developer
- **Command sequences** — what led to what
- **Session context** — which project, which agent, when

This data flows into a dashboard that gives admins a per-developer and per-session view of activity.

---

## Roadmap

### Phase 1 — Terminal Monitoring *(current)*
- [x] Hook into AI IDE terminal sessions (Cursor, VS Code)
- [x] Capture and log commands with timestamps and session context
- [x] Admin dashboard — per developer, per session view
- [ ] Anomaly flagging — detect unusual command patterns

### Phase 2 — Full Agent Observability
- [ ] API call interception — log all outbound LLM API calls with prompt, model, tokens, cost
- [ ] Reasoning trace capture — record chain-of-thought and tool-use sequences
- [ ] Context window snapshots — capture what context the agent was working with when it made a decision
- [ ] Hallucination detection — flag responses that contradict the codebase or prior context
- [ ] Developer insight reports — per-developer usage patterns, error rates, AI reliance scores

### Phase 3 — Policy Firewall
- [ ] Policy rule engine — define what commands and API calls are allowed
- [ ] Real-time blocking — intercept and block policy-violating terminal commands before execution
- [ ] Hallucination firewall — block API calls made under detected hallucination conditions
- [ ] Org-wide policy management — role-based rules per team or seniority level
- [ ] Audit log — immutable record of all blocked actions with reason

---

## Architecture (Current)

```
AI IDE Session (Cursor / VS Code + Copilot)
        │
        │  Terminal hook / process monitor
        ▼
  Local EZ-Catch Agent
        │
        │  Event stream
        ▼
  EZ-Catch Backend (FastAPI)
        │
        ├── SQLite (local buffer)
        └── Dashboard API
                │
                ▼
        Admin Dashboard (React)
        — per-developer activity
        — session timelines
        — command logs
```

---

## Who It's For

**Engineering managers and team leads** in organisations where developers are using AI IDEs — and who want visibility into how AI agents are operating within their codebase and infrastructure.

This is especially relevant for:
- Teams with compliance requirements (fintech, healthtech)
- Organizations with strict API cost budgets
- Teams where junior developers are using AI agents with production access

---

## Setup

```bash
git clone https://github.com/AWW4B/EZ-catch
cd EZ-catch

# Local development
docker compose -f docker-compose.local.yml up

# Enterprise (multi-tenant)
docker compose -f docker-compose.enterprise.yml up
```

---

## Contributing

EZ-Catch is open source. If you're working in AI observability, agent governance, or developer tooling — contributions, issues, and discussions are welcome.

Areas where help is most valuable right now:
- API call interception adapters for different LLM providers
- Hallucination detection heuristics
- Dashboard visualisations for session timelines

---

## License

See [LICENSE](LICENSE).