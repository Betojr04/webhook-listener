#!/bin/bash

echo "🧪 Testing Backend Endpoints"
echo "================================"
echo ""

echo "Test 1: GET /api/v1/chats"
echo "Expected: List of chats"
echo "---"
curl -s http://localhost:8000/api/v1/chats | python3 -m json.tool
echo ""
echo ""

echo "Test 2: GET /api/v1/messages (for swift-demo chat)"
echo "Expected: List of messages"
echo "---"
curl -s "http://localhost:8000/api/v1/messages?chatId=swift-demo&limit=3" | python3 -m json.tool
echo ""
echo ""

echo "Test 3: POST /api/v1/device/register"
echo "Expected: {ok: true, message: 'Device registered...'}"
echo "---"
curl -s -X POST http://localhost:8000/api/v1/device/register \
  -H "Content-Type: application/json" \
  -d '{"userId":"+14803187213","deviceToken":"test-token-from-script"}' | python3 -m json.tool
echo ""
echo ""

echo "Test 4: POST /api/v1/messages/send"
echo "Expected: {ok: true, message: {...}}"
echo "---"
curl -s -X POST http://localhost:8000/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"chatId":"swift-demo","to":"+14803187213","text":"Test from script at '$(date +%H:%M:%S)'"}' | python3 -m json.tool
echo ""
echo ""

echo "Test 5: Check whitelist protection (should FAIL)"
echo "Expected: 403 error - recipient not in whitelist"
echo "---"
curl -s -X POST http://localhost:8000/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"chatId":"test","to":"+15555555555","text":"This should be blocked"}'
echo ""
echo ""

echo "✅ All tests completed!"
echo ""
echo "Next: Open http://localhost:8000/docs in your browser to see interactive API docs"
