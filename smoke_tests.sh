#!/bin/bash
# =============================================================================
# Smoke Test Script for Echo App
# =============================================================================
# This script tests the backend API with and without authentication tokens.
# It verifies:
# 1. Public endpoints (health check) work without authentication
# 2. Protected endpoints return 401 without valid tokens
# 3. Protected endpoints work with valid X-User-Id header (auth disabled mode)
# 4. Cosmos DB connection is working
#
# Usage:
#   ./smoke_tests.sh                    # Run against local dev (http://localhost:8000)
#   ./smoke_tests.sh https://api.example.com  # Run against custom URL
#   ./smoke_tests.sh --with-token <token>     # Test with a real Entra token
#   ./smoke_tests.sh --help
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
BASE_URL="${1:-http://localhost:8000}"
TOKEN=""
VERBOSE=false
PASSED=0
FAILED=0
SKIPPED=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --with-token)
            TOKEN="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [BASE_URL] [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --with-token <token>  Test with a real Entra ID access token"
            echo "  --verbose, -v         Show detailed output"
            echo "  --help, -h            Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Test local dev server"
            echo "  $0 http://localhost:8000     # Test specific URL"
            echo "  $0 --with-token \$(az account get-access-token --resource api://xxx --query accessToken -o tsv)"
            exit 0
            ;;
        http*|https*)
            BASE_URL="$1"
            shift
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

print_test() {
    echo -e "\n${YELLOW}▶ TEST:${NC} $1"
}

print_pass() {
    echo -e "${GREEN}✓ PASS:${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}✗ FAIL:${NC} $1"
    ((FAILED++))
}

print_skip() {
    echo -e "${YELLOW}○ SKIP:${NC} $1"
    ((SKIPPED++))
}

print_info() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}  INFO:${NC} $1"
    fi
}

# Check if server is running
check_server() {
    print_test "Checking server availability at $BASE_URL"
    if curl -s --connect-timeout 5 "$BASE_URL/healthz" > /dev/null 2>&1; then
        print_pass "Server is reachable"
        return 0
    else
        print_fail "Server is not reachable at $BASE_URL"
        echo -e "${RED}Make sure the backend server is running.${NC}"
        exit 1
    fi
}

# Test: Health endpoint (public)
test_health_endpoint() {
    print_test "Health endpoint (GET /healthz) - should be public"
    
    response=$(curl -s -w "\n%{http_code}" "$BASE_URL/healthz")
    body=$(echo "$response" | head -n -1)
    status=$(echo "$response" | tail -n 1)
    
    print_info "Response: $body"
    print_info "Status: $status"
    
    if [ "$status" = "200" ]; then
        if echo "$body" | grep -q "healthy"; then
            print_pass "Health endpoint returns 200 with healthy status"
        else
            print_fail "Health endpoint returns 200 but body doesn't contain 'healthy'"
        fi
    else
        print_fail "Health endpoint returned $status instead of 200"
    fi
}

# Test: Root endpoint (public)
test_root_endpoint() {
    print_test "Root endpoint (GET /) - should be public"
    
    response=$(curl -s -w "\n%{http_code}" "$BASE_URL/")
    body=$(echo "$response" | head -n -1)
    status=$(echo "$response" | tail -n 1)
    
    print_info "Response: $body"
    print_info "Status: $status"
    
    if [ "$status" = "200" ]; then
        if echo "$body" | grep -q "name"; then
            print_pass "Root endpoint returns 200 with API info"
        else
            print_fail "Root endpoint returns 200 but missing expected fields"
        fi
    else
        print_fail "Root endpoint returned $status instead of 200"
    fi
}

# Test: Protected endpoint without auth
test_protected_no_auth() {
    print_test "Protected endpoint (GET /decks) without authentication"
    
    response=$(curl -s -w "\n%{http_code}" "$BASE_URL/decks")
    body=$(echo "$response" | head -n -1)
    status=$(echo "$response" | tail -n 1)
    
    print_info "Response: $body"
    print_info "Status: $status"
    
    if [ "$status" = "401" ]; then
        print_pass "Protected endpoint correctly returns 401 without auth"
    else
        print_fail "Protected endpoint returned $status instead of 401 (may indicate auth is disabled)"
    fi
}

# Test: Protected endpoint with X-User-Id (auth disabled mode)
test_protected_with_user_id() {
    print_test "Protected endpoint (GET /decks) with X-User-Id header (auth disabled mode)"
    
    response=$(curl -s -w "\n%{http_code}" -H "X-User-Id: smoke-test-user" "$BASE_URL/decks")
    body=$(echo "$response" | head -n -1)
    status=$(echo "$response" | tail -n 1)
    
    print_info "Response: $body"
    print_info "Status: $status"
    
    if [ "$status" = "200" ]; then
        if echo "$body" | grep -q "decks"; then
            print_pass "Protected endpoint works with X-User-Id header"
        else
            print_fail "Response missing expected 'decks' field"
        fi
    elif [ "$status" = "401" ]; then
        print_info "Auth is enabled - X-User-Id header not accepted"
        print_skip "X-User-Id test (auth is enabled, need Bearer token)"
    else
        print_fail "Unexpected status $status"
    fi
}

