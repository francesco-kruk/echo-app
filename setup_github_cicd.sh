#!/bin/bash
# setup_github_cicd.sh - Configure GitHub repository for CI/CD with Azure
#
# This script automates the setup of:
# 1. Azure service principal with federated credentials for GitHub Actions
# 2. Entra ID app registrations (if not already created)
# 3. GitHub repository variables and secrets
#
# Prerequisites:
# - Azure CLI installed and logged in with permissions to create app registrations
# - GitHub CLI installed and authenticated (gh auth login)
# - Repository owner permissions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Echo App - GitHub CI/CD Setup"
echo "=========================================="
echo ""

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."
    
    if ! command -v az &> /dev/null; then
        echo -e "${RED}ERROR: Azure CLI (az) is not installed${NC}"
        exit 1
    fi
    
    if ! command -v gh &> /dev/null; then
        echo -e "${RED}ERROR: GitHub CLI (gh) is not installed${NC}"
        echo "Install it from: https://cli.github.com/"
        exit 1
    fi
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        echo -e "${RED}ERROR: Not logged in to Azure CLI${NC}"
        echo "Run: az login"
        exit 1
    fi
    
    # Check GitHub login
    if ! gh auth status &> /dev/null; then
        echo -e "${RED}ERROR: Not logged in to GitHub CLI${NC}"
        echo "Run: gh auth login"
        exit 1
    fi
    
    echo -e "${GREEN}✓ All prerequisites met${NC}"
}

# Get repository info
get_repo_info() {
    echo ""
    echo "Getting repository information..."
    
    # Try to get from git remote
    if git remote get-url origin &> /dev/null; then
        REPO_URL=$(git remote get-url origin)
        # Extract owner/repo from URL (handles both HTTPS and SSH)
        GITHUB_REPO=$(echo "$REPO_URL" | sed -E 's/.*[:/]([^/]+\/[^/]+)(\.git)?$/\1/' | sed 's/\.git$//')
    fi
    
    if [ -z "$GITHUB_REPO" ]; then
        read -p "Enter GitHub repository (owner/repo): " GITHUB_REPO
    fi
    
    GITHUB_ORG=$(echo "$GITHUB_REPO" | cut -d'/' -f1)
    GITHUB_REPO_NAME=$(echo "$GITHUB_REPO" | cut -d'/' -f2)
    
    echo "Repository: $GITHUB_REPO"
}

# Get Azure subscription info
get_azure_info() {
    echo ""
    echo "Getting Azure subscription information..."
    
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
    SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
    TENANT_ID=$(az account show --query tenantId -o tsv)
    
    echo "Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"
    echo "Tenant ID: $TENANT_ID"
    
    read -p "Use this subscription? [Y/n]: " confirm
    if [[ "$confirm" =~ ^[Nn]$ ]]; then
        echo "Available subscriptions:"
        az account list --query "[].{Name:name, ID:id}" -o table
        read -p "Enter subscription ID: " SUBSCRIPTION_ID
        az account set --subscription "$SUBSCRIPTION_ID"
        TENANT_ID=$(az account show --query tenantId -o tsv)
    fi
}

# Create or get service principal for GitHub Actions
setup_service_principal() {
    echo ""
    echo "Setting up service principal for GitHub Actions..."
    
    SP_NAME="github-actions-${GITHUB_REPO_NAME}"
    
    # Check if SP already exists
    EXISTING_SP=$(az ad app list --filter "displayName eq '$SP_NAME'" --query "[0].appId" -o tsv 2>/dev/null || echo "")
    
    if [ -n "$EXISTING_SP" ] && [ "$EXISTING_SP" != "null" ]; then
        echo "Service principal already exists: $SP_NAME"
        SP_CLIENT_ID="$EXISTING_SP"
    else
        echo "Creating service principal: $SP_NAME"
        
        # Create the app registration
        SP_CLIENT_ID=$(az ad app create \
            --display-name "$SP_NAME" \
            --sign-in-audience "AzureADMyOrg" \
            --query "appId" -o tsv)
        
        # Create service principal for the app
        az ad sp create --id "$SP_CLIENT_ID" > /dev/null
        
        echo -e "${GREEN}✓ Created service principal with Client ID: $SP_CLIENT_ID${NC}"
    fi
    
    # Get the app's object ID (needed for federated credentials)
    APP_OBJECT_ID=$(az ad app show --id "$SP_CLIENT_ID" --query "id" -o tsv)
    
    # Assign Contributor role to the subscription
    echo "Assigning Contributor role to subscription..."
    az role assignment create \
        --assignee "$SP_CLIENT_ID" \
        --role "Contributor" \
        --scope "/subscriptions/$SUBSCRIPTION_ID" \
        --only-show-errors 2>/dev/null || echo "Role already assigned or insufficient permissions"
    
    # Assign User Access Administrator for managed identity role assignments
    echo "Assigning User Access Administrator role..."
    az role assignment create \
        --assignee "$SP_CLIENT_ID" \
        --role "User Access Administrator" \
        --scope "/subscriptions/$SUBSCRIPTION_ID" \
        --only-show-errors 2>/dev/null || echo "Role already assigned or insufficient permissions"
    
    # Setup federated credentials for GitHub Actions
    echo "Setting up federated credentials for GitHub Actions..."
    
    # Federated credential for main branch
    setup_federated_credential "main-branch" "ref:refs/heads/main" "$APP_OBJECT_ID"
    
    # Federated credential for pull requests
    setup_federated_credential "pull-requests" "pull_request" "$APP_OBJECT_ID"
    
    # Federated credentials for environments
    for env in dev staging prod; do
        setup_federated_credential "env-$env" "environment:$env" "$APP_OBJECT_ID"
    done
    
    echo -e "${GREEN}✓ Service principal setup complete${NC}"
}

