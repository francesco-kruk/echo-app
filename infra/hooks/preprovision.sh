#!/bin/bash
# preprovision.sh - Creates Entra ID app registrations for echo-app
# This script is idempotent - it will skip creation if apps already exist
#
# In CI/CD mode (when BACKEND_API_CLIENT_ID is set), this script will:
# - Skip app registration creation (assumes apps already exist)
# - Only export environment variables to azd env

set -e

echo "=========================================="
echo "Echo App - Entra ID App Registration Setup"
echo "=========================================="

# Detect CI/CD mode - if app IDs are already set, skip creation
CI_MODE=false
if [ -n "$BACKEND_API_CLIENT_ID" ] && [ -n "$FRONTEND_SPA_CLIENT_ID" ]; then
    CI_MODE=true
    echo ""
    echo "CI/CD mode detected - using pre-configured app registrations"
    echo "  Backend API Client ID: $BACKEND_API_CLIENT_ID"
    echo "  Frontend SPA Client ID: $FRONTEND_SPA_CLIENT_ID"
fi

# Get tenant ID from environment or Azure CLI
if [ -n "$AZURE_TENANT_ID" ]; then
    TENANT_ID="$AZURE_TENANT_ID"
else
    TENANT_ID=$(az account show --query tenantId -o tsv 2>/dev/null || echo "")
fi

if [ -z "$TENANT_ID" ]; then
    echo "ERROR: Not logged in to Azure CLI and AZURE_TENANT_ID not set."
    echo "Run 'az login' first or set AZURE_TENANT_ID environment variable."
    exit 1
fi
echo "Using Tenant ID: $TENANT_ID"

# In CI mode, skip app registration creation and just export variables
if [ "$CI_MODE" = true ]; then
    echo ""
    echo "Skipping app registration creation (CI/CD mode)"
    echo ""
    echo "Exporting values to azd environment..."
    
    API_APP_ID="$BACKEND_API_CLIENT_ID"
    SPA_APP_ID="$FRONTEND_SPA_CLIENT_ID"
    
    # Core identity values
    azd env set AZURE_TENANT_ID "$TENANT_ID"
    azd env set AZURE_API_APP_ID "$API_APP_ID"
    azd env set AZURE_SPA_APP_ID "$SPA_APP_ID"
    azd env set AZURE_API_SCOPE "api://$API_APP_ID"
    
    # Bicep parameter values
    azd env set BACKEND_API_CLIENT_ID "$API_APP_ID"
    azd env set FRONTEND_SPA_CLIENT_ID "$SPA_APP_ID"
    
    # Frontend build args (Vite environment variables)
    azd env set VITE_AZURE_CLIENT_ID "$SPA_APP_ID"
    azd env set VITE_TENANT_ID "$TENANT_ID"
    azd env set VITE_API_SCOPE "api://$API_APP_ID/Decks.ReadWrite api://$API_APP_ID/Cards.ReadWrite"
    
    echo ""
    echo "=========================================="
    echo "CI/CD App Registration Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Backend API App ID:  $API_APP_ID"
    echo "Frontend SPA App ID: $SPA_APP_ID"
    echo "Tenant ID:           $TENANT_ID"
    echo "=========================================="
    
    exit 0
fi

# App display names
API_APP_NAME="echo-api"
SPA_APP_NAME="echo-spa"

# ============================================
# Backend API App Registration
# ============================================
echo ""
echo "Checking for Backend API app registration ($API_APP_NAME)..."

API_APP_ID=$(az ad app list --filter "displayName eq '$API_APP_NAME'" --query "[0].appId" -o tsv 2>/dev/null)

