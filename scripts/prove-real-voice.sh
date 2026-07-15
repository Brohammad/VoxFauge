#!/usr/bin/env bash
# Prove a real-provider voice turn (Deepgram + OpenAI + Cartesia).
# Requires API keys in the environment and a running local/prod stack.
#
# Usage:
#   export DEEPGRAM_API_KEY=... OPENAI_API_KEY=... CARTESIA_API_KEY=...
#   export ACCESS_TOKEN=...   # JWT from /api/v1/auth/login
#   ./scripts/prove-real-voice.sh [base_url]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
: "${ACCESS_TOKEN:?Set ACCESS_TOKEN to a valid JWT}"
: "${DEEPGRAM_API_KEY:?}"
: "${OPENAI_API_KEY:?}"
: "${CARTESIA_API_KEY:?}"

echo "==> Creating websocket session via onboarding sample call"
# Onboarding sample uses configured providers; with real keys and DEMO_ENABLED=false
# this exercises STT/LLM/TTS end-to-end without a microphone.
resp="$(curl -fsS -X POST "${BASE_URL}/api/v1/onboarding/run-sample-call" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json")"

echo "${resp}" | python3 -c '
import json,sys
data=json.load(sys.stdin)
assert data.get("status")=="test_call_passed", data
print("session:", data.get("test_session_id"))
print("OK: real-provider sample call passed")
'
