#!/bin/bash
# postprovision.sh - Updates SPA redirect URIs with production URL after deployment
# This script runs after infrastructure provisioning completes

set -e

echo "=========================================="
echo "Echo App - Post-Provisioning Setup"
echo "=========================================="

# Get values from azd environment
SPA_APP_ID=$(azd env get-value AZURE_SPA_APP_ID 2>/dev/null || echo "")
API_APP_ID=$(azd env get-value AZURE_API_APP_ID 2>/dev/null || echo "")
FRONTEND_URI=$(azd env get-value FRONTEND_URI 2>/dev/null || echo "")

# ============================================
# Ensure Service Principal exists for API app
# ============================================
# This is required for the SPA to request tokens for the API
if [ -n "$API_APP_ID" ]; then
    echo ""
    echo "Ensuring service principal exists for API app..."
    
    # Check if service principal already exists
    SP_EXISTS=$(az ad sp show --id "$API_APP_ID" --query "id" -o tsv 2>/dev/null || echo "")
    
    if [ -n "$SP_EXISTS" ]; then
        echo "✓ Service principal already exists for API app ($API_APP_ID)"
    else
        echo "Creating service principal for API app ($API_APP_ID)..."
        az ad sp create --id "$API_APP_ID" --output none
        echo "✓ Service principal created successfully"
    fi
else
    echo "WARNING: AZURE_API_APP_ID not found. Skipping service principal creation."
fi

if [ -z "$SPA_APP_ID" ]; then
    echo "WARNING: AZURE_SPA_APP_ID not found in environment. Skipping redirect URI update."
else
    echo "SPA App ID: $SPA_APP_ID"
    
    if [ -n "$FRONTEND_URI" ] && [ "$FRONTEND_URI" != "null" ]; then
        echo "Frontend URL: $FRONTEND_URI"
        echo ""
        echo "Updating SPA redirect URIs..."
        
        # Get current redirect URIs
        CURRENT_URIS=$(az ad app show --id "$SPA_APP_ID" --query "spa.redirectUris" -o json 2>/dev/null || echo "[]")
        
        # Check if the frontend URI is already in the list
        if echo "$CURRENT_URIS" | grep -q "$FRONTEND_URI"; then
            echo "Frontend URI already configured in SPA app registration."
        else
            echo "Adding $FRONTEND_URI to SPA redirect URIs..."
            
            # Build the new list of URIs using jq if available, otherwise use sed
            if command -v jq &> /dev/null; then
                NEW_URIS=$(echo "$CURRENT_URIS" | jq --arg uri "$FRONTEND_URI" '. + [$uri]')
            else
                # Fallback: manually build JSON array
                if [ "$CURRENT_URIS" = "[]" ]; then
                    NEW_URIS="[\"$FRONTEND_URI\"]"
                else
                    # Remove trailing ] and add new URI
                    NEW_URIS=$(echo "$CURRENT_URIS" | sed 's/]$/,\"'"$FRONTEND_URI"'\"]/')
                fi
            fi
            
            # Create a temp file with the full SPA object
            cat > /tmp/echo-spa-update.json <<EOFINNER
{"spa": {"redirectUris": $NEW_URIS}}
EOFINNER
            
            # Get the object ID of the app (needed for REST API)
            APP_OBJECT_ID=$(az ad app show --id "$SPA_APP_ID" --query "id" -o tsv)
            
            # Use az rest to update the app via Graph API
            az rest --method PATCH \
                --uri "https://graph.microsoft.com/v1.0/applications/$APP_OBJECT_ID" \
                --headers "Content-Type=application/json" \
                --body @/tmp/echo-spa-update.json
            
            rm /tmp/echo-spa-update.json
            echo "✓ Successfully added $FRONTEND_URI to SPA redirect URIs"
        fi
    else
        echo "WARNING: FRONTEND_URI not available. Redirect URI update skipped."
        echo "You may need to manually add the production URL to the SPA app registration."
    fi
fi

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Environment:              ${AZURE_ENV_NAME}"
echo "Frontend URL:             ${FRONTEND_URI:-'Not available'}"
echo "Backend URL (internal):   ${BACKEND_URI:-'Not available'}"
echo ""
echo "Entra ID Configuration:"
echo "  Tenant ID:              ${AZURE_TENANT_ID:-'Not set'}"
echo "  Backend API App ID:     ${AZURE_API_APP_ID:-'Not set'}"
echo "  Frontend SPA App ID:    ${AZURE_SPA_APP_ID:-'Not set'}"
echo "=========================================="

