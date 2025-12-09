@description('The name for the container apps environment')
param containerAppsEnvironmentName string

@description('The name for the container registry')
param containerRegistryName string

@description('The location for all resources')
param location string = resourceGroup().location

@description('Tags for all resources')
param tags object = {}

@description('Name prefix for resources')
param name string

@description('VNet name for Container Apps Environment')
param vnetName string = 'vnet-${name}'

@description('Address prefix for VNet')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Address prefix for Container Apps subnet')
param containerAppsSubnetAddressPrefix string = '10.0.0.0/23'

// Virtual Network for Container Apps
resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'container-apps'
        properties: {
          addressPrefix: containerAppsSubnetAddressPrefix
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
    ]
  }
}

// Log Analytics workspace for Container Apps
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${name}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Container Apps Environment with VNet integration and internal load balancer
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: vnet.properties.subnets[0].id
      internal: false  // Environment itself is not internal; individual apps control external/internal ingress
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

output environmentName string = containerAppsEnvironment.name
output environmentId string = containerAppsEnvironment.id
output defaultDomain string = containerAppsEnvironment.properties.defaultDomain
output registryName string = containerRegistry.name
output registryLoginServer string = containerRegistry.properties.loginServer
