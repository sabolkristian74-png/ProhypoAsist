#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

APP_FILE="Prohpo asistent Final.py"
LOG_FILE="$SCRIPT_DIR/webapp.log"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python nebol nájdený. Nainštalujte Python 3."
  exit 1
fi

# kill existing webapp process if running
pkill -f "$APP_FILE" 2>/dev/null || true

# start webapp in background
nohup "$PYTHON_BIN" "$APP_FILE" > "$LOG_FILE" 2>&1 &

# wait for startup (up to 15s)
for i in {1..30}; do
  if curl -sS -o /dev/null http://127.0.0.1:5000/; then
    break
  fi
  sleep 0.5
done

# check port
echo "Checking port 5000 status..."
netstat_output=$(ss -ltnp 2>/dev/null | grep ':5000' || true)
if [ -z "$netstat_output" ]; then
  echo "Port 5000 is not open. Check webapp.log for errors."
  tail -n 30 "$LOG_FILE"
  exit 1
fi

echo "Port 5000 is open:"
echo "$netstat_output"

echo "Testing endpoint..."
curl -I http://127.0.0.1:5000 || true

echo "Web app should now be running at http://127.0.0.1:5000"
echo "Bezi lokalne bez GitHub prihlasenia."