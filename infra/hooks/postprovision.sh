#!/bin/bash
# postprovision.sh - Updates SPA redirect URIs with production URL after deployment
# This script runs after infrastructure provisioning completes

set -e

echo "=========================================="
echo "Echo App - Post-Provisioning Setup"
echo "=========================================="

# Detect CI environment (GitHub Actions, Azure DevOps, etc.)
# In CI, we skip operations that require elevated Entra ID permissions
# since the federated credentials don't have Application.ReadWrite.All
IS_CI="${CI:-false}"
if [ "$IS_CI" = "true" ] || [ -n "$GITHUB_ACTIONS" ] || [ -n "$TF_BUILD" ]; then
    echo ""
    echo "🔄 Running in CI environment - skipping Entra ID operations"
    echo "   (Service principal and redirect URI updates are handled separately)"
    echo ""
    echo "=========================================="
    echo "Post-Provisioning Complete (CI mode)"
    echo "=========================================="
    exit 0
fi

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
            
            # Build the new list of URIs using jq if available, otherwise use Python.
            if command -v jq &> /dev/null; then
                NEW_URIS=$(echo "$CURRENT_URIS" | jq --arg uri "$FRONTEND_URI" '. + [$uri]')
            else
                # Fallback: use Python to safely append to the JSON array (URLs contain '/').
                PYTHON_BIN=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
                if [ -z "$PYTHON_BIN" ]; then
                    echo "ERROR: jq not available and no python interpreter found to update redirect URIs." >&2
                    exit 1
                fi

                NEW_URIS=$(CURRENT_URIS="$CURRENT_URIS" FRONTEND_URI="$FRONTEND_URI" "$PYTHON_BIN" - <<'PY'
import json
import os

current = json.loads(os.environ.get("CURRENT_URIS", "[]") or "[]")
uri = os.environ.get("FRONTEND_URI", "")

if uri and uri not in current:
    current.append(uri)

print(json.dumps(current))
PY
)
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
echo "Post-Provisioning Complete!"
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
echo ""
echo "Next Steps:"
echo "  To set up CI/CD, run: ./scripts/ci/setup_github_cicd.sh"
echo "=========================================="
