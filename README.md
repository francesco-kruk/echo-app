# Echo App

A flashcard application built with React + FastAPI, designed for Azure Container Apps deployment with Cosmos DB backend.

## Overview

- Azure-first deployment with automatic infrastructure and identity setup
- Secure by default: internal backend, Entra ID auth, Managed Identity for Cosmos DB
- Simple local dev with Docker Compose or scripts
- CI/CD setup handled separately via dedicated script

### Features

- 📚 **Deck Management** – Create, edit, and delete flashcard decks
- 🃏 **Card Management** – Add, edit, and delete cards within decks
- 🔄 **Interactive Flashcards** – Click to flip cards and reveal answers
- 📦 **Sample Data** – One-click button to populate sample flashcard decks
- 🌐 **Azure Ready** – Deploys to Azure Container Apps with Cosmos DB

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Container Apps Environment                │
│                         (VNet Integrated)                    │
│                                                              │
│  ┌─────────────────────┐     ┌───────────────────────────┐   │
│  │     Frontend        │     │         Backend           │   │
│  │  (external: true)   │     │    (external: false)      │   │
│  │                     │     │                           │   │
│  │  ┌───────────────┐  │     │  ┌─────────────────────┐  │   │
│  │  │    Nginx      │  │────>│  │      FastAPI        │  │   │
│  │  │  /api proxy   │  │http │  │    (Entra auth)     │  │   │
│  │  └───────────────┘  │     │  └─────────────────────┘  │   │
│  │         ▲           │     │             │             │   │
│  └─────────│───────────┘     └─────────────│─────────────┘   │
│            │                               │                 │
└────────────│───────────────────────────────│─────────────────┘
             │                               │
      HTTPS (public)                  Managed Identity
             │                               │
             │                               ▼
      ┌─────────────┐               ┌─────────────────┐
      │   Browser   │               │    Cosmos DB    │
      │ (MSAL auth) │               │   (RBAC auth)   │
      └─────────────┘               └─────────────────┘
