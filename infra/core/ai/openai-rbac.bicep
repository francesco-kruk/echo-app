@description('The name of the Azure OpenAI account')
param accountName string

@description('Principal ID to assign Cognitive Services OpenAI User role')
param principalId string

@description('Principal type for role assignment (defaults to ServicePrincipal for managed identities)')
@allowed(['ServicePrincipal', 'User', 'Group'])
param principalType string = 'ServicePrincipal'

// Cognitive Services OpenAI User role
// https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/role-based-access-control
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// Reference existing Azure OpenAI account
resource openAIAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: accountName
}

// Role assignment for Managed Identity to access Azure OpenAI
// Using openAIAccount.id in guid ensures account is resolved before role assignment
resource openAIRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAIAccount.id, principalId, cognitiveServicesOpenAIUserRoleId)
  scope: openAIAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: principalId
    principalType: principalType
  }
}
