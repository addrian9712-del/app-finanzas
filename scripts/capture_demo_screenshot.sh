#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/artifacts/screenshots"
OUT_FILE="$OUT_DIR/phase1_demo.png"

mkdir -p "$OUT_DIR"

start_services() {
  python "$ROOT_DIR/backend/mock_server.py" >/tmp/mock_server.log 2>&1 &
  MOCK_PID=$!
  python -m http.server 8080 >/tmp/static_server.log 2>&1 &
  STATIC_PID=$!
  sleep 2
}

stop_services() {
  if [[ -n "${MOCK_PID:-}" ]]; then kill "$MOCK_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "${STATIC_PID:-}" ]]; then kill "$STATIC_PID" >/dev/null 2>&1 || true; fi
}

run_node_playwright() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi
  if [[ ! -d "$ROOT_DIR/node_modules/playwright" ]]; then
    return 1
  fi
  node "$ROOT_DIR/scripts/take_demo_screenshot.mjs"
}

run_docker_playwright() {
  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi

  docker run --rm \
    --network host \
    -v "$ROOT_DIR:/work" \
    -w /work \
    mcr.microsoft.com/playwright:v1.53.0-jammy \
    bash -lc "node scripts/take_demo_screenshot.mjs"
}

trap stop_services EXIT
start_services

if run_node_playwright; then
  echo "Screenshot generated with local playwright: $OUT_FILE"
  exit 0
fi

if run_docker_playwright; then
  echo "Screenshot generated with docker playwright: $OUT_FILE"
  exit 0
fi

echo "ERROR: Could not generate screenshot automatically."
echo "- Missing local playwright package and Docker fallback unavailable."
echo "- Fix: install playwright locally or run CI workflow .github/workflows/ci-demo-screenshot.yml"
exit 1
