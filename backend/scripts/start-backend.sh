#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
export NOVNC_PORT="${BACKEND_VNC_PORT:-6080}"

mkdir -p /tmp/runtime

Xvfb "$DISPLAY" -screen 0 1440x1024x24 -ac +extension RANDR >/tmp/runtime/xvfb.log 2>&1 &
fluxbox >/tmp/runtime/fluxbox.log 2>&1 &
x11vnc -display "$DISPLAY" -rfbport 5900 -forever -shared -nopw -xkb >/tmp/runtime/x11vnc.log 2>&1 &
/usr/share/novnc/utils/novnc_proxy --vnc localhost:5900 --listen "$NOVNC_PORT" >/tmp/runtime/novnc.log 2>&1 &

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
