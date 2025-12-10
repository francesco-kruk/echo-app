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
# CI/CD Pipeline Setup Prompt
# ============================================
# Only prompt for CI/CD setup in interactive mode (not in CI)
if [ -z "$CI" ] && [ -z "$GITHUB_ACTIONS" ] && [ -t 0 ]; then
    echo ""
    echo "=========================================="
    echo "CI/CD Pipeline Setup"
    echo "=========================================="
    
    # Check if gh CLI is available
    if command -v gh &> /dev/null && gh auth status &> /dev/null 2>&1; then
        # Check if repo has GitHub Actions configured
        REPO_URL=$(git remote get-url origin 2>/dev/null || echo "")
        
        if [ -n "$REPO_URL" ]; then
            GITHUB_REPO=$(echo "$REPO_URL" | sed -E 's/.*[:/]([^/]+\/[^/]+)(\.git)?$/\1/' | sed 's/\.git$//')
            
            # Check if secrets are already configured
            EXISTING_SECRET=$(gh secret list --repo "$GITHUB_REPO" 2>/dev/null | grep -c "BACKEND_API_CLIENT_ID" || echo "0")
            
            if [ "$EXISTING_SECRET" = "0" ]; then
                echo ""
                echo "GitHub Actions is not fully configured for this repository."
                echo ""
                read -p "Would you like to set up CI/CD now? [y/N]: " setup_cicd
                
                if [[ "$setup_cicd" =~ ^[Yy]$ ]]; then
                    echo ""
                    echo "Running CI/CD setup..."
                    ./setup_github_cicd.sh
                else
                    echo ""
                    echo "To set up CI/CD later, run:"
                    echo "  ./setup_github_cicd.sh"
                    echo ""
                    echo "Or use azd pipeline config and manually add secrets:"
                    echo "  gh secret set BACKEND_API_CLIENT_ID --body \"$(azd env get-value BACKEND_API_CLIENT_ID)\""
                    echo "  gh secret set FRONTEND_SPA_CLIENT_ID --body \"$(azd env get-value FRONTEND_SPA_CLIENT_ID)\""
                fi
            else
                echo "✓ CI/CD pipeline is already configured"
            fi
        fi
    else
        echo ""
        echo "To enable CI/CD deployments, run:"
        echo "  ./setup_github_cicd.sh"
        echo ""
        echo "(Requires GitHub CLI: https://cli.github.com/)"
    fi
fi
