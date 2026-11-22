#!/bin/zsh
set -e
ROOT="${0:A:h}"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo '请先在终端运行：python3 -m venv .venv && .venv/bin/pip install -r requirements.txt'
  exit 1
fi
exec "$PY" -m backend.server --ws-port 8896 --swap-device-channels --data-root "$ROOT"