# Test: Protected endpoint with Bearer token
test_protected_with_token() {
    if [ -z "$TOKEN" ]; then
        print_skip "Bearer token test (no token provided, use --with-token)"
        return
    fi
    
    print_test "Protected endpoint (GET /decks) with Bearer token"
    
    response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/decks")
    body=$(echo "$response" | head -n -1)
    status=$(echo "$response" | tail -n 1)
    
    print_info "Response: $body"
    print_info "Status: $status"
    
    if [ "$status" = "200" ]; then
        if echo "$body" | grep -q "decks"; then
            print_pass "Protected endpoint works with Bearer token"
        else
            print_fail "Response missing expected 'decks' field"
        fi
    elif [ "$status" = "401" ]; then
        print_fail "Bearer token rejected (401) - token may be expired or invalid"
    elif [ "$status" = "403" ]; then
        print_fail "Bearer token forbidden (403) - insufficient permissions"
    else
        print_fail "Unexpected status $status"
    fi
}

# Test: Create and delete a deck (write operations)
test_crud_operations() {
    print_test "CRUD operations - Create and delete a test deck"
    
    # Determine auth header
    AUTH_HEADER=""
    if [ -n "$TOKEN" ]; then
        AUTH_HEADER="-H \"Authorization: Bearer $TOKEN\""
    else
        AUTH_HEADER="-H \"X-User-Id: smoke-test-user\""
    fi
    
    # Create a deck
    create_response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-User-Id: smoke-test-user" \
        -d '{"name": "Smoke Test Deck", "description": "Created by smoke test"}' \
        "$BASE_URL/decks" 2>/dev/null)
    
    create_body=$(echo "$create_response" | head -n -1)
    create_status=$(echo "$create_response" | tail -n 1)
    
    print_info "Create response: $create_body"
    print_info "Create status: $create_status"
    
    if [ "$create_status" = "200" ] || [ "$create_status" = "201" ]; then
        # Extract deck ID
        deck_id=$(echo "$create_body" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        
        if [ -n "$deck_id" ]; then
            print_pass "Created test deck with ID: $deck_id"
            
            # Delete the deck
            delete_response=$(curl -s -w "\n%{http_code}" \
                -X DELETE \
                -H "X-User-Id: smoke-test-user" \
                "$BASE_URL/decks/$deck_id" 2>/dev/null)
            
            delete_status=$(echo "$delete_response" | tail -n 1)
            
            if [ "$delete_status" = "200" ] || [ "$delete_status" = "204" ]; then
                print_pass "Deleted test deck successfully"
            else
                print_fail "Failed to delete test deck (status: $delete_status)"
            fi
        else
            print_fail "Created deck but couldn't extract ID"
        fi
    elif [ "$create_status" = "401" ]; then
        print_skip "CRUD test (authentication required)"
    else
        print_fail "Failed to create test deck (status: $create_status)"
    fi
}

# Test: Invalid token format
test_invalid_token() {
    print_test "Protected endpoint with invalid token format"
    
    response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer invalid.token.here" "$BASE_URL/decks")
    body=$(echo "$response" | head -n -1)
    status=$(echo "$response" | tail -n 1)
    
    print_info "Response: $body"
    print_info "Status: $status"
    
    if [ "$status" = "401" ]; then
        print_pass "Invalid token correctly rejected with 401"
    elif [ "$status" = "200" ]; then
        print_info "Auth appears to be disabled (accepting any token)"
        print_skip "Invalid token test (auth disabled)"
    else
        print_fail "Unexpected status $status for invalid token"
    fi
}

# Print summary
print_summary() {
    print_header "Test Summary"
    echo -e "${GREEN}Passed:  $PASSED${NC}"
    echo -e "${RED}Failed:  $FAILED${NC}"
    echo -e "${YELLOW}Skipped: $SKIPPED${NC}"
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed! ✓${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed. ✗${NC}"
        return 1
    fi
}

# Main execution
main() {
    print_header "Echo App Smoke Tests"
    echo "Target: $BASE_URL"
    echo "Token provided: $([ -n "$TOKEN" ] && echo "Yes" || echo "No")"
    
    check_server
    
    print_header "Public Endpoints"
    test_health_endpoint
    test_root_endpoint
    
    print_header "Authentication Tests"
    test_protected_no_auth
    test_protected_with_user_id
    test_protected_with_token
    test_invalid_token
    
    print_header "Data Operations"
    test_crud_operations
    
    print_summary
}

main
