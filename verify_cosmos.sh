#!/bin/bash
# =============================================================================
# Cosmos DB Connection Verification Script
# =============================================================================
# This script verifies that Cosmos DB is accessible using the current
# authentication method (Managed Identity in Azure, Azure CLI locally, 
# or Cosmos DB Emulator for local development).
#
# Usage:
#   ./verify_cosmos.sh                  # Auto-detect mode
#   ./verify_cosmos.sh --emulator       # Test with local emulator
#   ./verify_cosmos.sh --azure          # Test with Azure credentials
#   ./verify_cosmos.sh --help
#
# Exit codes:
#   0 - Connection successful
#   1 - Connection failed
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
MODE="auto"
COSMOS_ENDPOINT="${COSMOS_ENDPOINT:-}"
COSMOS_DB_NAME="${COSMOS_DB_NAME:-echoapp}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --emulator)
            MODE="emulator"
            shift
            ;;
        --azure)
            MODE="azure"
            shift
            ;;
        --endpoint)
            COSMOS_ENDPOINT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --emulator          Test with local Cosmos DB emulator"
            echo "  --azure             Test with Azure credentials (Managed Identity or Azure CLI)"
            echo "  --endpoint <url>    Specify Cosmos DB endpoint"
            echo "  --help, -h          Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  COSMOS_ENDPOINT     Cosmos DB endpoint URL"
            echo "  COSMOS_DB_NAME      Database name (default: echoapp)"
            echo ""
            echo "Examples:"
            echo "  $0 --emulator                  # Test local emulator"
            echo "  $0 --azure --endpoint https://mydb.documents.azure.com:443/"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Detect mode if auto
detect_mode() {
    if [ "$MODE" = "auto" ]; then
        # Check if emulator is running
        if curl -sk "https://localhost:8081/_explorer/emulator.pem" > /dev/null 2>&1; then
            print_info "Detected local Cosmos DB emulator"
            MODE="emulator"
        elif [ -n "$COSMOS_ENDPOINT" ]; then
            print_info "Using COSMOS_ENDPOINT: $COSMOS_ENDPOINT"
            MODE="azure"
        else
            print_error "Could not detect Cosmos DB mode"
            print_info "Set COSMOS_ENDPOINT or run the emulator"
            exit 1
        fi
    fi
}

# Test emulator connection
test_emulator() {
    print_header "Testing Cosmos DB Emulator Connection"
    
    local emulator_url="https://localhost:8081"
    
    # Check if emulator is running
    print_info "Checking emulator at $emulator_url..."
    
    if ! curl -sk "$emulator_url/_explorer/emulator.pem" > /dev/null 2>&1; then
        print_error "Cosmos DB emulator is not running"
        print_info "Start it with: docker compose up cosmosdb -d"
        return 1
    fi
    
    print_success "Emulator is running"
    
    # Test database connection using Python
    print_info "Testing database connection..."
    
    python3 << 'PYTHON_SCRIPT'
import sys
try:
    from azure.cosmos import CosmosClient
    
    # Emulator well-known key
    EMULATOR_KEY = "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
    EMULATOR_ENDPOINT = "https://localhost:8081"
    
    client = CosmosClient(
        EMULATOR_ENDPOINT,
        credential=EMULATOR_KEY,
        connection_verify=False
    )
    
    # Try to list databases
    databases = list(client.list_databases())
    print(f"Connected! Found {len(databases)} database(s)")
    
    for db in databases:
        print(f"  - {db['id']}")
    
    sys.exit(0)
    
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
PYTHON_SCRIPT
    
    return $?
}

# Test Azure connection (Managed Identity / Azure CLI)
test_azure() {
    print_header "Testing Azure Cosmos DB Connection"
    
    if [ -z "$COSMOS_ENDPOINT" ]; then
        print_error "COSMOS_ENDPOINT is not set"
        print_info "Set COSMOS_ENDPOINT environment variable or use --endpoint"
        return 1
    fi
    
    print_info "Endpoint: $COSMOS_ENDPOINT"
    print_info "Database: $COSMOS_DB_NAME"
    
    # Check Azure CLI login
    print_info "Checking Azure CLI authentication..."
    
    if ! az account show > /dev/null 2>&1; then
        print_warning "Not logged in to Azure CLI"
        print_info "Run: az login"
        print_info "Note: In Azure, Managed Identity will be used instead"
    else
        local account=$(az account show --query "{name:name,id:id}" -o tsv)
        print_success "Azure CLI authenticated: $account"
    fi
    
    # Test database connection using Python with DefaultAzureCredential
    print_info "Testing database connection with DefaultAzureCredential..."
    
    COSMOS_ENDPOINT="$COSMOS_ENDPOINT" COSMOS_DB_NAME="$COSMOS_DB_NAME" python3 << 'PYTHON_SCRIPT'
import os
import sys
try:
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential
    
    endpoint = os.environ.get('COSMOS_ENDPOINT')
    db_name = os.environ.get('COSMOS_DB_NAME', 'echoapp')
    
    print(f"Connecting to {endpoint}...")
    
    credential = DefaultAzureCredential()
    client = CosmosClient(endpoint, credential=credential)
    
    # Try to get the database
    database = client.get_database_client(db_name)
    db_properties = database.read()
    
    print(f"Connected to database: {db_properties['id']}")
    
    # List containers
    containers = list(database.list_containers())
    print(f"Found {len(containers)} container(s):")
    for container in containers:
        print(f"  - {container['id']}")
    
    sys.exit(0)
    
except Exception as e:
    print(f"Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Ensure you're logged in: az login")
    print("2. Check your account has 'Cosmos DB Built-in Data Contributor' role")
    print("3. Verify COSMOS_ENDPOINT is correct")
    sys.exit(1)
PYTHON_SCRIPT
    
    return $?
}

# Test using the backend app directly
test_via_backend() {
    print_header "Testing via Backend Health Check"
    
    local backend_url="${BACKEND_URL:-http://localhost:8000}"
    
    print_info "Checking backend at $backend_url..."
    
    # Test health endpoint
    if curl -s "$backend_url/healthz" | grep -q "healthy"; then
        print_success "Backend health check passed"
    else
        print_warning "Backend health check failed or not running"
        return 1
    fi
    
    # Test database by attempting to list decks
    print_info "Testing database through API..."
    
    local response
    response=$(curl -s -w "\n%{http_code}" -H "X-User-Id: verify-script" "$backend_url/decks")
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1)
    
    if [ "$status" = "200" ]; then
        print_success "Database connection working (via API)"
        return 0
    elif [ "$status" = "401" ]; then
        print_warning "Authentication required - cannot test database via API"
        print_info "Use --emulator or --azure flag to test directly"
        return 0
    else
        print_error "API returned status $status"
        print_info "Response: $body"
        return 1
    fi
}

# Main execution
main() {
    print_header "Cosmos DB Connection Verification"
    
    detect_mode
    
    local result=0
    
    case $MODE in
        emulator)
            test_emulator || result=1
            ;;
        azure)
            test_azure || result=1
            ;;
    esac
    
    # Also test via backend if running
    test_via_backend || true
    
    echo ""
    if [ $result -eq 0 ]; then
        print_success "Cosmos DB verification completed successfully!"
    else
        print_error "Cosmos DB verification failed"
    fi
    
    return $result
}

main
