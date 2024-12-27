#!/bin/bash

# URL and API Key
URL="http://localhost:8000/api/v1/convert/text"
API_KEY="rNC9HyOXgnE1FWTX8LeS1LJSsCZWQirVlRMWMagmDMQ"
CONTENT='{"content": "<p>Test</p>"}'

# Number of requests to send (more than the limit to trigger rate limiting)
REQUESTS=15

# Loop to send requests
for ((i=1; i<=REQUESTS; i++))
do
    echo "Request $i:"
    curl -i -X POST "$URL" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "$CONTENT"
    echo -e "\n-----------------\n"
    # Small delay to make output readable
    sleep 0.5
done