if [ -z "$API_APP_ID" ] || [ "$API_APP_ID" == "null" ]; then
    echo "Creating Backend API app registration..."
    
    # Create the app
    API_APP_ID=$(az ad app create \
        --display-name "$API_APP_NAME" \
        --sign-in-audience "AzureADMyOrg" \
        --query "appId" -o tsv)
    
    echo "Created app with ID: $API_APP_ID"
    
    # Set the Application ID URI
    az ad app update \
        --id "$API_APP_ID" \
        --identifier-uris "api://$API_APP_ID"
    
    echo "Set Application ID URI: api://$API_APP_ID"
    
    # Define and add API scopes
    cat <<EOF > /tmp/echo-api-scopes.json
{
  "oauth2PermissionScopes": [
    {
      "id": "$(uuidgen | tr '[:upper:]' '[:lower:]')",
      "adminConsentDescription": "Allows the app to read decks on behalf of the signed-in user",
      "adminConsentDisplayName": "Read Decks",
      "isEnabled": true,
      "type": "User",
      "userConsentDescription": "Allows the app to read your decks",
      "userConsentDisplayName": "Read your decks",
      "value": "Decks.Read"
    },
    {
      "id": "$(uuidgen | tr '[:upper:]' '[:lower:]')",
      "adminConsentDescription": "Allows the app to read and write decks on behalf of the signed-in user",
      "adminConsentDisplayName": "Read and Write Decks",
      "isEnabled": true,
      "type": "User",
      "userConsentDescription": "Allows the app to read and modify your decks",
      "userConsentDisplayName": "Read and modify your decks",
      "value": "Decks.ReadWrite"
    },
    {
      "id": "$(uuidgen | tr '[:upper:]' '[:lower:]')",
      "adminConsentDescription": "Allows the app to read cards on behalf of the signed-in user",
      "adminConsentDisplayName": "Read Cards",
      "isEnabled": true,
      "type": "User",
      "userConsentDescription": "Allows the app to read your cards",
      "userConsentDisplayName": "Read your cards",
      "value": "Cards.Read"
    },
    {
      "id": "$(uuidgen | tr '[:upper:]' '[:lower:]')",
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
EOF
    
    az ad app update \
        --id "$API_APP_ID" \
        --set api=@/tmp/echo-api-scopes.json
    
    rm /tmp/echo-api-scopes.json
    echo "Added API scopes: Decks.Read, Decks.ReadWrite, Cards.Read, Cards.ReadWrite"
else
    echo "Backend API app already exists with ID: $API_APP_ID"
fi

# Get the scope IDs for later use
DECKS_READWRITE_SCOPE_ID=$(az ad app show --id "$API_APP_ID" --query "api.oauth2PermissionScopes[?value=='Decks.ReadWrite'].id" -o tsv)
CARDS_READWRITE_SCOPE_ID=$(az ad app show --id "$API_APP_ID" --query "api.oauth2PermissionScopes[?value=='Cards.ReadWrite'].id" -o tsv)

# ============================================
# Frontend SPA App Registration
# ============================================
echo ""
echo "Checking for Frontend SPA app registration ($SPA_APP_NAME)..."

SPA_APP_ID=$(az ad app list --filter "displayName eq '$SPA_APP_NAME'" --query "[0].appId" -o tsv 2>/dev/null)

if [ -z "$SPA_APP_ID" ] || [ "$SPA_APP_ID" == "null" ]; then
    echo "Creating Frontend SPA app registration..."
    
    # Create the SPA app with redirect URIs
    SPA_APP_ID=$(az ad app create \
        --display-name "$SPA_APP_NAME" \
        --sign-in-audience "AzureADMyOrg" \
        --enable-id-token-issuance true \
        --query "appId" -o tsv)
    
    echo "Created SPA app with ID: $SPA_APP_ID"
    
    # Configure SPA redirect URIs using the correct JSON format
    cat <<EOF > /tmp/echo-spa-config.json
{
  "redirectUris": ["http://localhost:5173", "http://localhost:3000"]
}
EOF
    
    az ad app update \
        --id "$SPA_APP_ID" \
        --set spa=@/tmp/echo-spa-config.json
    
    rm /tmp/echo-spa-config.json
    echo "Configured SPA redirect URIs for local development"
    
    # Add API permissions for the SPA to call the backend
    # Request Decks.ReadWrite and Cards.ReadWrite scopes
    az ad app permission add \
        --id "$SPA_APP_ID" \
        --api "$API_APP_ID" \
        --api-permissions "$DECKS_READWRITE_SCOPE_ID=Scope" "$CARDS_READWRITE_SCOPE_ID=Scope"
    
    echo "Added API permissions for SPA to call Backend API"
else
    echo "Frontend SPA app already exists with ID: $SPA_APP_ID"
fi

# ============================================
# Grant Admin Consent (if possible)
# ============================================
echo ""
echo "Attempting to grant admin consent..."

# Try to grant admin consent - this may fail if user doesn't have admin rights
if az ad app permission admin-consent --id "$SPA_APP_ID" 2>/dev/null; then
    echo "Admin consent granted successfully"
else
    echo "WARNING: Could not grant admin consent automatically."
    echo "An admin needs to grant consent in the Azure Portal:"
    echo "  1. Go to Azure Portal > Entra ID > App registrations"
    echo "  2. Select '$SPA_APP_NAME'"
    echo "  3. Go to API permissions > Grant admin consent"
fi

# ============================================
# Export values to azd environment
# ============================================
echo ""
echo "Exporting values to azd environment..."

# Core identity values
azd env set AZURE_TENANT_ID "$TENANT_ID"
azd env set AZURE_API_APP_ID "$API_APP_ID"
azd env set AZURE_SPA_APP_ID "$SPA_APP_ID"
azd env set AZURE_API_SCOPE "api://$API_APP_ID"

# Bicep parameter values (used in infra/environments/*.parameters.json)
azd env set BACKEND_API_CLIENT_ID "$API_APP_ID"
azd env set FRONTEND_SPA_CLIENT_ID "$SPA_APP_ID"

# Frontend build args (Vite environment variables)
azd env set VITE_AZURE_CLIENT_ID "$SPA_APP_ID"
azd env set VITE_TENANT_ID "$TENANT_ID"
azd env set VITE_API_SCOPE "api://$API_APP_ID/Decks.ReadWrite api://$API_APP_ID/Cards.ReadWrite"

echo ""
echo "=========================================="
echo "App Registration Setup Complete!"
echo "=========================================="
echo ""
echo "Backend API App ID:  $API_APP_ID"
echo "Frontend SPA App ID: $SPA_APP_ID"
echo "Tenant ID:           $TENANT_ID"
echo "API Scope URI:       api://$API_APP_ID"
echo ""
echo "These values have been saved to your azd environment."
echo "=========================================="
