# postprovision.ps1 - Updates SPA redirect URIs with production URL after deployment
# This script runs after infrastructure provisioning completes

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "Echo App - Post-Provisioning Setup"
Write-Host "=========================================="

# Get values from azd environment
$SPA_APP_ID = azd env get-value AZURE_SPA_APP_ID 2>$null
$API_APP_ID = azd env get-value AZURE_API_APP_ID 2>$null
$FRONTEND_URI = azd env get-value FRONTEND_URI 2>$null

# ============================================
# Ensure Service Principal exists for API app
# ============================================
# This is required for the SPA to request tokens for the API
if (-not [string]::IsNullOrEmpty($API_APP_ID)) {
    Write-Host ""
    Write-Host "Ensuring service principal exists for API app..."
    
    # Check if service principal already exists
    $spExists = az ad sp show --id $API_APP_ID --query "id" -o tsv 2>$null
    
    if (-not [string]::IsNullOrEmpty($spExists)) {
        Write-Host "✓ Service principal already exists for API app ($API_APP_ID)"
    } else {
        Write-Host "Creating service principal for API app ($API_APP_ID)..."
        az ad sp create --id $API_APP_ID --output none
        Write-Host "✓ Service principal created successfully"
    }
} else {
    Write-Host "WARNING: AZURE_API_APP_ID not found. Skipping service principal creation."
}

