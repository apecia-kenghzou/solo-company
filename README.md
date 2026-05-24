# Solo Agent OS

**An Autonomous Business Brain for the One-Person Company**

Solo Agent OS is an AI-powered operating system for solo professionals — real estate agents, consultants, recruiters, and other independent operators. It handles your inbox, follows up on leads, researches the market, creates content, and briefs you every morning so you can focus on the work only you can do.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/solo-agent-os.git
cd solo-agent-os

# 2. Copy the environment template and fill in your API keys
cp .env.example .env
# Edit .env with your actual credentials (Anthropic, OpenAI, Pinecone, etc.)

# 3. Start all services with Docker Compose
docker-compose up --build

# 4. Open the app
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# API Docs:  http://localhost:8000/docs
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│            Dashboard · Inbox · Listings · Content Hub            │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST + WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                     Backend (FastAPI)                            │
│   /api/leads  /api/listings  /api/agents  /api/webhooks         │
└──────────┬──────────────────────────────┬───────────────────────┘
           │                              │
┌──────────▼──────────┐       ┌───────────▼──────────────────────┐
│   Postgres (SQLAlch) │       │  Celery Workers (Redis broker)    │
│   Users, Leads,      │       │  - Morning Briefing (07:00)       │
│   Listings, Content  │       │  - Social Trend Scan (09:00)      │
│   Agent Actions      │       │  - Market Intelligence (Mon 08:00)│
└──────────────────────┘       │  - Follow-up Queue (hourly)       │
                               └───────────────────────────────────┘
           │                              │
┌──────────▼──────────────────────────────▼──────────────────────┐
│                      AI Layer (LangGraph)                        │
│  InboxAgent · FollowUpAgent · ResearchAgent · MarketingAgent    │
│  SocialTrendAgent · AdminAgent · BriefingAgent                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌─────▼──────┐ ┌───▼─────────────┐
│  Pinecone    │ │  External  │ │  File Storage    │
│  (Vector KB) │ │  APIs      │ │  (S3 / R2)       │
│              │ │  Gmail     │ └──────────────────┘
└──────────────┘ │  WhatsApp  │
                 │  Meta      │
                 │  Tavily    │
                 │  Apify     │
                 │  Stripe    │
                 └────────────┘
```

Key design decisions:
- **Vertical config YAMLs** drive agent behavior — swap `vertical: real_estate` for `consultant` or `recruiter` and the entire system reorients.
- **Human-in-the-loop approvals** for content publishing and sensitive messages — agents draft, you approve.
- **Pinecone knowledge base** stores your listings, business rules, and brand voice as embeddings so every agent has full context.
- **WebSocket events** push real-time updates to the dashboard (new lead, briefing ready, approval needed).

---

## Milestone Roadmap

| Milestone | Focus | Status |
|-----------|-------|--------|
| **M0** | Repo scaffold, Docker Compose, env config, vertical YAMLs | ✅ Done |
| **M1** | Postgres models, Alembic migrations, CRUD APIs, health checks | 🔨 In Progress |
| **M2** | Knowledge Base (Pinecone ingestion), Listing upload + embed, search | ⬜ Planned |
| **M3** | LangGraph agent graph — InboxAgent + FollowUpAgent live on WhatsApp/Gmail | ⬜ Planned |
| **M4** | MarketingAgent + SocialTrendAgent — daily content drafts, Buffer scheduling | ⬜ Planned |
| **M5** | BriefingAgent — morning summary email + dashboard card | ⬜ Planned |
| **M6** | Multi-user, Stripe billing, Clerk auth, vertical switcher UI | ⬜ Planned |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2.0 async |
| AI / LLM | Anthropic Claude (claude-sonnet-4-6), LangGraph, LangChain |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | Pinecone |
| Database | PostgreSQL 15 |
| Cache / Queue | Redis 7, Celery 5 |
| File Storage | AWS S3 / Cloudflare R2 |
| Auth | Clerk |
| Payments | Stripe |
| Email | Gmail API (OAuth2) |
| Messaging | 360dialog WhatsApp Business API |
| Social | Meta Graph API, Buffer |
| Research | Tavily Search, Apify |
| Image Gen | Ideogram |
| Observability | Sentry, LangSmith, structlog |
| Infrastructure | Docker Compose, GitHub Actions |

---

## Project Structure

```
solo-company/
├── .env.example          # All required environment variables
├── docker-compose.yml    # Full local dev + production compose
├── README.md
│
├── config/
│   └── verticals/
│       ├── real_estate.yaml
│       ├── consultant.yaml
│       └── recruiter.yaml
│
└── backend/
    ├── main.py           # FastAPI app entrypoint
    ├── requirements.txt
    ├── config/
    │   └── settings.py   # Pydantic settings (all env vars)
    ├── models/           # SQLAlchemy models
    │   ├── base.py
    │   ├── user.py
    │   ├── listing.py
    │   ├── lead.py
    │   └── content.py
    ├── api/              # FastAPI routers
    │   ├── health.py
    │   ├── listings.py
    │   ├── leads.py
    │   ├── webhooks.py
    │   └── agents.py
    ├── tools/            # External API integrations
    │   ├── gmail.py
    │   ├── whatsapp.py
    │   ├── s3.py
    │   ├── tavily.py
    │   ├── calendar.py
    │   ├── meta_api.py
    │   └── apify.py
    └── workers/          # Celery tasks
        ├── celery_app.py
        └── tasks.py
```

---

## Contributing

1. Fork the repository and create a feature branch: `git checkout -b feat/your-feature`
2. Make your changes following the existing code style (ruff for Python, eslint/prettier for TS)
3. Add or update tests where applicable
4. Open a Pull Request with a clear description of what changes and why
5. All PRs require one approval before merging to `main`

For large features, open an issue first to discuss the design.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright (c) 2024 Solo Agent OS Contributors
