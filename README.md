# Echo App

A minimal React + FastAPI application designed for Azure Container Apps deployment with a secure internal backend architecture.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Azure Container Apps                      │
│                                                              │
│  ┌─────────────────────────┐    ┌─────────────────────────┐  │
│  │   Frontend (Public)     │    │  Backend (Internal)     │  │
│  │   ┌─────────────────┐   │    │                         │  │
│  │   │  Nginx Proxy    │   │───▶│  FastAPI (port 8000)    │  │
│  │   │  /api/* → backend   │    │  /echo, /healthz        │  │
│  │   │  /* → static files  │    │                         │  │
│  │   └─────────────────┘   │    │  (internal FQDN only)   │  │
│  └─────────────────────────┘    └─────────────────────────┘  │
│           ▲                                                  │
└───────────│──────────────────────────────────────────────────┘
            │
     Public Internet
```

- **Frontend**: Publicly accessible, serves static React app and proxies `/api/*` requests to the internal backend
- **Backend**: Internal-only (not accessible from the internet), communicates only within the Container Apps environment

## Project Structure

```
echo-app/
├── frontend/          # Vite + React frontend with Nginx proxy
│   ├── src/
│   ├── nginx.conf     # Nginx config for /api proxy
│   ├── Dockerfile     # Multi-stage build with Nginx
│   └── package.json
├── backend/           # FastAPI backend
│   ├── app/
│   ├── Dockerfile
│   └── pyproject.toml
├── infra/             # Azure Bicep templates
├── docker-compose.yml # Local development
├── azure.yaml         # Azure Developer CLI config
└── README.md
```

## Local Development

### Option 1: Dev Container (Recommended)

If you're using VS Code with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Open this folder in VS Code
2. Click "Reopen in Container" when prompted (or run `Dev Containers: Reopen in Container` from the command palette)
3. Wait for the container to build — all dependencies are installed automatically
4. Run services with `docker compose up` or start them manually

The dev container includes Python 3.12, Node.js 20, uv, Azure CLI, and azd pre-configured.

### Option 2: Docker Compose

> **Prerequisites:** [Docker](https://docker.com/) & Docker Compose

```bash
# Start both services with hot reload
docker compose up --build

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

### Option 3: Manual Setup

> **Prerequisites:** [Node.js](https://nodejs.org/) 20+, [Python](https://python.org/) 3.12+, [uv](https://docs.astral.sh/uv/)

**Backend:**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
VITE_API_TARGET=http://localhost:8000 npm run dev
```

> **Note:** The `VITE_API_TARGET` environment variable tells Vite to proxy API requests to your local backend instead of the Docker hostname.

## API Endpoints

| Endpoint   | Method | Description              |
|------------|--------|--------------------------|
| `/`        | GET    | API info                 |
| `/healthz` | GET    | Health check             |
| `/echo`    | POST   | Echo back `{ message }`  |

## Azure Deployment

> **Prerequisites:** [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Docker](https://docker.com/), and an Azure subscription
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
1. Create a resource group
2. Provision Azure Container Registry
3. Create Container Apps Environment
4. Build and push Docker images
5. Deploy frontend and backend Container Apps
6. Output the public URLs

### Environment Variables

The deployment automatically configures:
- `CORS_ORIGINS` on backend → Frontend's public FQDN
- `BACKEND_URL` on frontend → Backend internal endpoint used by the Nginx proxy

Clarification for `BACKEND_URL`:
- In this repo's `infra/main.bicep`, `BACKEND_URL` is currently set to `http://backend`. This assumes internal name resolution within the Azure Container Apps environment such that the frontend can reach the backend by the app name `backend`.
- If you prefer using the backend's internal FQDN, adjust `infra/main.bicep` to set `BACKEND_URL` to that value (e.g., `http://<internal-fqdn>`), and ensure the Nginx config (`frontend/nginx.conf`) continues to proxy `/api/*` to `${BACKEND_URL}`.

> **Note:** The backend is internal-only and not accessible from the internet. All API requests go through the frontend's Nginx proxy at `/api/*`.

## Development Notes

- **Frontend dev port:** 3000 (Vite with `/api` proxy to backend)
- **Frontend prod port:** 80 (Nginx with `/api` proxy to backend)
- **Backend port:** 8000
- **API path:** All frontend code uses `/api/*` paths (e.g., `/api/echo`, `/api/healthz`)
- **CORS:** Configured in `backend/.env` for local, auto-set for Azure

## CI/CD

This project includes a GitHub Actions workflow for automated Azure deployments.

### Setup

1. Run `azd pipeline config` to configure the pipeline:
   ```bash
   azd pipeline config
   ```
   This will:
   - Create a service principal with federated credentials
   - Set up GitHub repository variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_ENV_NAME`, `AZURE_LOCATION`)

2. Push to `main` to trigger automatic deployment

### Manual Trigger

You can also trigger the workflow manually from the **Actions** tab in GitHub.

## Tech Stack

- **Frontend:** React 18, Vite, TypeScript
- **Backend:** FastAPI, Uvicorn, Pydantic
- **Infrastructure:** Azure Container Apps, Bicep, azd
