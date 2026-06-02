---
name: project-bill-splitter
description: Bill Splitter Telegram Mini App project structure and dev setup
metadata:
  type: project
---

Full-stack Telegram Mini App for splitting restaurant bills.

**Stack:** FastAPI + PostgreSQL (backend), React 18 + TypeScript + Vite (frontend), Docker Compose.

**Key libs added:** @tanstack/react-query v5, framer-motion, clsx (installed 2026-05-29).

**Local dev workflow:**
1. `docker compose -f docker-compose.dev.yml up -d` — starts db (port 5432) + backend (port 8000)
2. `cd frontend && npm run dev` — Vite dev server on port 5173, proxies /api → localhost:8000
3. Open http://localhost:5173

**Why:** docker-compose.dev.yml was created separately from production compose (which requires SSL certs + built frontend).

**How to apply:** When user asks to run the project locally, use docker-compose.dev.yml + npm run dev, not the main docker-compose.yml.