setup_federated_credential() {
    local name=$1
    local subject=$2
    local app_object_id=$3
    
    # Check if credential already exists
    EXISTING=$(az ad app federated-credential list --id "$app_object_id" --query "[?name=='$name'].name" -o tsv 2>/dev/null || echo "")
    
    if [ -n "$EXISTING" ]; then
        echo "  Federated credential '$name' already exists"
        return
    fi
    
    echo "  Creating federated credential: $name"
    
    az ad app federated-credential create \
        --id "$app_object_id" \
        --parameters "{
            \"name\": \"$name\",
            \"issuer\": \"https://token.actions.githubusercontent.com\",
            \"subject\": \"repo:${GITHUB_REPO}:$subject\",
            \"audiences\": [\"api://AzureADTokenExchange\"]
        }" > /dev/null 2>&1 || echo "    Warning: Could not create credential (may already exist)"
}

# Create or get Entra ID app registrations
setup_app_registrations() {
    echo ""
    echo "Setting up Entra ID app registrations..."
    
    API_APP_NAME="echo-api"
    SPA_APP_NAME="echo-spa"
    
    # Check for existing Backend API app
    BACKEND_API_CLIENT_ID=$(az ad app list --filter "displayName eq '$API_APP_NAME'" --query "[0].appId" -o tsv 2>/dev/null || echo "")
    
    if [ -z "$BACKEND_API_CLIENT_ID" ] || [ "$BACKEND_API_CLIENT_ID" == "null" ]; then
        echo -e "${YELLOW}Backend API app registration not found.${NC}"
        echo "Run 'azd up' locally first to create app registrations, or run './infra/hooks/preprovision.sh'"
        read -p "Would you like to run the preprovision script now? [Y/n]: " confirm
        if [[ ! "$confirm" =~ ^[Nn]$ ]]; then
            ./infra/hooks/preprovision.sh
            BACKEND_API_CLIENT_ID=$(az ad app list --filter "displayName eq '$API_APP_NAME'" --query "[0].appId" -o tsv)
        else
            echo "Please provide the Backend API Client ID:"
            read -p "Backend API Client ID: " BACKEND_API_CLIENT_ID
        fi
    else
        echo "Backend API app exists: $BACKEND_API_CLIENT_ID"
    fi
    
    # Check for existing Frontend SPA app
    FRONTEND_SPA_CLIENT_ID=$(az ad app list --filter "displayName eq '$SPA_APP_NAME'" --query "[0].appId" -o tsv 2>/dev/null || echo "")
    
    if [ -z "$FRONTEND_SPA_CLIENT_ID" ] || [ "$FRONTEND_SPA_CLIENT_ID" == "null" ]; then
        if [ -z "$BACKEND_API_CLIENT_ID" ]; then
            echo "Please provide the Frontend SPA Client ID:"
            read -p "Frontend SPA Client ID: " FRONTEND_SPA_CLIENT_ID
        fi
    else
        echo "Frontend SPA app exists: $FRONTEND_SPA_CLIENT_ID"
    fi
    
    # Grant SP permission to manage app registrations (for redirect URI updates)
    echo "Granting Application.ReadWrite.All permission to service principal..."
    
    # Microsoft Graph API ID
    MS_GRAPH_ID="00000003-0000-0000-c000-000000000000"
    # Application.ReadWrite.All scope ID
    APP_RW_SCOPE="1bfefb4e-e0b5-418b-a88f-73c46d2cc8e9"
    
    az ad app permission add \
        --id "$SP_CLIENT_ID" \
        --api "$MS_GRAPH_ID" \
        --api-permissions "${APP_RW_SCOPE}=Role" \
        --only-show-errors 2>/dev/null || true
    
    echo ""
    echo -e "${YELLOW}NOTE: An admin must grant consent for the service principal to update app registrations.${NC}"
    echo "Go to Azure Portal > Entra ID > App registrations > $SP_NAME > API permissions > Grant admin consent"
    
    echo -e "${GREEN}✓ App registrations verified${NC}"
}

