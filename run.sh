#!/usr/bin/env bash
# One command: bootstrap if needed, then serve the dashboard.
#   ./run.sh                      -> http://127.0.0.1:8642
#   TTS_HOST=0.0.0.0 ./run.sh     -> expose on LAN
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] && [ -d Qwen3-TTS-12Hz-1.7B-CustomVoice ] || ./setup.sh
exec .venv/bin/python dashboard.py
