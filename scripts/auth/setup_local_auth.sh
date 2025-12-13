#!/bin/bash
# setup_local_auth.sh - Configure local development with Entra ID authentication
# 
# This script creates app registrations in Azure Entra ID and updates
# local .env files to enable authentication in local development.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Permissions to create app registrations in your Entra tenant
#
# Usage:
#   ./scripts/auth/setup_local_auth.sh           # Create app registrations and enable auth
#   ./scripts/auth/setup_local_auth.sh --disable # Disable auth (reset to default)
#   ./scripts/auth/setup_local_auth.sh --status  # Show current auth configuration

set -e

# Anchor to repo root so the script works from anywhere
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
BACKEND_ENV="$REPO_ROOT/backend/.env"
FRONTEND_ENV="$REPO_ROOT/frontend/.env.local"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}=========================================="
    echo "$1"
    echo -e "==========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Show current status
show_status() {
    print_header "Local Auth Configuration Status"
    
    echo ""
    echo "Backend ($BACKEND_ENV):"
    if [ -f "$BACKEND_ENV" ]; then
        AUTH_ENABLED=$(grep "^AUTH_ENABLED=" "$BACKEND_ENV" | cut -d'=' -f2)
        TENANT_ID=$(grep "^AZURE_TENANT_ID=" "$BACKEND_ENV" | cut -d'=' -f2)
        API_APP_ID=$(grep "^AZURE_API_APP_ID=" "$BACKEND_ENV" | cut -d'=' -f2)
        
        if [ "$AUTH_ENABLED" == "true" ]; then
            print_success "Auth enabled"
        else
            print_warning "Auth disabled"
        fi
        
        if [ -n "$TENANT_ID" ]; then
            echo "  Tenant ID: $TENANT_ID"
        fi
        if [ -n "$API_APP_ID" ]; then
            echo "  API App ID: $API_APP_ID"
        fi
    else
        print_error "File not found"
    fi
    
    echo ""
    echo "Frontend ($FRONTEND_ENV):"
    if [ -f "$FRONTEND_ENV" ]; then
        VITE_AUTH=$(grep "^VITE_AUTH_ENABLED=" "$FRONTEND_ENV" | cut -d'=' -f2)
        VITE_CLIENT=$(grep "^VITE_AZURE_CLIENT_ID=" "$FRONTEND_ENV" | cut -d'=' -f2)
        VITE_TENANT=$(grep "^VITE_TENANT_ID=" "$FRONTEND_ENV" | cut -d'=' -f2)
        
        if [ "$VITE_AUTH" == "true" ]; then
            print_success "Auth enabled"
        else
            print_warning "Auth disabled"
        fi
        
        if [ -n "$VITE_TENANT" ]; then
            echo "  Tenant ID: $VITE_TENANT"
        fi
        if [ -n "$VITE_CLIENT" ]; then
            echo "  SPA Client ID: $VITE_CLIENT"
        fi
    else
        print_error "File not found"
    fi
    
    echo ""
}

# Disable auth
disable_auth() {
    print_header "Disabling Local Authentication"
    
    # Update backend .env
    if [ -f "$BACKEND_ENV" ]; then
        sed -i.bak 's/^AUTH_ENABLED=.*/AUTH_ENABLED=false/' "$BACKEND_ENV"
        rm -f "$BACKEND_ENV.bak"
        print_success "Backend auth disabled"
    fi
    
    # Update frontend .env.local
    if [ -f "$FRONTEND_ENV" ]; then
        sed -i.bak 's/^VITE_AUTH_ENABLED=.*/VITE_AUTH_ENABLED=false/' "$FRONTEND_ENV"
        rm -f "$FRONTEND_ENV.bak"
        print_success "Frontend auth disabled"
    fi
    
    echo ""
    echo "Auth has been disabled. Restart your services to apply changes."
}

# Update .env file with a key-value pair
update_env_file() {
    local file="$1"
    local key="$2"
    local value="$3"
    
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        # Key exists, update it
        sed -i.bak "s|^${key}=.*|${key}=${value}|" "$file"
        rm -f "$file.bak"
    else
        # Key doesn't exist, append it
        echo "${key}=${value}" >> "$file"
    fi
}

