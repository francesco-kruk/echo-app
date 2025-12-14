@description('The name of the Cosmos DB account')
param accountName string

@description('Principal ID to assign Cosmos DB Data Contributor role (e.g., Container App managed identity)')
param principalId string

// Cosmos DB Built-in Data Contributor role ID
// https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-setup-rbac#built-in-role-definitions
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

// Reference existing Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: accountName
}

// Cosmos DB RBAC role assignment for managed identity
// Assigns "Cosmos DB Built-in Data Contributor" role to the specified principal
// Use deterministic name generation that includes subscription + scope + role + principal
resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  name: guid(subscription().id, cosmosAccount.id, cosmosDataContributorRoleId, principalId)
  parent: cosmosAccount
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    principalId: principalId
    scope: cosmosAccount.id
  }
}