if ([string]::IsNullOrEmpty($SPA_APP_ID)) {
    Write-Host "WARNING: AZURE_SPA_APP_ID not found in environment. Skipping redirect URI update."
} else {
    Write-Host "SPA App ID: $SPA_APP_ID"
    
    if (-not [string]::IsNullOrEmpty($FRONTEND_URI) -and $FRONTEND_URI -ne "null") {
        Write-Host "Frontend URL: $FRONTEND_URI"
        Write-Host ""
        Write-Host "Updating SPA redirect URIs..."
        
        # Get current redirect URIs
        $currentUrisJson = az ad app show --id $SPA_APP_ID --query "spa.redirectUris" -o json 2>$null
        if ([string]::IsNullOrEmpty($currentUrisJson)) {
            $currentUrisJson = "[]"
        }
        $currentUris = $currentUrisJson | ConvertFrom-Json
        
        # Check if the frontend URI is already in the list
        if ($currentUris -contains $FRONTEND_URI) {
            Write-Host "Frontend URI already configured in SPA app registration."
        } else {
            Write-Host "Adding $FRONTEND_URI to SPA redirect URIs..."
            
            # Build the new list of URIs
            $newUris = @($currentUris) + @($FRONTEND_URI)
            $newUrisJson = $newUris | ConvertTo-Json -Compress
            if ($newUris.Count -eq 1) {
                $newUrisJson = "[$newUrisJson]"
            }
            
            # Create temp file with the full SPA object
            $tempFile = [System.IO.Path]::GetTempFileName()
            @"
{"spa": {"redirectUris": $newUrisJson}}
"@ | Out-File -FilePath $tempFile -Encoding UTF8
            
            # Get the object ID of the app (needed for REST API)
            $APP_OBJECT_ID = az ad app show --id $SPA_APP_ID --query "id" -o tsv
            
            # Use az rest to update the app via Graph API
            az rest --method PATCH `
                --uri "https://graph.microsoft.com/v1.0/applications/$APP_OBJECT_ID" `
                --headers "Content-Type=application/json" `
                --body "@$tempFile"
            
            Remove-Item $tempFile
            Write-Host "✓ Successfully added $FRONTEND_URI to SPA redirect URIs"
        }
    } else {
        Write-Host "WARNING: FRONTEND_URI not available. Redirect URI update skipped."
        Write-Host "You may need to manually add the production URL to the SPA app registration."
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Deployment Complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Environment:              $env:AZURE_ENV_NAME"
Write-Host "Frontend URL:             $FRONTEND_URI"
Write-Host "Backend URL (internal):   $env:BACKEND_URI"
Write-Host ""
Write-Host "Entra ID Configuration:"
Write-Host "  Tenant ID:              $env:AZURE_TENANT_ID"
Write-Host "  Backend API App ID:     $env:AZURE_API_APP_ID"
Write-Host "  Frontend SPA App ID:    $SPA_APP_ID"
Write-Host "=========================================="

# ============================================
# Automatic CI/CD Pipeline Setup
# ============================================

function Setup-GitHubCICD {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "Configuring GitHub Actions CI/CD"
    Write-Host "=========================================="
    
    # Get repository info
    $REPO_URL = git remote get-url origin 2>$null
    if ([string]::IsNullOrEmpty($REPO_URL)) {
        Write-Host "WARNING: Not a git repository. Skipping CI/CD setup."
        return
    }
    
    $GITHUB_REPO = $REPO_URL -replace '.*[:/]([^/]+/[^/]+)(\.git)?$', '$1' -replace '\.git$', ''
    Write-Host "Repository: $GITHUB_REPO"
    
    # Get values from azd environment
    $TENANT_ID = azd env get-value AZURE_TENANT_ID 2>$null
    $SUBSCRIPTION_ID = azd env get-value AZURE_SUBSCRIPTION_ID 2>$null
    if ([string]::IsNullOrEmpty($SUBSCRIPTION_ID)) {
        $SUBSCRIPTION_ID = az account show --query id -o tsv 2>$null
    }
    $API_APP_ID_VAL = azd env get-value AZURE_API_APP_ID 2>$null
    if ([string]::IsNullOrEmpty($API_APP_ID_VAL)) {
        $API_APP_ID_VAL = azd env get-value BACKEND_API_CLIENT_ID 2>$null
    }
    $SPA_APP_ID_VAL = azd env get-value AZURE_SPA_APP_ID 2>$null
    if ([string]::IsNullOrEmpty($SPA_APP_ID_VAL)) {
        $SPA_APP_ID_VAL = azd env get-value FRONTEND_SPA_CLIENT_ID 2>$null
    }
    
    # Check if azd pipeline is already configured
    $AZD_PRINCIPAL = azd env get-value AZURE_CLIENT_ID 2>$null
    
    if ([string]::IsNullOrEmpty($AZD_PRINCIPAL)) {
        Write-Host "Running azd pipeline config to set up service principal..."
        try {
            azd pipeline config --provider github --principal-name "github-actions-echo-app" 2>$null
            $AZD_PRINCIPAL = azd env get-value AZURE_CLIENT_ID 2>$null
        } catch {
            Write-Host "WARNING: azd pipeline config failed. You may need to run it manually."
            Write-Host "  azd pipeline config"
            return
        }
    } else {
        Write-Host "✓ Azure service principal already configured: $AZD_PRINCIPAL"
    }
    
    # Set GitHub repository variables using gh CLI
    if (-not [string]::IsNullOrEmpty($AZD_PRINCIPAL)) {
        Write-Host "Setting GitHub repository variables..."
        gh variable set AZURE_CLIENT_ID --body $AZD_PRINCIPAL --repo $GITHUB_REPO 2>$null
        gh variable set AZURE_TENANT_ID --body $TENANT_ID --repo $GITHUB_REPO 2>$null
        gh variable set AZURE_SUBSCRIPTION_ID --body $SUBSCRIPTION_ID --repo $GITHUB_REPO 2>$null
        Write-Host "✓ GitHub variables configured"
    }
    
    # Set GitHub secrets for app registrations
    if (-not [string]::IsNullOrEmpty($API_APP_ID_VAL) -and -not [string]::IsNullOrEmpty($SPA_APP_ID_VAL)) {
        Write-Host "Setting GitHub repository secrets..."
        gh secret set BACKEND_API_CLIENT_ID --body $API_APP_ID_VAL --repo $GITHUB_REPO 2>$null
        gh secret set FRONTEND_SPA_CLIENT_ID --body $SPA_APP_ID_VAL --repo $GITHUB_REPO 2>$null
        Write-Host "✓ GitHub secrets configured"
    } else {
        Write-Host "WARNING: App registration IDs not found. Secrets not configured."
    }
    
    Write-Host ""
    Write-Host "✓ GitHub Actions CI/CD configured successfully!"
    Write-Host "  Push to main branch to trigger deployment."
}

# Only run CI/CD setup if gh CLI is available and authenticated
$ghExists = Get-Command gh -ErrorAction SilentlyContinue
if ($ghExists) {
    $ghAuth = gh auth status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Setup-GitHubCICD
    } else {
        Write-Host ""
        Write-Host "NOTE: GitHub CLI not authenticated. Skipping automatic CI/CD setup."
        Write-Host "  To configure CI/CD later, run: gh auth login; azd pipeline config"
    }
} else {
    Write-Host ""
    Write-Host "NOTE: GitHub CLI not installed. Skipping automatic CI/CD setup."
    Write-Host "  Install from: https://cli.github.com/"
    Write-Host "  Then run: azd pipeline config"
}
