#!/usr/bin/env bash
# Start the TrustDeploy web console and open the guided demo.
cd "$(dirname "$0")/.."
docker start td-registry >/dev/null 2>&1
lsof -ti tcp:8765 >/dev/null || (python3 -m trustdeploy.web >/dev/null 2>&1 &)
sleep 1
echo "TrustDeploy console: http://127.0.0.1:8765   (guided demo: http://127.0.0.1:8765/?demo)"
