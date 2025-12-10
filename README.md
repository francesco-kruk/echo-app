# Echo App

A flashcard application built with React + FastAPI, designed for Azure Container Apps deployment with Cosmos DB backend.

## Features

- 📚 **Deck Management** - Create, edit, and delete flashcard decks
- 🃏 **Card Management** - Add, edit, and delete cards within decks
- 🔄 **Interactive Flashcards** - Click to flip cards and reveal answers
- 📦 **Sample Data** - One-click button to populate sample flashcard decks
- 🌐 **Azure Ready** - Deploys to Azure Container Apps with Cosmos DB

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Container Apps Environment                    │
│                         (VNet Integrated)                        │
│                                                                  │
│  ┌─────────────────────┐     ┌─────────────────────────────┐   │
│  │     Frontend        │     │         Backend             │   │
│  │  (external: true)   │     │    (external: false)        │   │
│  │                     │     │                             │   │
│  │  ┌───────────────┐  │     │  ┌───────────────────────┐  │   │
│  │  │    Nginx      │  │────▶│  │      FastAPI          │  │   │
│  │  │  /api proxy   │  │http │  │  (Entra auth)         │  │   │
│  │  └───────────────┘  │     │  └───────────────────────┘  │   │
│  │         ▲           │     │             │               │   │
│  └─────────│───────────┘     └─────────────│───────────────┘   │
│            │                               │                    │
└────────────│───────────────────────────────│────────────────────┘
             │                               │
    HTTPS (public)                  Managed Identity
             │                               │
             │                               ▼
      ┌──────┴──────┐              ┌─────────────────┐
      │   Browser   │              │    Cosmos DB    │
      │ (MSAL auth) │              │   (RBAC auth)   │
      └─────────────┘              └─────────────────┘
```

### Security Layers

- **Network Isolation**: Backend is internal-only, not accessible from internet
- **Authentication**: Entra ID tokens required for all API calls (validated by FastAPI)
- **CORS**: Backend only accepts requests from frontend origin
- **Managed Identity**: No secrets for Cosmos DB access (system-assigned identity)

## Project Structure

```
echo-app/
├── frontend/           # Vite + React frontend
│   ├── src/
│   │   ├── api/        # API client for backend communication
│   │   ├── pages/      # DecksPage, CardsPage
│   │   ├── components/ # DeckForm, CardForm modals
│   │   └── main.tsx    # React Router setup
│   ├── nginx.conf      # Nginx config for static file serving
│   ├── Dockerfile      # Multi-stage build with Nginx
│   └── package.json
├── backend/            # FastAPI backend
│   ├── app/
│   │   ├── routers/    # decks, cards, seed endpoints
│   │   ├── models/     # Pydantic models
│   │   ├── repositories/ # Cosmos DB data access
│   │   └── db/         # Cosmos DB connection
│   ├── Dockerfile
│   └── pyproject.toml
├── infra/              # Azure Bicep templates
├── docker-compose.yml  # Local development
├── azure.yaml          # Azure Developer CLI config
└── README.md
```

## Local Development

### Quick Start

**Option A: Docker Compose (Recommended)**
```bash
docker compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

**Option B: Manual Setup**
```bash
./manual_setup.sh
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
```

Both options run with authentication **disabled** by default, using the Cosmos DB emulator for data storage.

### Development Options

#### Option 1: Dev Container

If you're using VS Code with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Open this folder in VS Code
2. Click "Reopen in Container" when prompted
3. Run `docker compose up` or `./manual_setup.sh`

The dev container includes Python 3.12, Node.js 20, uv, Azure CLI, and azd pre-configured.

#### Option 2: Docker Compose

