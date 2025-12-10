@description('The name of the container app')
param name string

@description('The location for all resources')
param location string = resourceGroup().location

@description('Tags for all resources')
param tags object = {}

@description('The name of the container apps environment')
param containerAppsEnvironmentName string

@description('The name of the container registry')
param containerRegistryName string

@description('The target port for the container')
param targetPort int = 80

@description('Whether the container app is externally accessible')
param external bool = true

@description('Environment variables for the container')
param env array = []

@description('Container image to deploy (leave empty for azd to fill)')
param imageName string = ''

@description('Additional secrets for the container app')
param secrets array = []

@description('Allow insecure (HTTP) traffic for internal container-to-container communication')
param allowInsecure bool = false

// Reference existing Container Apps Environment
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppsEnvironmentName
}

// Reference existing Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: external
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: allowInsecure
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: concat([
        {
          name: 'registry-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
      ], secrets)
    }
    template: {
      containers: [
        {
          name: 'main'
          image: !empty(imageName) ? imageName : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: env
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 10
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output uri string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output name string = containerApp.name
