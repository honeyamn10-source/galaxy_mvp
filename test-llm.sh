#!/bin/bash

# Test script for LLM Service integration
# This script verifies that Ollama and LLM service are properly configured
# Usage: bash test-llm.sh

set -e

echo "=========================================="
echo "Galaxy LLM Service Integration Test Suite"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILURES=0

# Helper function for test results
test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        FAILURES=$((FAILURES + 1))
    fi
}

# Test 1: Check if Ollama is reachable
echo "Test 1: Ollama Connectivity"
echo "---"
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags 2>/dev/null || echo "000")
if [ "$response" = "200" ]; then
    test_result 0 "Ollama is reachable at http://localhost:11434"
else
    test_result 1 "Ollama is not reachable (HTTP $response)"
    echo -e "${YELLOW}Hint: Is Ollama running? Try: ollama serve${NC}"
fi
echo ""

# Test 2: Check if required model is available
echo "Test 2: DeepSeek Model Availability"
echo "---"
response=$(curl -s http://localhost:11434/api/tags 2>/dev/null || echo "")
if echo "$response" | grep -q "deepseek"; then
    test_result 0 "DeepSeek model is available in Ollama"
    echo "  Available models:"
    echo "$response" | jq -r '.models[].name' | sed 's/^/    /' 2>/dev/null || echo "    (could not parse model list)"
else
    test_result 1 "DeepSeek model not found"
    echo -e "${YELLOW}Hint: Pull the model with: ollama pull deepseek-llm:6.7b${NC}"
fi
echo ""

# Test 3: Check if LLM service is running
echo "Test 3: LLM Service Health"
echo "---"
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8600/health 2>/dev/null || echo "000")
if [ "$response" = "200" ]; then
    test_result 0 "LLM service is reachable at http://localhost:8600"
    # Get detailed health info
    health=$(curl -s http://localhost:8600/health 2>/dev/null)
    echo "  Service status: $(echo "$health" | jq -r '.status' 2>/dev/null || echo "unknown")"
    echo "  LLM enabled: $(echo "$health" | jq -r '.llm_enabled' 2>/dev/null || echo "unknown")"
    echo "  Ollama available: $(echo "$health" | jq -r '.ollama_available' 2>/dev/null || echo "unknown")"
else
    test_result 1 "LLM service is not reachable (HTTP $response)"
    echo -e "${YELLOW}Hint: Is the LLM service running? Try: docker-compose up llm-service${NC}"
fi
echo ""

# Test 4: Test event analysis endpoint
echo "Test 4: Event Analysis Endpoint"
echo "---"
event_response=$(curl -s -X POST http://localhost:8600/analyze_event \
    -H "Content-Type: application/json" \
    -d '{
        "event_type": "intrusion_attempt",
        "confidence": 0.65,
        "device_id": "test-device",
        "frame_hash": "test123",
        "location": "north-gate"
    }' 2>/dev/null || echo "")

if echo "$event_response" | jq . > /dev/null 2>&1; then
    verdict=$(echo "$event_response" | jq -r '.verdict' 2>/dev/null || echo "unknown")
    confidence=$(echo "$event_response" | jq -r '.confidence' 2>/dev/null || echo "unknown")
    test_result 0 "Event analysis endpoint works"
    echo "  Verdict: $verdict"
    echo "  Confidence: $confidence"
else
    test_result 1 "Event analysis endpoint failed or returned invalid JSON"
    if [ -z "$event_response" ]; then
        echo -e "${YELLOW}Hint: LLM service may not be responding. Check: docker-compose logs llm-service${NC}"
    else
        echo "  Response was: $event_response"
    fi
fi
echo ""

# Test 5: Test chat endpoint
echo "Test 5: Chat Endpoint"
echo "---"
chat_response=$(curl -s -X POST http://localhost:8600/chat \
    -H "Content-Type: application/json" \
    -d '{
        "question": "What is event verification in a security system?"
    }' 2>/dev/null || echo "")

if echo "$chat_response" | jq . > /dev/null 2>&1; then
    answer=$(echo "$chat_response" | jq -r '.answer' 2>/dev/null | head -c 100)
    test_result 0 "Chat endpoint works"
    echo "  Response preview: $answer..."
else
    test_result 1 "Chat endpoint failed or returned invalid JSON"
    if [ -z "$chat_response" ]; then
        echo -e "${YELLOW}Hint: Check if Ollama is accessible and the model is running${NC}"
    else
        echo "  Response was: $chat_response"
    fi
fi
echo ""

# Test 6: Check Authority-chain connection
echo "Test 6: Authority-chain Integration"
echo "---"
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:1317/health 2>/dev/null || echo "000")
if [ "$response" = "200" ]; then
    test_result 0 "Authority-chain gateway is reachable"
    # Check if LLM service is configured
    health=$(curl -s http://localhost:1317/health 2>/dev/null)
    llm_url=$(echo "$health" | jq -r '.llm_service_url' 2>/dev/null || echo "not-configured")
    llm_available=$(echo "$health" | jq -r '.llm_available' 2>/dev/null || echo "unknown")
    echo "  LLM service URL: $llm_url"
    echo "  LLM available: $llm_available"
else
    test_result 1 "Authority-chain gateway is not reachable (HTTP $response)"
    echo -e "${YELLOW}Hint: Is the authority-chain service running? Try: docker-compose up authority-chain${NC}"
fi
echo ""

# Test 7: Test end-to-end event submission
echo "Test 7: End-to-End Event Submission with LLM"
echo "---"
submit_response=$(curl -s -X POST http://localhost:1317/galaxy/v1/events \
    -H "Content-Type: application/json" \
    -d '{
        "submitter": "test-user",
        "envelope_id": "test-env-'$(date +%s)'",
        "origin_peer_id": "test-peer",
        "event": {
            "device_id": "test-device",
            "event_type": "intrusion_attempt",
            "confidence": 0.65,
            "frame_hash": "test123",
            "location": "test-location"
        }
    }' 2>/dev/null || echo "")

if echo "$submit_response" | jq . > /dev/null 2>&1; then
    status=$(echo "$submit_response" | jq -r '.status' 2>/dev/null || echo "unknown")
    height=$(echo "$submit_response" | jq -r '.height' 2>/dev/null || echo "unknown")
    test_result 0 "Event submission successful"
    echo "  Status: $status"
    echo "  Height: $height"
else
    test_result 1 "Event submission failed or returned invalid response"
    echo "  Response was: $submit_response"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    echo ""
    echo "Your LLM service is properly configured."
    echo "You can now:"
    echo "  1. Submit events to http://localhost:1317 and they will be analyzed by LLM"
    echo "  2. Open the dashboard and use the chat widget"
    echo "  3. Monitor logs with: docker-compose logs -f llm-service"
    exit 0
else
    echo -e "${RED}$FAILURES test(s) failed.${NC}"
    echo ""
    echo "Troubleshooting steps:"
    echo "  1. Ensure Ollama is running: ollama serve"
    echo "  2. Verify the model is available: ollama list"
    echo "  3. Check service logs: docker-compose logs llm-service"
    echo "  4. Verify connectivity: curl http://localhost:11434/api/tags"
    echo "  5. Review the LLM Integration Guide: docs/LLM_INTEGRATION.md"
    exit 1
fi
