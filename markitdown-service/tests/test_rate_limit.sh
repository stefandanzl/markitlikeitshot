#!/bin/bash

# Configuration
API_ENDPOINT="http://localhost:8000/api/v1/convert/text"  # Correct endpoint for HTML to Markdown conversion
API_KEY="YOUR-API-KEY-HERE"
HTML_CONTENT="<html><head><title>Test</title></head><body><h1>Hello, World!</h1><p>This is a test HTML content.</p></body></html>"
TOTAL_REQUESTS=70  # Number of requests to make
DELAY=0.1         # Delay between requests in seconds

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Starting rate limit test..."
echo "Endpoint: $API_ENDPOINT"
echo "Total requests: $TOTAL_REQUESTS"
echo "Delay between requests: ${DELAY}s"
echo "----------------------------------------"

for ((i=1; i<=$TOTAL_REQUESTS; i++)); do
    echo -e "\nRequest $i of $TOTAL_REQUESTS"
    
    # Make the request and capture headers and status code
    response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
        -X POST "$API_ENDPOINT" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"content\": \"$HTML_CONTENT\"}" \
        -D -)

    # Extract status code
    status_code=$(echo "$response" | grep "HTTP_STATUS:" | cut -d':' -f2)
    
    # Extract rate limit headers
    remaining=$(echo "$response" | grep -i "X-RateLimit-Remaining:" | cut -d' ' -f2 | tr -d '\r')
    limit=$(echo "$response" | grep -i "X-RateLimit-Limit:" | cut -d' ' -f2 | tr -d '\r')
    reset=$(echo "$response" | grep -i "X-RateLimit-Reset:" | cut -d' ' -f2 | tr -d '\r')

    # Display results
    if [ "$status_code" == "200" ]; then
        echo -e "${GREEN}Status: $status_code - Success${NC}"
        ((successful_requests++))
    elif [ "$status_code" == "429" ]; then
        echo -e "${RED}Status: $status_code - Rate Limited${NC}"
        retry_after=$(echo "$response" | grep -i "Retry-After:" | cut -d' ' -f2 | tr -d '\r')
        echo -e "${YELLOW}Retry After: $retry_after seconds${NC}"
        ((rate_limited_requests++))
    else
        echo -e "${RED}Status: $status_code - Error${NC}"
        ((error_requests++))
    fi

    echo "Rate Limit Remaining: ${remaining:-N/A}"
    echo "Rate Limit Total: ${limit:-N/A}"
    echo "Reset Time: ${reset:-N/A}"

    # If rate limited, show warning
    if [ "$status_code" == "429" ]; then
        echo -e "${RED}Rate limit exceeded! Waiting for reset...${NC}"
        sleep 5
    fi

    # Add delay between requests
    sleep $DELAY
done

echo -e "\n----------------------------------------"
echo "Rate limit test completed"
echo -e "\nSummary:"
echo "Total Requests: $TOTAL_REQUESTS"
echo "Successful Requests: $successful_requests"
echo "Rate Limited Requests: $rate_limited_requests"
echo "Error Requests: $error_requests"
