targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Whether to enable Cosmos DB Free Tier (only one per subscription)')
param cosmosFreeTierEnabled bool = false

@description('Whether the backend container app is externally accessible')
param backendExternal bool = false

@description('Azure AD Tenant ID for authentication')
param tenantId string = ''

@description('Backend API App Registration Client ID')
param backendApiClientId string = ''

@description('Frontend SPA App Registration Client ID')
param frontendSpaClientId string = ''

// Tags that should be applied to all resources
var tags = {
  'azd-env-name': environmentName
}

// Computed resource names (used to avoid circular dependencies)
var cosmosAccountName = 'cosmos-${environmentName}'
var cosmosDatabaseName = 'echoapp'
var cosmosDecksContainerName = 'decks'
var cosmosCardsContainerName = 'cards'

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

// Container apps host (including container registry)
module containerApps './core/host/container-apps.bicep' = {
  name: 'container-apps'
  scope: rg
  params: {
    name: 'app'
    location: location
    tags: tags
    containerAppsEnvironmentName: 'cae-${environmentName}'
    containerRegistryName: 'cr${replace(environmentName, '-', '')}${uniqueString(rg.id)}'
  }
}

// Cosmos DB account, database, and containers
module cosmos './core/data/cosmos.bicep' = {
  name: 'cosmos'
  scope: rg
  params: {
    accountName: cosmosAccountName
    location: location
    tags: tags
    enableFreeTier: cosmosFreeTierEnabled
    databaseName: cosmosDatabaseName
    decksContainerName: cosmosDecksContainerName
    cardsContainerName: cosmosCardsContainerName
    enableServerless: true
  }
}

// Frontend container app (public, proxies API calls to internal backend via nginx)
module frontend './core/host/container-app.bicep' = {
  name: 'frontend'
  scope: rg
  params: {
    name: 'frontend'
    location: location
    tags: union(tags, { 'azd-service-name': 'frontend' })
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    targetPort: 80  // Nginx serves static files on port 80
    external: true
    env: [
      {
        // Internal backend URL for nginx proxy (injected at runtime via envsubst)
        // Using HTTP since backend has allowInsecure=true for internal communication
        // Container Apps routes to target port automatically via ingress
        name: 'BACKEND_URL'
        value: 'http://backend'  // Container Apps internal DNS name
      }
    ]
  }
}

// Backend container app (internal, called by frontend via nginx proxy)
// Uses managed identity for Cosmos DB access (no secrets needed)
module backend './core/host/container-app.bicep' = {
  name: 'backend'
  scope: rg
  params: {
    name: 'backend'
    location: location
    tags: union(tags, { 'azd-service-name': 'backend' })
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    targetPort: 8000
    external: backendExternal  // Internal: only accessible within Container Apps Environment
    allowInsecure: !backendExternal  // Allow HTTP for internal container-to-container communication
    enableManagedIdentity: true  // Enable system-assigned managed identity for Cosmos DB access
    minReplicas: 1  // Keep at least 1 replica running for internal service availability
    env: [
      {
        name: 'PORT'
        value: '8000'
      }
      {
        // CORS allows requests from public frontend URL
        // Computed from Container Apps Environment default domain to avoid circular dependency
        name: 'CORS_ORIGINS'
        value: 'https://frontend.${containerApps.outputs.defaultDomain}'
      }
      {
        name: 'COSMOS_ENDPOINT'
        value: cosmos.outputs.endpoint
      }
      {
        name: 'COSMOS_DB_NAME'
        value: cosmosDatabaseName
      }
      {
        name: 'COSMOS_DECKS_CONTAINER'
        value: cosmosDecksContainerName
      }
      {
        name: 'COSMOS_CARDS_CONTAINER'
        value: cosmosCardsContainerName
      }
      {
        name: 'AUTH_ENABLED'
        value: 'true'
      }
      {
        name: 'AZURE_TENANT_ID'
        value: tenantId
      }
      {
        name: 'AZURE_API_SCOPE'
        value: 'api://${backendApiClientId}'
      }
      {
        name: 'AZURE_API_APP_ID'
        value: backendApiClientId
      }
    ]
  }
}

// Cosmos DB RBAC role assignment for backend managed identity
// This must be deployed after both cosmos and backend to get the principal ID
module cosmosRbac './core/data/cosmos-rbac.bicep' = {
  name: 'cosmos-rbac'
  scope: rg
  params: {
    accountName: cosmosAccountName
    principalId: backend.outputs.principalId
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName
output BACKEND_URI string = backend.outputs.uri  // Internal API endpoint (not accessible from internet)
output BACKEND_INTERNAL_FQDN string = backend.outputs.fqdn  // Internal FQDN for container-to-container calls
output FRONTEND_URI string = frontend.outputs.uri  // Public frontend (gated by MSAL auth)
// Frontend uses /api proxy to reach backend - no direct URL needed at build time
output VITE_AZURE_CLIENT_ID string = frontendSpaClientId  // For frontend MSAL config
output VITE_TENANT_ID string = tenantId  // For frontend MSAL config
output VITE_API_SCOPE string = 'api://${backendApiClientId}/Decks.ReadWrite api://${backendApiClientId}/Cards.ReadWrite'  // For frontend to request API scopes
