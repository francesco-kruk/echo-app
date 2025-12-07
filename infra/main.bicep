targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

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

// Backend container app (internal-only, accessed via frontend proxy)
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
    external: false  // Internal-only: not publicly accessible
    env: [
      {
        name: 'PORT'
        value: '8000'
      }
      {
        // CORS allows requests from frontend proxy (internal communication)
        name: 'CORS_ORIGINS'
        value: 'https://${frontend.outputs.fqdn}'
      }
    ]
  }
}

// Frontend container app (public, proxies /api to internal backend)
module frontend './core/host/container-app.bicep' = {
  name: 'frontend'
  scope: rg
  params: {
    name: 'frontend'
    location: location
    tags: union(tags, { 'azd-service-name': 'frontend' })
    containerAppsEnvironmentName: containerApps.outputs.environmentName
    containerRegistryName: containerApps.outputs.registryName
    targetPort: 80  // Nginx serves on port 80
    external: true
    env: [
      {
        // Backend internal FQDN for nginx proxy
        name: 'BACKEND_URL'
        value: 'http://backend'
      }
    ]
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApps.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApps.outputs.registryName
output BACKEND_URI string = backend.outputs.uri  // Internal-only, not publicly accessible
output FRONTEND_URI string = frontend.outputs.uri  // Public entry point, proxies /api to backend
