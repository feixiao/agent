#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import json
from pathlib import Path

p = Path("/app/service_config.json")
p.write_text(json.dumps({"port": 8080, "healthcheck_path": "/healthz"}, indent=2) + "\n")
PY
