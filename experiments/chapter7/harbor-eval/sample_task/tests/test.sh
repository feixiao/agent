#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/verifier
if python3 - <<'PY'
import json
from pathlib import Path

cfg = json.loads(Path("/app/service_config.json").read_text())
assert cfg.get("port") == 8080
assert cfg.get("healthcheck_path") == "/healthz"
PY
then
  echo "1" > /logs/verifier/reward.txt
else
  echo "0" > /logs/verifier/reward.txt
fi