> **Prerequisites:** [Docker](https://docker.com/) & Docker Compose

```bash
# Start all services (frontend, backend, Cosmos DB emulator)
docker compose up --build

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

Environment variables are configured via `docker-compose.yml`. To enable authentication, set `AUTH_ENABLED=true` and `VITE_AUTH_ENABLED=true` before running.

#### Option 3: Manual Setup

> **Prerequisites:** [Node.js](https://nodejs.org/) 20+, [Python](https://python.org/) 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# Quick start (auto-creates .env files if needed)
./manual_setup.sh

# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
```

The script automatically:
- Creates `backend/.env` and `frontend/.env.local` if they don't exist
- Installs dependencies for both services
- Checks if Cosmos DB emulator is running
- Starts frontend and backend with hot reload

**Manual service startup:**

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Local Authentication with Entra ID

To test with real Entra ID authentication locally:

```bash
# 1. Create app registrations (requires Azure CLI)
./setup_local_auth.sh

# 2. Start the Cosmos DB emulator
docker compose up cosmosdb -d

# 3. Start with auth enabled
./manual_setup.sh --auth
# OR
AUTH_ENABLED=true VITE_AUTH_ENABLED=true docker compose up
```

The `setup_local_auth.sh` script:
- Creates `echo-api-local` and `echo-spa-local` app registrations
- Configures API scopes and SPA redirect URIs
- Updates `.env` files to enable authentication
- Attempts to grant admin consent automatically

To disable auth later: `./setup_local_auth.sh --disable`

### Cosmos DB Options

**Option 1: Cosmos DB Emulator (Default)**
```bash
# Start the emulator
docker compose up cosmosdb -d

# Set in backend/.env
COSMOS_EMULATOR=true
```

> ⚠️ **Apple Silicon (M1/M2/M3) Note:** The Cosmos DB Linux emulator does not support ARM64 architecture. If you're on Apple Silicon, use **Option 2** (Azure Cosmos DB) instead, or run Docker with Rosetta emulation enabled.

**Option 2: Azure Cosmos DB**
```bash
# Login to Azure
az login

# Set in backend/.env
COSMOS_EMULATOR=false
COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
```

> **Note:** The frontend defaults to proxying API requests to the backend. When running via Docker Compose, `VITE_API_TARGET` is automatically set to use the Docker hostname.

## Usage

1. Open the app at `http://localhost:3000` (or the deployed URL)
2. You'll be redirected to the **Decks** page (`/#/decks`)
3. Click **"📦 Create Sample Data"** to populate sample flashcard decks (Spanish, French, German basics)
4. Click on a deck to view its cards
5. Click on a card to flip and reveal the answer
6. Use the ✏️ and 🗑️ buttons to edit or delete decks/cards

## API Endpoints

All endpoints (except `/healthz`) require authentication:
- **In production**: Bearer token from Entra ID (`Authorization: Bearer <token>`)
- **In local dev with auth disabled**: `X-User-Id` header for user identification

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

## Azure Deployment

> **Prerequisites:** 
> - [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
> - [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
> - [Docker](https://docker.com/)
> - Azure subscription with permissions to create app registrations
>
> 💡 **Tip:** Using the dev container? Azure CLI, azd, and Docker are already installed — just run the commands below.

Deploy to Azure Container Apps with a single command:

```bash
# Login to Azure
azd auth login

# Deploy infrastructure and apps
azd up
```

This will:
1. Create Entra ID app registrations (echo-api, echo-spa)
2. Create a resource group
3. Provision Azure Container Registry, Container Apps Environment, and Cosmos DB
4. Build and push Docker images
5. Deploy frontend and backend Container Apps
6. Configure Managed Identity and RBAC for Cosmos DB
7. **Automatically configure GitHub Actions CI/CD** (prompts to install/authenticate GitHub CLI if needed)
8. Output the public URLs

### Automatic CI/CD Setup

During `azd up`, the postprovision hook will:
- **If GitHub CLI is not installed:** Prompt to install it automatically (supports macOS/Linux)
- **If GitHub CLI is not authenticated:** Prompt you to run `gh auth login`
- **If authenticated:** Automatically configure GitHub Actions with all required secrets and variables

Once configured, pushing to `main` triggers automatic deployment to the dev environment.

> **Note:** In non-interactive environments (CI), the CLI installation prompt is skipped. For manual setup:
> ```bash
> gh auth login
> azd pipeline config
> gh secret set BACKEND_API_CLIENT_ID --body "$(azd env get-value BACKEND_API_CLIENT_ID)"
> gh secret set FRONTEND_SPA_CLIENT_ID --body "$(azd env get-value FRONTEND_SPA_CLIENT_ID)"
> ```

### Environment Variables

The deployment automatically configures all environment variables via the `azd` provisioning process:

#### Automatic Configuration Flow

1. **preprovision hooks** (`infra/hooks/preprovision.sh`) create Entra ID app registrations
2. **azd env** stores the values: `AZURE_TENANT_ID`, `BACKEND_API_CLIENT_ID`, `FRONTEND_SPA_CLIENT_ID`, etc.
3. **Bicep parameters** (`infra/environments/*.parameters.json`) reference these values using `${VAR_NAME}` syntax
4. **Container Apps** receive environment variables from Bicep outputs

#### Configuration Reference

| Variable | Source | Used By | Description |
|----------|--------|---------|-------------|
| `AZURE_TENANT_ID` | preprovision | Backend, Frontend | Entra ID tenant ID |
| `BACKEND_API_CLIENT_ID` | preprovision | Bicep | Backend API app registration ID |
| `FRONTEND_SPA_CLIENT_ID` | preprovision | Bicep | Frontend SPA app registration ID |
| `VITE_AZURE_CLIENT_ID` | preprovision | Frontend build | SPA client ID for MSAL |
| `VITE_TENANT_ID` | preprovision | Frontend build | Tenant ID for MSAL |
| `VITE_API_SCOPE` | preprovision | Frontend build | API scopes for token requests |
| `COSMOS_ENDPOINT` | Bicep output | Backend | Cosmos DB endpoint URL |
| `AUTH_ENABLED` | Bicep | Backend | Enable/disable token validation |

**Local Development:**
- Backend: Copy `backend/.env.example` to `backend/.env`
- Frontend: Copy `frontend/.env.example` to `frontend/.env.local`
- Set `AUTH_ENABLED=false` and `VITE_AUTH_ENABLED=false` to skip Entra auth locally

**Azure Deployment:**
- All values are automatically configured — no manual configuration needed

## Development Notes

- **Frontend dev port:** 3000 (Vite with `/api` proxy to backend)
- **Frontend prod port:** 80 (Nginx serves static files, frontend calls backend directly)
- **Backend port:** 8000 (public HTTPS in Azure, HTTP locally)
- **API client:** Uses `VITE_API_URL` in production or `/api` proxy in local dev
- **CORS:** Configured in `backend/.env` for local, auto-set for Azure

## CI/CD

This project includes GitHub Actions workflows for automated deployments with environment promotion.

### Workflow Structure

| Workflow | Trigger | Environment | Description |
|----------|---------|-------------|-------------|
| `ci.yml` | Pull Request | - | Runs tests and validation |
| `deploy-dev.yml` | Push to `main` | dev | Automatic deployment to dev |
| `deploy-staging.yml` | Manual | staging | Deploy to staging with confirmation |
| `deploy-prod.yml` | Manual | prod | Deploy to production with confirmation |

### Initial Setup

Run the setup script to configure GitHub Actions with Azure:

```bash
./setup_github_cicd.sh
```

This automated script will:
1. **Create a service principal** with federated credentials for GitHub Actions
2. **Verify app registrations** (creates them if not present)
3. **Configure GitHub repository** with variables and secrets
4. **Set up federated credentials** for each environment

#### Prerequisites for Setup Script

- Azure CLI logged in (`az login`) with permissions to create app registrations
- GitHub CLI authenticated (`gh auth login`) with repo permissions
- App registrations created (run `azd up` locally first, or `./infra/hooks/preprovision.sh`)

#### Manual Setup Alternative

If you prefer manual setup:

1. **Create a service principal:**
   ```bash
   az ad sp create-for-rbac --name "github-actions-echo-app" --role contributor \
     --scopes /subscriptions/<subscription-id> --json-auth
   ```

2. **Configure federated credentials** in Azure Portal:
   - Go to Entra ID > App registrations > github-actions-echo-app
   - Add federated credentials for:
     - `repo:owner/repo:ref:refs/heads/main`
     - `repo:owner/repo:environment:dev`
     - `repo:owner/repo:environment:staging`
     - `repo:owner/repo:environment:prod`

3. **Set GitHub repository variables:**
   - `AZURE_CLIENT_ID` - Service principal client ID
   - `AZURE_TENANT_ID` - Azure tenant ID
   - `AZURE_SUBSCRIPTION_ID` - Azure subscription ID

4. **Set GitHub repository secrets:**
   - `BACKEND_API_CLIENT_ID` - Backend API app registration ID
   - `FRONTEND_SPA_CLIENT_ID` - Frontend SPA app registration ID

### Environment Protection Rules

For staging and production deployments, configure protection rules in GitHub:

1. Go to **Settings** > **Environments**
2. Create environments: `dev`, `staging`, `prod`
3. For `staging` and `prod`:
   - Add **required reviewers**
   - Optionally restrict to specific branches

### Deployment Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Develop   │     │   Pull      │     │   Review    │     │   Deploy    │
│   Feature   │────▶│   Request   │────▶│   & Merge   │────▶│   to Dev    │
│             │     │   (CI runs) │     │   to main   │     │ (automatic) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                        ┌──────────────────────────┘
                                        ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              Manual Workflow Dispatch                │
                    ├─────────────────────────────────────────────────────┤
                    │  Deploy to Staging  ──▶  Deploy to Production       │
                    │  (type "staging")       (type "production")         │
                    │       │                        │                    │
                    │       ▼                        ▼                    │
                    │  ┌─────────┐              ┌─────────┐               │
                    │  │ staging │              │  prod   │               │
                    │  │  env    │              │  env    │               │
                    │  └─────────┘              └─────────┘               │
                    └─────────────────────────────────────────────────────┘
```

### Triggering Deployments

**Automatic (Dev):**
- Push to `main` branch triggers deployment to dev environment

**Manual (Staging/Prod):**
```bash
# Deploy to staging
gh workflow run deploy-staging.yml -f confirm=staging

# Deploy to production
gh workflow run deploy-prod.yml -f confirm=production
```

Or via GitHub UI:
1. Go to **Actions** tab
2. Select workflow (e.g., "Deploy to Staging")
3. Click **Run workflow**
4. Type the confirmation word (`staging` or `production`)
5. Click **Run workflow**

### What Gets Deployed

Each deployment:
1. Initializes azd environment with app registration IDs
2. Provisions/updates Azure infrastructure (Container Apps, Cosmos DB, etc.)
3. Builds and pushes Docker images
4. Deploys frontend and backend containers
5. Updates SPA redirect URIs with deployed frontend URL

### Troubleshooting

**"Permission denied" during deployment:**
- Ensure the service principal has `Contributor` role on the subscription
- For redirect URI updates, grant `Application.ReadWrite.All` API permission

**App registrations not found:**
- Run `azd up` locally first to create the app registrations
- Or manually run `./infra/hooks/preprovision.sh`

**Environment variables missing:**
- Check GitHub repository secrets and variables
- Verify `BACKEND_API_CLIENT_ID` and `FRONTEND_SPA_CLIENT_ID` secrets are set

## Testing

### Running Unit Tests

**Backend tests:**
```bash
cd backend

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_auth.py

# Run with coverage
uv run pytest --cov=app --cov-report=html
```

**Test categories:**
- `tests/test_auth.py` - JWT validation, token handling, auth configuration
- `tests/test_cosmos.py` - Cosmos DB connection and settings
- `tests/test_api_integration.py` - API endpoint integration tests

### Smoke Tests

Run end-to-end smoke tests against a running backend:

```bash
# Test against local development server
./smoke_tests.sh

# Test against custom URL
./smoke_tests.sh https://api.example.com

# Test with a real Entra ID token
./smoke_tests.sh --with-token $(az account get-access-token --resource api://your-api-id --query accessToken -o tsv)

# Verbose output
./smoke_tests.sh --verbose
```

**What smoke tests verify:**
- Public endpoints (health check) work without authentication
- Protected endpoints return 401 without valid tokens
- Protected endpoints work with X-User-Id header (auth disabled mode)
- CRUD operations (create/delete deck)
- Invalid token rejection

### Cosmos DB Verification

Verify Cosmos DB connectivity:

```bash
# Auto-detect mode (emulator or Azure)
./verify_cosmos.sh

# Test with local emulator
./verify_cosmos.sh --emulator

# Test with Azure credentials
./verify_cosmos.sh --azure --endpoint https://your-account.documents.azure.com:443/
```

**Authentication modes verified:**
1. **Emulator mode**: Uses well-known emulator key
2. **Azure CLI**: Uses `az login` credentials locally
3. **Managed Identity**: Used automatically in Azure Container Apps

### CI Pipeline Tests

The CI pipeline (`.github/workflows/ci.yml`) runs on every pull request:

```yaml
# Automated checks:
- Backend: pytest, type checking, linting
- Frontend: TypeScript build, linting
- Infrastructure: Bicep template validation
```

### Manual API Testing

**With auth disabled (local dev):**
```bash
# List decks
curl -H "X-User-Id: test-user" http://localhost:8000/decks

# Create a deck
curl -X POST -H "Content-Type: application/json" -H "X-User-Id: test-user" \
  -d '{"name": "My Deck", "description": "Test"}' \
  http://localhost:8000/decks
```

**With auth enabled:**
```bash
# Get a token
TOKEN=$(az account get-access-token --resource api://your-api-id --query accessToken -o tsv)

# Use Bearer token
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/decks
```

## Tech Stack

- **Frontend:** React 18, Vite, TypeScript, React Router
- **Backend:** FastAPI, Uvicorn, Pydantic
- **Database:** Azure Cosmos DB
- **Infrastructure:** Azure Container Apps, Bicep, azd
