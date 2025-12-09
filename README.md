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
┌──────────────────────────────────────────────────────────────┐
│                    Azure Container Apps                      │
│                                                              │
│  ┌─────────────────────────┐    ┌─────────────────────────┐  │
│  │   Frontend (Public)     │    │   Backend (Public)      │  │
│  │   ┌─────────────────┐   │    │                         │  │
│  │   │  Nginx Static   │   │    │  FastAPI (port 8000)    │  │
│  │   │  Serves React   │   │───>│  /decks, /cards, /seed  │  │
│  │   │  SPA files      │   │    │                         │  │
│  │   └─────────────────┘   │    │  (public HTTPS)         │  │
│  └─────────────────────────┘    └─────────────────────────┘  │
│           ▲                              │                   │
└───────────│──────────────────────────────│───────────────────┘
            │                              │
     Public Internet              ┌────────▼────────┐
                                  │   Cosmos DB     │
                                  │  (decks/cards)  │
                                  └─────────────────┘
```

- **Frontend**: Publicly accessible, serves React SPA and calls backend API directly
- **Backend**: Publicly accessible with CORS configured to accept requests from the frontend origin

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

### Option 1: Dev Container (Recommended)

If you're using VS Code with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Open this folder in VS Code
2. Click "Reopen in Container" when prompted (or run `Dev Containers: Reopen in Container` from the command palette)
3. Wait for the container to build — all dependencies are installed automatically
4. Copy `.env.example` to `.env` in the `backend/` folder and configure Cosmos DB credentials
5. Run services with `docker compose up` or start them manually

The dev container includes Python 3.12, Node.js 20, uv, Azure CLI, and azd pre-configured.

### Option 2: Docker Compose

> **Prerequisites:** [Docker](https://docker.com/) & Docker Compose

```bash
# Copy and configure environment variables
cp backend/.env.example backend/.env
# Edit backend/.env with your Cosmos DB credentials

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
cp .env.example .env  # Configure Cosmos DB credentials
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

> **Note:** The frontend defaults to proxying API requests to `http://localhost:8000`. When running via Docker Compose, `VITE_API_TARGET` is automatically set to use the Docker hostname.

## Usage

1. Open the app at `http://localhost:3000` (or the deployed URL)
2. You'll be redirected to the **Decks** page (`/#/decks`)
3. Click **"📦 Create Sample Data"** to populate sample flashcard decks (Spanish, French, German basics)
4. Click on a deck to view its cards
5. Click on a card to flip and reveal the answer
6. Use the ✏️ and 🗑️ buttons to edit or delete decks/cards

## API Endpoints

All endpoints require the `X-User-Id` header for user identification.

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
- `CORS_ORIGINS` on backend → Frontend's public FQDN (allows cross-origin requests)
- `VITE_API_URL` → Backend's public URL (baked into frontend at build time)

**Local Development:**
- Backend: Configure Cosmos DB credentials in `backend/.env`
- Frontend: Uses Vite proxy (`VITE_API_TARGET`) for local dev, or set `VITE_API_URL` for direct API calls

**Azure Deployment:**
- `VITE_API_URL` is automatically set from Bicep outputs and passed to the frontend build
- CORS is automatically configured to allow only the frontend origin

## Development Notes

- **Frontend dev port:** 3000 (Vite with `/api` proxy to backend)
- **Frontend prod port:** 80 (Nginx serves static files, frontend calls backend directly)
- **Backend port:** 8000 (public HTTPS in Azure, HTTP locally)
- **API client:** Uses `VITE_API_URL` in production or `/api` proxy in local dev
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

- **Frontend:** React 18, Vite, TypeScript, React Router
- **Backend:** FastAPI, Uvicorn, Pydantic
- **Database:** Azure Cosmos DB
- **Infrastructure:** Azure Container Apps, Bicep, azd
