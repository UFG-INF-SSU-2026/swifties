#!/usr/bin/env bash
# Roda todas as suítes: Python (consumidor + publisher), dashboard (Node) e mobile (Jest).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/pytest ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-dev.txt
fi
[ -d dashboard/node_modules ] || (cd dashboard && npm install --silent)
[ -d mobile/node_modules ] || (cd mobile && npm install --silent --legacy-peer-deps)

echo "== consumidor + publisher (pytest) =="; .venv/bin/pytest
echo "== dashboard (node:test + jsdom) ==";   (cd dashboard && npm test --silent)
echo "== mobile (jest-expo) ==";              (cd mobile && npx jest)
