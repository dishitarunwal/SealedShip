#!/usr/bin/env bash
# Render a local HTML file to PNG with headless Chrome (does not touch the visible browser).
# Usage: htmlshot.sh <file.html> <out.png> [width] [height]
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --user-data-dir="$(mktemp -d)" --window-size="${3:-1700},${4:-1100}" --screenshot="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")" \
  "file://$(cd "$(dirname "$1")" && pwd)/$(basename "$1")" >/dev/null 2>&1
echo "[screenshot saved: $2]"
