#!/bin/bash

# Path of Trading v1.0 - Wrapper Script
# This script manages the clipboard automation and launches the isolated python environment.

export YDOTOOL_SOCKET="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.ydotool_socket"

# Simulate Ctrl+C using ydotool to copy item data from Path of Exile 2
ydotool key 29:1 46:1 46:0 29:0

# Small delay to ensure the OS clipboard has time to synchronize
sleep 0.4

# Launch the backend script using the isolated Python virtual environment
VENV_PYTHON="$HOME/.local/share/pathoftrading-v1.0/venv/bin/python3"
SCRIPT_PATH="$HOME/.local/share/pathoftrading-v1.0/backend.py"

if [ -f "$VENV_PYTHON" ] && [ -f "$SCRIPT_PATH" ]; then
    "$VENV_PYTHON" "$SCRIPT_PATH" &
else
    notify-send "Path of Trading" "Installation not found. Please run install.sh"
fi