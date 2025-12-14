@description('Name of the Azure OpenAI account')
param accountName string

@description('Location for the resource')
param location string = resourceGroup().location

@description('Tags for the resource')
param tags object = {}

@description('Name of the model deployment')
param deploymentName string = 'gpt-4o'

@description('Model name to deploy')
param modelName string = 'gpt-4o'

@description('Model version to deploy')
param modelVersion string = '2024-11-20'

@description('Deployment capacity (tokens per minute in thousands)')
param deploymentCapacity int = 10

@description('SKU for the Azure OpenAI account')
param sku string = 'S0'

// Custom subdomain is required for token-based auth (Managed Identity)
var customSubDomainName = toLower(replace(accountName, '-', ''))

resource openAIAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: sku
  }
  properties: {
    customSubDomainName: customSubDomainName
    // Disable key-based auth - use Managed Identity only
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

// Deploy the GPT-4o model
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAIAccount
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: deploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

@description('The endpoint URL for the Azure OpenAI account')
output endpoint string = openAIAccount.properties.endpoint

@description('The name of the Azure OpenAI account')
output name string = openAIAccount.name

@description('The resource ID of the Azure OpenAI account')
output resourceId string = openAIAccount.id

@description('The name of the model deployment')
output deploymentName string = modelDeployment.name
