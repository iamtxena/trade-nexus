# Trade Nexus — Environment Variable Contract

> **Owner**: Team VOps
> **Last updated**: 2026-02-21
> **Purpose**: Handoff document for dev lanes. Defines what environment variables are available per deployment target.

## For Dev Teams

> **Rule**: If you need a new environment variable, open a VOps request in #223.
> **Rule**: Never provision Azure, Supabase, or Vercel resources directly.
> **Rule**: Use the provided `.env.example` templates for local development.

## Backend (Azure Container Apps)

| Env Var | Source | Required | Default | Purpose |
|---------|--------|----------|---------|---------|
| XAI_API_KEY | secretRef: xai-api-key | Yes | — | xAI Grok model access |
| SUPABASE_URL | plain | Yes | — | Database endpoint |
| SUPABASE_KEY | secretRef: supabase-key | Yes | — | Database service role key |
| LANGSMITH_API_KEY | secretRef: langsmith-api-key | Yes | — | LangSmith observability |
| LANGSMITH_ENDPOINT | plain | Yes | — | LangSmith API URL |
| LANGSMITH_PROJECT | plain | Yes | `trade-nexus-backend` | Project name |
| LANGSMITH_TRACING | plain | Yes | `true` | Enable tracing |
| LONA_GATEWAY_URL | plain | Yes | `https://gateway.lona.agency` | Lona platform |
| LONA_AGENT_ID | plain | Yes | `trade-nexus` | Agent identifier |
| LONA_AGENT_NAME | plain | Yes | `Trade Nexus Orchestrator` | Display name |
| LONA_AGENT_TOKEN | secretRef: lona-agent-token | Yes | — | Lona auth (30-day TTL) |
| LIVE_ENGINE_URL | plain | Yes | `https://live.lona.agency` | Live engine endpoint |
| LIVE_ENGINE_SERVICE_API_KEY | secretRef: live-engine-service-api-key | Yes | — | Live engine auth |

> **Note**: This table covers *deployed* Container App variables only. Local development requires additional variables (e.g., `LONA_AGENT_REGISTRATION_SECRET`, `INITIAL_CAPITAL`, `MAX_POSITION_PCT`, `MAX_DRAWDOWN_PCT`, `TRADER_DATA_*`). See `backend/.env.example` for the full local dev set.

## Frontend (Vercel)

| Env Var | Visibility | Required | Default | Purpose |
|---------|------------|----------|---------|---------|
| NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY | Public | Yes | — | Clerk client auth |
| CLERK_SECRET_KEY | Server | Yes | — | Clerk server auth |
| NEXT_PUBLIC_CLERK_SIGN_IN_URL | Public | Yes | `/sign-in` | Sign-in path |
| NEXT_PUBLIC_CLERK_SIGN_UP_URL | Public | Yes | `/sign-up` | Sign-up path |
| NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL | Public | Yes | `/dashboard` | Post sign-in redirect |
| NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL | Public | Yes | `/dashboard` | Post sign-up redirect |
| NEXT_PUBLIC_SUPABASE_URL | Public | Yes | — | Supabase endpoint |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | Public | Yes | — | Supabase anon key |
| SUPABASE_SERVICE_ROLE_KEY | Server | Yes | — | Supabase admin key |
| UPSTASH_REDIS_REST_URL | Server | Yes | — | Redis endpoint |
| UPSTASH_REDIS_REST_TOKEN | Server | Yes | — | Redis auth |
| XAI_API_KEY | Server | Yes | — | AI model access |
| LANGSMITH_API_KEY | Server | Yes | — | Observability |
| LANGSMITH_PROJECT | Server | Yes | `trade-nexus` | Project name |
| ML_BACKEND_URL | Server | Yes | `http://localhost:8000` | Backend API |
| LONA_GATEWAY_URL | Server | Yes | `https://gateway.lona.agency` | Lona platform |
| LONA_AGENT_ID | Server | Yes | `trade-nexus` | Agent ID |
| LONA_AGENT_NAME | Server | Yes | `Trade Nexus Orchestrator` | Agent name |
| LONA_AGENT_REGISTRATION_SECRET | Server | No | — | Registration secret |
| LONA_AGENT_TOKEN | Server | Yes | — | Lona auth |
| LONA_TOKEN_TTL_DAYS | Server | No | `30` | Token TTL |
| LIVE_ENGINE_URL | Server | Yes | `https://live.lona.agency` | Live engine |
| LIVE_ENGINE_SERVICE_KEY | Server | Yes | — | Live engine auth |

## trading-cli (External CLI)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLATFORM_API_BASE_URL` | Yes (non-local) | `http://localhost:3000` | Must point to `https://api-nexus.lona.agency` in production |

## CI/CD (GitHub Actions)

| Secret | Used In | Description |
|--------|---------|-------------|
| `AZURE_CREDENTIALS` | `backend-deploy.yml` | SP OIDC federation JSON |
| `ACR_LOGIN_SERVER` | `backend-deploy.yml` | `tradenexusacr.azurecr.io` |
| `ACR_USERNAME` | `backend-deploy.yml` | ACR admin user (**remove after MI migration**) |
| `ACR_PASSWORD` | `backend-deploy.yml` | ACR admin password (**remove after MI migration**) |
| `NPM_TOKEN` | `publish-sdk.yml` | npm publishing |

## Domain References — Canonical Values

| Purpose | Old value | New value |
|---------|-----------|-----------|
| Frontend | *(Vercel default)* | `https://trade-nexus.lona.agency` |
| Backend API | `https://api.trade-nexus.io` | `https://api-nexus.lona.agency` |
| Docs portal | *(none)* | `https://docs-nexus.lona.agency` |
| Schema IDs | `https://trade-nexus.io/schemas/...` | `https://trade-nexus.lona.agency/schemas/...` |
| Ops scripts | `trade-nexus-backend.whitecliff-*.azurecontainerapps.io` | `api-nexus.lona.agency` |

## Local Development

- Backend: Copy `backend/.env.example` → `backend/.env`
- Frontend: Copy `frontend/.env.example` → `frontend/.env.local`
- Fill in credentials from your team lead or VOps-provided dev credentials.

## Issue → Environment Contract

| Issue | Feature | Required Env Vars | Status |
|-------|---------|-------------------|--------|
| #226 | Validation storage adapters | SUPABASE_URL, SUPABASE_KEY | **Available** |
| #229 | Baseline replay + gates | No new env vars | **N/A** |
| #230 | Web review lane | Frontend Supabase vars | **Available** |
| #231 | CLI validation commands | Backend env vars | **Available** |
