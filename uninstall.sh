#!/usr/bin/env bash
set -euo pipefail
if (( EUID == 0 )); then echo 'Run as your normal user.'; exit 1; fi
rm -f -- "$HOME/.local/share/applications/g502x-control.desktop" "$HOME/.local/share/g502x-control/app.py" "$HOME/.local/share/g502x-control/backend.py"
echo 'App removed. Mouse settings and shared system dependencies have been kept.'
