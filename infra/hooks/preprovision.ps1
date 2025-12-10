# preprovision.ps1 - Creates Entra ID app registrations for echo-app
# This script is idempotent - it will skip creation if apps already exist

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "Echo App - Entra ID App Registration Setup"
Write-Host "=========================================="

# Get tenant ID from current Azure CLI login
$TENANT_ID = az account show --query tenantId -o tsv
if ([string]::IsNullOrEmpty($TENANT_ID)) {
    Write-Error "ERROR: Not logged in to Azure CLI. Run 'az login' first."
    exit 1
}
Write-Host "Using Tenant ID: $TENANT_ID"

# App display names
$API_APP_NAME = "echo-api"
$SPA_APP_NAME = "echo-spa"

# ============================================
# Backend API App Registration
# ============================================
Write-Host ""
Write-Host "Checking for Backend API app registration ($API_APP_NAME)..."

$API_APP_ID = az ad app list --filter "displayName eq '$API_APP_NAME'" --query "[0].appId" -o tsv 2>$null

if ([string]::IsNullOrEmpty($API_APP_ID) -or $API_APP_ID -eq "null") {
    Write-Host "Creating Backend API app registration..."
    
    # Create the app
    $API_APP_ID = az ad app create `
        --display-name $API_APP_NAME `
        --sign-in-audience "AzureADMyOrg" `
        --query "appId" -o tsv
    
    Write-Host "Created app with ID: $API_APP_ID"
    
    # Set the Application ID URI
    az ad app update `
        --id $API_APP_ID `
        --identifier-uris "api://$API_APP_ID"
    
    Write-Host "Set Application ID URI: api://$API_APP_ID"
    
    # Generate UUIDs for scopes
    $SCOPE_ID_1 = [guid]::NewGuid().ToString()
    $SCOPE_ID_2 = [guid]::NewGuid().ToString()
    $SCOPE_ID_3 = [guid]::NewGuid().ToString()
    $SCOPE_ID_4 = [guid]::NewGuid().ToString()
    
    # Define and add API scopes
    $scopesJson = @"
{
  "oauth2PermissionScopes": [
    {
      "id": "$SCOPE_ID_1",
      "adminConsentDescription": "Allows the app to read decks on behalf of the signed-in user",
      "adminConsentDisplayName": "Read Decks",
      "isEnabled": true,
      "type": "User",
      "userConsentDescription": "Allows the app to read your decks",
      "userConsentDisplayName": "Read your decks",
      "value": "Decks.Read"
    },
    {
      "id": "$SCOPE_ID_2",
      "adminConsentDescription": "Allows the app to read and write decks on behalf of the signed-in user",
      "adminConsentDisplayName": "Read and Write Decks",
      "isEnabled": true,
      "type": "User",
      "userConsentDescription": "Allows the app to read and modify your decks",
      "userConsentDisplayName": "Read and modify your decks",
      "value": "Decks.ReadWrite"
    },
    {
      "id": "$SCOPE_ID_3",
      "adminConsentDescription": "Allows the app to read cards on behalf of the signed-in user",
      "adminConsentDisplayName": "Read Cards",
      "isEnabled": true,
      "type": "User",
      "userConsentDescription": "Allows the app to read your cards",
      "userConsentDisplayName": "Read your cards",
      "value": "Cards.Read"
    },
    {
      "id": "$SCOPE_ID_4",
      "adminConsentDescription": "Allows the app to read and write cards on behalf of the signed-in user",
      "adminConsentDisplayName": "Read and Write Cards",
      "isEnabled": true,
      "type": "User",
      "userConsentDescription": "Allows the app to read and modify your cards",
      "userConsentDisplayName": "Read and modify your cards",
      "value": "Cards.ReadWrite"
    }
  ]
}
"@
    
    $tempFile = [System.IO.Path]::GetTempFileName()
    $scopesJson | Out-File -FilePath $tempFile -Encoding UTF8
    
    az ad app update `
        --id $API_APP_ID `
        --set api=@$tempFile
    
    Remove-Item $tempFile
    Write-Host "Added API scopes: Decks.Read, Decks.ReadWrite, Cards.Read, Cards.ReadWrite"
} else {
    Write-Host "Backend API app already exists with ID: $API_APP_ID"
}

# Get the scope IDs for later use
$DECKS_READWRITE_SCOPE_ID = az ad app show --id $API_APP_ID --query "api.oauth2PermissionScopes[?value=='Decks.ReadWrite'].id" -o tsv
$CARDS_READWRITE_SCOPE_ID = az ad app show --id $API_APP_ID --query "api.oauth2PermissionScopes[?value=='Cards.ReadWrite'].id" -o tsv

# ============================================
# Frontend SPA App Registration
# ============================================
Write-Host ""
Write-Host "Checking for Frontend SPA app registration ($SPA_APP_NAME)..."

$SPA_APP_ID = az ad app list --filter "displayName eq '$SPA_APP_NAME'" --query "[0].appId" -o tsv 2>$null

if ([string]::IsNullOrEmpty($SPA_APP_ID) -or $SPA_APP_ID -eq "null") {
    Write-Host "Creating Frontend SPA app registration..."
    
    # Create the SPA app with redirect URIs
    $SPA_APP_ID = az ad app create `
        --display-name $SPA_APP_NAME `
        --sign-in-audience "AzureADMyOrg" `
        --enable-id-token-issuance true `
        --query "appId" -o tsv
    
    Write-Host "Created SPA app with ID: $SPA_APP_ID"
    
    # Configure SPA redirect URIs
    az ad app update `
        --id $SPA_APP_ID `
        --spa-redirect-uris "http://localhost:5173" "http://localhost:3000"
    
    Write-Host "Configured SPA redirect URIs for local development"
    
    # Add API permissions for the SPA to call the backend
    az ad app permission add `
        --id $SPA_APP_ID `
        --api $API_APP_ID `
        --api-permissions "$DECKS_READWRITE_SCOPE_ID=Scope" "$CARDS_READWRITE_SCOPE_ID=Scope"
    
    Write-Host "Added API permissions for SPA to call Backend API"
} else {
    Write-Host "Frontend SPA app already exists with ID: $SPA_APP_ID"
}