# Enable auth with app registrations
enable_auth() {
    print_header "Setting Up Local Entra ID Authentication"
    
    # Check Azure CLI is installed
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed."
        echo "Please install it from: https://learn.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    fi
    
    # Check Azure CLI is logged in
    if ! az account show &> /dev/null; then
        print_error "Not logged in to Azure CLI."
        echo "Please run: az login"
        exit 1
    fi
    
    # Get tenant ID
    TENANT_ID=$(az account show --query tenantId -o tsv)
    print_success "Using tenant: $TENANT_ID"
    
    # App display names
    API_APP_NAME="echo-api-local"
    SPA_APP_NAME="echo-spa-local"
    
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
        
        print_success "Created API app: $API_APP_ID"
        
        # Set the Application ID URI
        az ad app update \
            --id "$API_APP_ID" \
            --identifier-uris "api://$API_APP_ID"
        
        # Define and add API scopes
        cat <<EOF > /tmp/echo-api-scopes.json
{
  "oauth2PermissionScopes": [
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
        print_success "Added API scopes: Decks.ReadWrite, Cards.ReadWrite"
    else
        print_success "Backend API app exists: $API_APP_ID"
    fi
    
    # Get scope IDs
    DECKS_SCOPE_ID=$(az ad app show --id "$API_APP_ID" --query "api.oauth2PermissionScopes[?value=='Decks.ReadWrite'].id" -o tsv)
    CARDS_SCOPE_ID=$(az ad app show --id "$API_APP_ID" --query "api.oauth2PermissionScopes[?value=='Cards.ReadWrite'].id" -o tsv)
    
    # ============================================
    # Frontend SPA App Registration
    # ============================================
    echo ""
    echo "Checking for Frontend SPA app registration ($SPA_APP_NAME)..."
    
    SPA_APP_ID=$(az ad app list --filter "displayName eq '$SPA_APP_NAME'" --query "[0].appId" -o tsv 2>/dev/null)
    
    if [ -z "$SPA_APP_ID" ] || [ "$SPA_APP_ID" == "null" ]; then
        echo "Creating Frontend SPA app registration..."
        
        # Create the SPA app
        SPA_APP_ID=$(az ad app create \
            --display-name "$SPA_APP_NAME" \
            --sign-in-audience "AzureADMyOrg" \
            --enable-id-token-issuance true \
            --query "appId" -o tsv)
        
        print_success "Created SPA app: $SPA_APP_ID"
        
        # Configure SPA redirect URIs
        cat <<EOF > /tmp/echo-spa-config.json
{
  "redirectUris": ["http://localhost:5173", "http://localhost:3000"]
}
EOF
        
        az ad app update \
            --id "$SPA_APP_ID" \
            --set spa=@/tmp/echo-spa-config.json
        
        rm /tmp/echo-spa-config.json
        print_success "Configured SPA redirect URIs"
        
        # Add API permissions
        az ad app permission add \
            --id "$SPA_APP_ID" \
            --api "$API_APP_ID" \
            --api-permissions "$DECKS_SCOPE_ID=Scope" "$CARDS_SCOPE_ID=Scope"
        
        print_success "Added API permissions"
    else
        print_success "Frontend SPA app exists: $SPA_APP_ID"
    fi
    
    # ============================================
    # Grant Admin Consent
    # ============================================
    echo ""
    echo "Attempting to grant admin consent..."
    
    if az ad app permission admin-consent --id "$SPA_APP_ID" 2>/dev/null; then
        print_success "Admin consent granted"
    else
        print_warning "Could not grant admin consent automatically."
        echo "  An admin needs to grant consent in the Azure Portal:"
        echo "  1. Go to Azure Portal > Entra ID > App registrations"
        echo "  2. Select '$SPA_APP_NAME'"
        echo "  3. Go to API permissions > Grant admin consent"
    fi
    
    # ============================================
    # Update .env files
    # ============================================
    print_header "Updating Environment Files"
    
    API_SCOPE="api://$API_APP_ID/Decks.ReadWrite api://$API_APP_ID/Cards.ReadWrite"
    
    # Ensure .env files exist
    if [ ! -f "$BACKEND_ENV" ]; then
        cp "$REPO_ROOT/backend/.env.example" "$BACKEND_ENV"
    fi
    if [ ! -f "$FRONTEND_ENV" ]; then
        cp "$REPO_ROOT/frontend/.env.example" "$FRONTEND_ENV"
    fi
    
    # Update backend .env
    update_env_file "$BACKEND_ENV" "AUTH_ENABLED" "true"
    update_env_file "$BACKEND_ENV" "AZURE_TENANT_ID" "$TENANT_ID"
    update_env_file "$BACKEND_ENV" "AZURE_API_SCOPE" "api://$API_APP_ID"
    update_env_file "$BACKEND_ENV" "AZURE_API_APP_ID" "$API_APP_ID"
    print_success "Updated backend/.env"
    
    # Update frontend .env.local
    update_env_file "$FRONTEND_ENV" "VITE_AUTH_ENABLED" "true"
    update_env_file "$FRONTEND_ENV" "VITE_AZURE_CLIENT_ID" "$SPA_APP_ID"
    update_env_file "$FRONTEND_ENV" "VITE_TENANT_ID" "$TENANT_ID"
    update_env_file "$FRONTEND_ENV" "VITE_API_SCOPE" "$API_SCOPE"
    print_success "Updated frontend/.env.local"
    
    # ============================================
    # Summary
    # ============================================
    print_header "Setup Complete!"
    
    echo ""
    echo "App Registrations:"
    echo "  Backend API: $API_APP_ID (echo-api-local)"
    echo "  Frontend SPA: $SPA_APP_ID (echo-spa-local)"
    echo ""
    echo "Tenant ID: $TENANT_ID"
    echo ""
    echo "Authentication has been ENABLED in your local environment."
    echo ""
    echo "Next steps:"
    echo "  1. Start the Cosmos DB emulator (if not running):"
    echo "     docker compose up cosmosdb"
    echo ""
    echo "  2. Start the application:"
    echo "     docker compose up"
    echo "     # OR"
    echo "     ./scripts/dev/manual_setup.sh"
    echo ""
    echo "  3. Open http://localhost:3000 and sign in with your Entra account"
    echo ""
    echo "To disable auth later, run: ./scripts/auth/setup_local_auth.sh --disable"
}

# Main script
case "${1:-}" in
    --disable)
        disable_auth
        ;;
    --status)
        show_status
        ;;
    --help|-h)
        echo "Usage: $0 [option]"
        echo ""
        echo "Options:"
        echo "  (none)      Create app registrations and enable auth"
        echo "  --disable   Disable auth (reset to default)"
        echo "  --status    Show current auth configuration"
        echo "  --help      Show this help message"
        ;;
    *)
        enable_auth
        ;;
esac
