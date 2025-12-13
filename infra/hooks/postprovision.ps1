# postprovision.ps1 - Updates SPA redirect URIs with production URL after deployment
# This script runs after infrastructure provisioning completes

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "Echo App - Post-Provisioning Setup"
Write-Host "=========================================="

# Detect CI environment (GitHub Actions, Azure DevOps, etc.)
# In CI, we skip operations that require elevated Entra ID permissions
# since the federated credentials don't have Application.ReadWrite.All
$isCI = $env:CI -eq "true" -or $env:GITHUB_ACTIONS -or $env:TF_BUILD
if ($isCI) {
    Write-Host ""
    Write-Host "🔄 Running in CI environment - skipping Entra ID operations"
    Write-Host "   (Service principal and redirect URI updates are handled separately)"
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "Post-Provisioning Complete (CI mode)"
    Write-Host "=========================================="
    exit 0
}

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
Write-Host "Post-Provisioning Complete!"
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
Write-Host ""
Write-Host "Next Steps:"
Write-Host "  To set up CI/CD, run: ./scripts/ci/setup_github_cicd.sh"
Write-Host "  (On Windows, use PowerShell: .\scripts\ci\setup_github_cicd.sh)"
Write-Host "=========================================="
