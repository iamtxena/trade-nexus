# Trade Nexus — Environment Variable Contract

> **Owner**: Team VOps
> **Last updated**: 2026-02-18
> **Purpose**: Handoff document for dev lanes. Defines what environment variables are available per deployment target.

## For Dev Teams

> **Rule**: If you need a new environment variable, open a VOps request in #223.
> **Rule**: Never provision Azure, Supabase, or Vercel resources directly.
> **Rule**: Use the provided `.env.example` templates for local development.

## Backend (Azure Container Apps)

| Env Var | Source | Required | Format | Purpose |
|---------|--------|----------|--------|---------|
| XAI_API_KEY | secretRef | Yes | `xai-...` | xAI Grok model access |
| SUPABASE_URL | plain | Yes | `https://<project>.supabase.co` | Database endpoint |
| SUPABASE_KEY | secretRef | Yes | `eyJ...` (JWT) | Database service role key |
| LANGSMITH_API_KEY | secretRef | Yes | `lsv2_...` | LangSmith observability |
| LANGSMITH_ENDPOINT | plain | Yes | `https://api.smith.langchain.com` | LangSmith API |
| LANGSMITH_PROJECT | plain | Yes | `trade-nexus-backend` | Project name |
| LANGSMITH_TRACING | plain | Yes | `true` | Enable tracing |
| LONA_GATEWAY_URL | plain | Yes | `https://gateway.lona.agency` | Lona platform |
| LONA_AGENT_ID | plain | Yes | `trade-nexus` | Agent identifier |
| LONA_AGENT_NAME | plain | Yes | `Trade Nexus Orchestrator` | Display name |
| LONA_AGENT_TOKEN | secretRef | Yes | `<token>` | Lona auth (30-day TTL) |
| LIVE_ENGINE_URL | plain | Yes | `https://live.lona.agency` | Live engine endpoint |

## Frontend (Vercel)

| Env Var | Visibility | Required | Purpose |
|---------|------------|----------|---------|
| NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY | Public | Yes | Clerk client auth |
| CLERK_SECRET_KEY | Server | Yes | Clerk server auth |
| NEXT_PUBLIC_CLERK_SIGN_IN_URL | Public | Yes | `/sign-in` |
| NEXT_PUBLIC_CLERK_SIGN_UP_URL | Public | Yes | `/sign-up` |
| NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL | Public | Yes | `/dashboard` |
| NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL | Public | Yes | `/dashboard` |
| NEXT_PUBLIC_SUPABASE_URL | Public | Yes | Supabase endpoint |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | Public | Yes | Supabase anon key |
| SUPABASE_SERVICE_ROLE_KEY | Server | Yes | Supabase admin key |
| UPSTASH_REDIS_REST_URL | Server | Yes | Redis endpoint |
| UPSTASH_REDIS_REST_TOKEN | Server | Yes | Redis auth |
| XAI_API_KEY | Server | Yes | AI model access |
| LANGSMITH_API_KEY | Server | Yes | Observability |
| LANGSMITH_PROJECT | Server | Yes | Project name |
| ML_BACKEND_URL | Server | Yes | Backend API |
| LONA_GATEWAY_URL | Server | Yes | Lona platform |
| LONA_AGENT_ID | Server | Yes | Agent ID |
| LONA_AGENT_NAME | Server | Yes | Agent name |
| LONA_AGENT_REGISTRATION_SECRET | Server | No | Registration secret |
| LONA_AGENT_TOKEN | Server | Yes | Lona auth |
| LONA_TOKEN_TTL_DAYS | Server | No | Token TTL (default 30) |
| LIVE_ENGINE_URL | Server | Yes | Live engine |
| LIVE_ENGINE_SERVICE_KEY | Server | Yes | Live engine auth |

## Local Development

- Backend: Copy `backend/.env.example` → `backend/.env`
- Frontend: Copy `frontend/.env.example` → `frontend/.env.local`
- Fill in credentials from your team lead or VOps-provided dev credentials.

## Issue → Environment Contract

| Issue | Feature | Required Env Vars | Status |
|-------|---------|-------------------|--------|
| #226 | Validation storage adapters | SUPABASE_URL, SUPABASE_KEY | **Available** — no new vars needed |
| #229 | Baseline replay + gates | No new env vars (uses existing Supabase) | **N/A** |
| #230 | Web review lane | Frontend Supabase vars | **Available** |
| #231 | CLI validation commands | Backend env vars | **Available** |

**Conclusion**: All environment variables needed for the validation program (#226–#231) are already provisioned. No new cloud resource provisioning is required for these issues.