# ============================================
# Automatic CI/CD Pipeline Setup
# ============================================
# Automatically configure GitHub Actions if gh CLI is available

setup_github_cicd() {
    echo ""
    echo "=========================================="
    echo "Configuring GitHub Actions CI/CD"
    echo "=========================================="
    
    # Get repository info
    REPO_URL=$(git remote get-url origin 2>/dev/null || echo "")
    if [ -z "$REPO_URL" ]; then
        echo "WARNING: Not a git repository. Skipping CI/CD setup."
        return 0
    fi
    
    GITHUB_REPO=$(echo "$REPO_URL" | sed -E 's/.*[:/]([^/]+\/[^/]+)(\.git)?$/\1/' | sed 's/\.git$//')
    echo "Repository: $GITHUB_REPO"
    
    # Get values from azd environment
    TENANT_ID=$(azd env get-value AZURE_TENANT_ID 2>/dev/null || echo "")
    SUBSCRIPTION_ID=$(azd env get-value AZURE_SUBSCRIPTION_ID 2>/dev/null || az account show --query id -o tsv 2>/dev/null || echo "")
    API_APP_ID=$(azd env get-value AZURE_API_APP_ID 2>/dev/null || azd env get-value BACKEND_API_CLIENT_ID 2>/dev/null || echo "")
    SPA_APP_ID=$(azd env get-value AZURE_SPA_APP_ID 2>/dev/null || azd env get-value FRONTEND_SPA_CLIENT_ID 2>/dev/null || echo "")
    
    # Check if azd pipeline is already configured
    AZD_PRINCIPAL=$(azd env get-value AZURE_CLIENT_ID 2>/dev/null || echo "")
    
    if [ -z "$AZD_PRINCIPAL" ]; then
        echo "Running azd pipeline config to set up service principal..."
        # Run azd pipeline config with defaults (creates SP with federated credentials)
        azd pipeline config --provider github --principal-name "github-actions-echo-app" 2>/dev/null || {
            echo "WARNING: azd pipeline config failed. You may need to run it manually."
            echo "  azd pipeline config"
            return 0
        }
        # Refresh the principal ID
        AZD_PRINCIPAL=$(azd env get-value AZURE_CLIENT_ID 2>/dev/null || echo "")
    else
        echo "✓ Azure service principal already configured: $AZD_PRINCIPAL"
    fi
    
    # Set GitHub repository variables using gh CLI
    if [ -n "$AZD_PRINCIPAL" ]; then
        echo "Setting GitHub repository variables..."
        gh variable set AZURE_CLIENT_ID --body "$AZD_PRINCIPAL" --repo "$GITHUB_REPO" 2>/dev/null || true
        gh variable set AZURE_TENANT_ID --body "$TENANT_ID" --repo "$GITHUB_REPO" 2>/dev/null || true
        gh variable set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID" --repo "$GITHUB_REPO" 2>/dev/null || true
        echo "✓ GitHub variables configured"
    fi
    
    # Set GitHub secrets for app registrations
    if [ -n "$API_APP_ID" ] && [ -n "$SPA_APP_ID" ]; then
        echo "Setting GitHub repository secrets..."
        gh secret set BACKEND_API_CLIENT_ID --body "$API_APP_ID" --repo "$GITHUB_REPO" 2>/dev/null || true
        gh secret set FRONTEND_SPA_CLIENT_ID --body "$SPA_APP_ID" --repo "$GITHUB_REPO" 2>/dev/null || true
        echo "✓ GitHub secrets configured"
    else
        echo "WARNING: App registration IDs not found. Secrets not configured."
        echo "  Run manually after azd up:"
        echo "  gh secret set BACKEND_API_CLIENT_ID --body \"<api-app-id>\""
        echo "  gh secret set FRONTEND_SPA_CLIENT_ID --body \"<spa-app-id>\""
    fi
    
    echo ""
    echo "✓ GitHub Actions CI/CD configured successfully!"
    echo "  Push to main branch to trigger deployment."
}

# Only run CI/CD setup if gh CLI is available and authenticated
if command -v gh &> /dev/null; then
    if gh auth status &> /dev/null 2>&1; then
        setup_github_cicd
    else
        echo ""
        echo "NOTE: GitHub CLI not authenticated. Skipping automatic CI/CD setup."
        echo "  To configure CI/CD later, run: gh auth login && azd pipeline config"
    fi
else
    echo ""
    echo "NOTE: GitHub CLI not installed. Skipping automatic CI/CD setup."
    echo "  Install from: https://cli.github.com/"
    echo "  Then run: azd pipeline config"
fi