# Configure GitHub repository
configure_github_repo() {
    echo ""
    echo "Configuring GitHub repository..."
    
    # Set repository variables (non-sensitive)
    echo "Setting repository variables..."
    gh variable set AZURE_CLIENT_ID --body "$SP_CLIENT_ID" --repo "$GITHUB_REPO"
    gh variable set AZURE_TENANT_ID --body "$TENANT_ID" --repo "$GITHUB_REPO"
    gh variable set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID" --repo "$GITHUB_REPO"
    
    # Set repository secrets (sensitive)
    echo "Setting repository secrets..."
    gh secret set BACKEND_API_CLIENT_ID --body "$BACKEND_API_CLIENT_ID" --repo "$GITHUB_REPO"
    gh secret set FRONTEND_SPA_CLIENT_ID --body "$FRONTEND_SPA_CLIENT_ID" --repo "$GITHUB_REPO"
    
    echo -e "${GREEN}✓ GitHub repository configured${NC}"
}

# Create GitHub environments
setup_github_environments() {
    echo ""
    echo "Setting up GitHub environments..."
    
    for env in dev staging prod; do
        echo "  Creating environment: $env"
        # Note: gh cli doesn't support creating environments directly
        # They will be created automatically when the workflow runs
        # For production, you should manually configure protection rules in GitHub UI
    done
    
    echo ""
    echo -e "${YELLOW}IMPORTANT: Configure environment protection rules in GitHub:${NC}"
    echo "  1. Go to: https://github.com/$GITHUB_REPO/settings/environments"
    echo "  2. Create environments: dev, staging, prod"
    echo "  3. For 'staging' and 'prod', add required reviewers"
    echo "  4. Optionally add deployment branches restriction"
}

# Main execution
main() {
    check_prerequisites
    get_repo_info
    get_azure_info
    setup_service_principal
    setup_app_registrations
    configure_github_repo
    setup_github_environments
    
    echo ""
    echo "=========================================="
    echo -e "${GREEN}Setup Complete!${NC}"
    echo "=========================================="
    echo ""
    echo "Summary:"
    echo "  GitHub Repository:        $GITHUB_REPO"
    echo "  Azure Subscription:       $SUBSCRIPTION_ID"
    echo "  Azure Tenant:             $TENANT_ID"
    echo "  Service Principal:        $SP_CLIENT_ID"
    echo "  Backend API App ID:       $BACKEND_API_CLIENT_ID"
    echo "  Frontend SPA App ID:      $FRONTEND_SPA_CLIENT_ID"
    echo ""
    echo "Next steps:"
    echo "  1. Grant admin consent for the service principal in Azure Portal"
    echo "  2. Configure environment protection rules in GitHub"
    echo "  3. Push to main branch to trigger deployment to dev"
    echo "  4. Use manual workflow dispatch for staging/prod deployments"
    echo ""
    echo "Test the setup:"
    echo "  gh workflow run deploy-dev.yml"
    echo ""
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h    Show this help message"
        echo "  --status      Show current configuration status"
        echo ""
        exit 0
        ;;
    --status)
        echo "Checking current configuration..."
        echo ""
        
        # Check Azure
        if az account show &> /dev/null; then
            echo "Azure CLI: Logged in"
            echo "  Subscription: $(az account show --query name -o tsv)"
        else
            echo "Azure CLI: Not logged in"
        fi
        
        # Check GitHub
        if gh auth status &> /dev/null; then
            echo "GitHub CLI: Authenticated"
        else
            echo "GitHub CLI: Not authenticated"
        fi
        
        # Check for app registrations
        API_ID=$(az ad app list --filter "displayName eq 'echo-api'" --query "[0].appId" -o tsv 2>/dev/null || echo "")
        SPA_ID=$(az ad app list --filter "displayName eq 'echo-spa'" --query "[0].appId" -o tsv 2>/dev/null || echo "")
        
        echo ""
        echo "App Registrations:"
        [ -n "$API_ID" ] && echo "  Backend API: $API_ID" || echo "  Backend API: Not found"
        [ -n "$SPA_ID" ] && echo "  Frontend SPA: $SPA_ID" || echo "  Frontend SPA: Not found"
        
        exit 0
        ;;
    *)
        main
        ;;
esac
