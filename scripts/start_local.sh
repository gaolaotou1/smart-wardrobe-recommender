#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
backend_python="/Users/gaolaotou/miniforge3/envs/tf_m1/bin/python"
agent_python="/Users/gaolaotou/Desktop/enter/envs/hello_agent/bin/python"

if [[ ! -x "$backend_python" || ! -x "$agent_python" ]]; then
  echo "未找到 tf_m1 或 hello_agent 环境，请先按 README 安装。" >&2
  exit 1
fi

cd "$project_dir"
"$agent_python" -m py_compile agent_service/main.py backend/app.py

FLASK_DEBUG=false "$backend_python" backend/app.py &
backend_pid=$!
"$agent_python" -m uvicorn agent_service.main:app --host 127.0.0.1 --port 8090 &
agent_pid=$!
(cd frontend && npm run dev -- --host 127.0.0.1) &
frontend_pid=$!

cleanup() {
  kill "$backend_pid" "$agent_pid" "$frontend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Flask: http://127.0.0.1:8088"
echo "Agent: http://127.0.0.1:8090"
echo "Web:   http://127.0.0.1:5173"
wait