```

## Prerequisites

| Scenario | Requirements |
|----------|--------------|
| **Azure Deployment** | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running), [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli), [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) |
| **Local Dev (Docker Compose)** | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running) |
| **Local Dev (Manual)** | Python 3.12+, Node.js 20+, [uv](https://docs.astral.sh/uv/) |

## Azure Deployment

> **Note:** Docker must be running before executing `azd up` — the deployment builds container images locally.

```bash
azd auth login
azd up
```

What gets provisioned:
- Azure Container Apps (frontend + backend) and Container Apps Environment
- Azure Container Registry
- Azure Cosmos DB with RBAC, databases/containers
- Entra ID app registrations (API and SPA)
- Managed Identity for backend with Cosmos RBAC

To set up CI/CD after provisioning:
```bash
./scripts/ci/setup_github_cicd.sh
```

Outputs:
- Public frontend URL
- Backend URL (internal in Azure, accessed by frontend)
- App registration IDs and environment values stored in `azd env`

Note: Authentication is enabled in Azure deployments.

## Configuration

How values are set:
- Preprovision hooks (`infra/hooks/preprovision.sh`) create Entra ID app registrations
- `azd env` stores values like `AZURE_TENANT_ID`, `BACKEND_API_CLIENT_ID`, `FRONTEND_SPA_CLIENT_ID`
- Bicep parameters (`infra/environments/*.parameters.json`) reference `${VAR_NAME}` from `azd env`
- Container Apps receive environment variables from Bicep outputs

Environment variables:
- **Auth:** `AZURE_TENANT_ID`, `BACKEND_API_CLIENT_ID`, `FRONTEND_SPA_CLIENT_ID`, `AUTH_ENABLED`, `VITE_AUTH_ENABLED`, `VITE_API_SCOPE`
- **Backend:** `COSMOS_ENDPOINT`, `CORS_ORIGINS`
- **Frontend:** `VITE_API_URL` (prod), `/api` proxy (local)

Local `.env` files:
- Backend: `backend/.env` (see `backend/.env.example`)
- Frontend: `frontend/.env.local` (see `frontend/.env.example`)

## Local Development (Secondary)

### Option A: Docker Compose (recommended)
```bash
docker compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

Enable auth locally by setting: `AUTH_ENABLED=true` and `VITE_AUTH_ENABLED=true`.

### Option B: Dev Container (optional)
1. Open folder in VS Code
2. Reopen in Container (Dev Containers extension)
3. Run local commands above

Includes Python 3.12, Node.js 20, uv, Azure CLI, and azd.

### Option C: Manual (optional)
```bash
# Quick start (auto-creates .env files if needed)
./scripts/dev/manual_setup.sh

# Backend (separate terminal)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Local defaults:
- Auth disabled
- Cosmos DB emulator for data storage

## Authentication

- Azure: Frontend uses MSAL; backend (FastAPI) validates Bearer tokens
- Local enablement:
   - Run `./scripts/auth/setup_local_auth.sh` to create local app registrations
   - Start with auth via `./scripts/dev/manual_setup.sh --auth` or `AUTH_ENABLED=true VITE_AUTH_ENABLED=true docker compose up`

Token examples:
- Auth disabled: use `X-User-Id` header
- Auth enabled: use `Authorization: Bearer <token>`

## Data Store (Cosmos DB)

### Option 1: Emulator (default)
```bash
docker compose up cosmosdb -d

# backend/.env
COSMOS_EMULATOR=true
```

Note (Apple Silicon M1/M2/M3): The Linux emulator does not support ARM64. Use Azure Cosmos DB instead or run Docker with Rosetta.

### Option 2: Azure Cosmos DB
```bash
az login

# backend/.env
COSMOS_EMULATOR=false
COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
```

Connectivity verification:
```bash
./scripts/dev/verify_cosmos.sh            # auto-detect
./scripts/dev/verify_cosmos.sh --emulator # emulator mode
./scripts/dev/verify_cosmos.sh --azure --endpoint https://your-account.documents.azure.com:443/
```

## Usage

1. Open the app at `http://localhost:3000` (or the deployed URL)
2. You’ll be redirected to the Decks page (`/#/decks`)
3. Click “📦 Create Sample Data” to populate sample decks (Spanish, French, German)
4. Click on a deck to view its cards
5. Click on a card to flip and reveal the answer
6. Use ✏️ and 🗑️ to edit or delete decks/cards

## API Reference

All endpoints (except `/healthz`) require authentication:
- In production: Bearer token from Entra ID (`Authorization: Bearer <token>`)
- In local dev with auth disabled: `X-User-Id` header

### Decks

| Endpoint           | Method | Description            |
|--------------------|--------|------------------------|
| `/decks`           | GET    | List all decks         |
| `/decks`           | POST   | Create a new deck      |
| `/decks/{id}`      | GET    | Get deck by ID         |
| `/decks/{id}`      | PUT    | Update a deck          |
| `/decks/{id}`      | DELETE | Delete deck and cards  |

### Cards

| Endpoint                      | Method | Description            |
|-------------------------------|--------|------------------------|
| `/decks/{deck_id}/cards`      | GET    | List cards in deck     |
| `/decks/{deck_id}/cards`      | POST   | Create a new card      |
| `/decks/{deck_id}/cards/{id}` | GET    | Get card by ID         |
| `/decks/{deck_id}/cards/{id}` | PUT    | Update a card          |
| `/decks/{deck_id}/cards/{id}` | DELETE | Delete a card          |

### Other

| Endpoint   | Method | Description                        |
|------------|--------|------------------------------------|
| `/`        | GET    | API info                           |
| `/healthz` | GET    | Health check                       |
| `/seed`    | POST   | Create sample flashcard data       |

## Testing

### Backend unit tests
```bash
cd backend
uv run pytest              # all tests
uv run pytest -v           # verbose
uv run pytest tests/test_auth.py
uv run pytest --cov=app --cov-report=html
```

Test categories:
- `tests/test_auth.py` – JWT validation, token handling, auth configuration
- `tests/test_cosmos.py` – Cosmos DB connection and settings
- `tests/test_api_integration.py` – API endpoint integration

### Smoke tests
```bash
./scripts/dev/smoke_tests.sh                # local backend
./scripts/dev/smoke_tests.sh https://api.example.com
./scripts/dev/smoke_tests.sh --with-token $(az account get-access-token --resource api://your-api-id --query accessToken -o tsv)
./scripts/dev/smoke_tests.sh --verbose
```

Verifies health checks, auth behaviors, CRUD, and invalid token handling.

## CI/CD

CI/CD setup is handled separately from Azure infrastructure provisioning.

After running `azd up`, configure GitHub Actions:
```bash
az login
gh auth login
./scripts/ci/setup_github_cicd.sh
```

What the setup script does:
- Creates Azure service principal with federated credentials
- Configures repository secrets and variables
- Adds federated credentials for environments (dev, staging, prod)

Workflows:
- `ci.yml` – PR: tests and validation
- `deploy-dev.yml` – Push to `main`: dev deploy
- `deploy-staging.yml` – Manual: staging deploy
- `deploy-prod.yml` – Manual: prod deploy

Triggers:
```bash
# Deploy to staging
gh workflow run deploy-staging.yml -f confirm=staging

# Deploy to production
gh workflow run deploy-prod.yml -f confirm=production
```

Environment protection:
- Create `dev`, `staging`, `prod` environments in GitHub
- Add required reviewers for `staging` and `prod`

## Troubleshooting

- **Permission denied during deployment:** Ensure service principal has `Contributor` on subscription; grant `Application.ReadWrite.All` for redirect URI updates.
- **App registrations not found:** Run `azd up` locally or `./infra/hooks/preprovision.sh`.
- **Environment variables missing:** Check repository secrets/variables; verify `BACKEND_API_CLIENT_ID` and `FRONTEND_SPA_CLIENT_ID` are set.
- **Cosmos emulator issues:** Confirm container running; on ARM64 use Azure Cosmos DB or Rosetta.

## Tech Stack

- **Frontend:** React 18, Vite, TypeScript, React Router
- **Backend:** FastAPI, Uvicorn, Pydantic
- **Database:** Azure Cosmos DB
- **Infrastructure:** Azure Container Apps, Bicep, azd

### Project Structure

```
├── azure.yaml                 # azd project manifest (environments, hooks, deployment)
├── docker-compose.yml         # Local dev orchestration (frontend, backend, Cosmos emulator)
│
├── backend/                   # FastAPI service
│   ├── Dockerfile             # Production image
│   ├── Dockerfile.dev         # Development image with hot reload
│   ├── pyproject.toml         # Python dependencies (uv/pytest config)
│   ├── app/
│   │   ├── main.py            # FastAPI entrypoint and router mounting
│   │   ├── auth/              # Entra ID/MSAL integration
│   │   │   ├── config.py      # Auth settings (tenant, client IDs, scopes)
│   │   │   ├── dependencies.py # FastAPI auth dependencies
│   │   │   └── token_validator.py # JWT validation and scope checks
│   │   ├── db/
│   │   │   └── cosmos.py      # Cosmos DB client (emulator vs Azure)
│   │   ├── models/            # Pydantic domain models
│   │   │   ├── card.py        # Card data shape and validation
│   │   │   └── deck.py        # Deck data shape and validation
│   │   ├── repositories/      # Data access layer
│   │   │   ├── card_repository.py # Card CRUD operations
│   │   │   └── deck_repository.py # Deck CRUD operations
│   │   └── routers/           # API route handlers
│   │       ├── cards.py       # Card endpoints
│   │       ├── decks.py       # Deck endpoints
│   │       └── seed.py        # Sample data population
│   └── tests/                 # Backend tests
│       ├── test_auth.py       # Token validation tests
│       ├── test_cosmos.py     # DB connection tests
│       └── test_api_integration.py # End-to-end API tests
│
├── frontend/                  # React + Vite SPA
│   ├── Dockerfile             # Production image (Nginx + built assets)
│   ├── index.html             # Vite HTML template
│   ├── nginx.conf             # Nginx config for static hosting + /api proxy
│   ├── package.json           # Node dependencies
│   ├── tsconfig.json          # TypeScript config
│   ├── vite.config.ts         # Vite build config
│   └── src/
│       ├── main.tsx           # App bootstrap
│       ├── App.tsx            # Routes and layout
│       ├── api/
│       │   └── client.ts      # API client with base URL and headers
│       ├── auth/              # MSAL auth wiring
│       │   ├── AuthProvider.tsx # Auth context provider
│       │   ├── useAuth.ts     # Auth hook
│       │   └── config.ts      # VITE_* auth vars and scopes
│       ├── components/        # UI components (forms, guards, login)
│       └── pages/             # Decks and Cards pages
│
├── infra/                     # Azure Bicep infrastructure
│   ├── main.bicep             # Root template (Container Apps, ACR, Cosmos)
│   ├── main.parameters.json   # Default parameters
│   ├── core/
│   │   ├── host/              # Container Apps environment and app definitions
│   │   └── data/              # Cosmos DB account, databases, RBAC
│   ├── environments/          # Environment-specific parameters
│   │   ├── dev.parameters.json
│   │   ├── staging.parameters.json
│   │   └── prod.parameters.json
│   └── hooks/                 # Pre/post provision scripts
│       ├── preprovision.sh    # Create app registrations
│       └── postprovision.sh   # Set environment variables
│
└── scripts/                   # Developer and CI utilities
    ├── auth/
    │   └── setup_local_auth.sh # Local Entra app registrations
    ├── ci/
    │   └── setup_github_cicd.sh # Configure GitHub Actions and secrets
    └── dev/
        ├── manual_setup.sh    # Bootstrap local env files
        ├── smoke_tests.sh     # API smoke tests
        └── verify_cosmos.sh   # Cosmos connectivity checks
```