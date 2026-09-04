#!/usr/bin/env bash
# k8s/monitoring/import-dashboards.sh
# Import dashboards via Grafana HTTP API (alternative to sidecar)
set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3001}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-admin}"
DASH_DIR="$(dirname "$0")/dashboards"

command -v jq >/dev/null 2>&1 || { echo "jq required"; exit 1; }

for file in "$DASH_DIR"/*.json; do
    name=$(basename "$file")
    echo "Importing $name..."

    payload=$(jq -n \
        --argjson dashboard "$(cat "$file")" \
        '{"dashboard": $dashboard, "overwrite": true, "folderTitle": "MUKTI"}')

    curl -sf -X POST "$GRAFANA_URL/api/dashboards/db" \
        -H "Content-Type: application/json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -d "$payload" > /dev/null

    echo "  ✅ $name imported"
done

echo "✅ All dashboards imported"
