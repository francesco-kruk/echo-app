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

// @description('Id of the user or app to assign application roles')
// param principalId string = ''

// Tags that should be applied to all resources
var tags = {
  'azd-env-name': environmentName
}

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
    accountName: 'cosmos-${environmentName}'
    location: location
    tags: tags
    enableFreeTier: cosmosFreeTierEnabled
    databaseName: 'echoapp'
    decksContainerName: 'decks'
    cardsContainerName: 'cards'
    enableServerless: true
  }
}

// Backend container app (public, called directly by frontend)
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
    external: true  // Public: directly accessible by frontend
    allowInsecure: false  // Use HTTPS for public access
    secrets: [
      {
        name: 'cosmos-key'
        value: cosmos.outputs.primaryKey
      }
    ]
    env: [
      {
        name: 'PORT'
        value: '8000'
      }
      {
        // CORS allows requests from public frontend URL
        name: 'CORS_ORIGINS'
        value: 'https://${frontend.outputs.fqdn}'
      }
      {
        name: 'COSMOS_ENDPOINT'
        value: cosmos.outputs.endpoint
      }
      {
        name: 'COSMOS_KEY'
        secretRef: 'cosmos-key'
      }
      {
        name: 'COSMOS_DB_NAME'
        value: cosmos.outputs.databaseName
      }
      {
        name: 'COSMOS_DECKS_CONTAINER'
        value: cosmos.outputs.decksContainerName
      }
      {
        name: 'COSMOS_CARDS_CONTAINER'
        value: cosmos.outputs.cardsContainerName
      }
    ]
  }
}

// Frontend container app (public, calls backend directly)
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
    env: []  // No env vars needed - API URL is injected at build time via azd
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName
output BACKEND_URI string = backend.outputs.uri  // Public API endpoint
output FRONTEND_URI string = frontend.outputs.uri  // Public frontend
output VITE_API_URL string = backend.outputs.uri  // For frontend build to know backend URL