# ============================================
# Grant Admin Consent (if possible)
# ============================================
Write-Host ""
Write-Host "Attempting to grant admin consent..."

try {
    az ad app permission admin-consent --id $SPA_APP_ID 2>$null
    Write-Host "Admin consent granted successfully"
} catch {
    Write-Host "WARNING: Could not grant admin consent automatically."
    Write-Host "An admin needs to grant consent in the Azure Portal:"
    Write-Host "  1. Go to Azure Portal > Entra ID > App registrations"
    Write-Host "  2. Select '$SPA_APP_NAME'"
    Write-Host "  3. Go to API permissions > Grant admin consent"
}

# ============================================
# Export values to azd environment
# ============================================
Write-Host ""
Write-Host "Exporting values to azd environment..."

# Core identity values
azd env set AZURE_TENANT_ID $TENANT_ID
azd env set AZURE_API_APP_ID $API_APP_ID
azd env set AZURE_SPA_APP_ID $SPA_APP_ID
azd env set AZURE_API_SCOPE "api://$API_APP_ID"

# Bicep parameter values (used in infra/environments/*.parameters.json)
azd env set BACKEND_API_CLIENT_ID $API_APP_ID
azd env set FRONTEND_SPA_CLIENT_ID $SPA_APP_ID

# Frontend build args (Vite environment variables)
azd env set VITE_AZURE_CLIENT_ID $SPA_APP_ID
azd env set VITE_TENANT_ID $TENANT_ID
azd env set VITE_API_SCOPE "api://$API_APP_ID/Decks.ReadWrite api://$API_APP_ID/Cards.ReadWrite"

Write-Host ""
Write-Host "=========================================="
Write-Host "App Registration Setup Complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Backend API App ID:  $API_APP_ID"
Write-Host "Frontend SPA App ID: $SPA_APP_ID"
Write-Host "Tenant ID:           $TENANT_ID"
Write-Host "API Scope URI:       api://$API_APP_ID"
Write-Host ""
Write-Host "These values have been saved to your azd environment."
Write-Host "=========================================="
