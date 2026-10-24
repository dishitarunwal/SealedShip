#!/usr/bin/env bash
# Phase 6: policy enforcement in the deployment workflow (local Docker target).
set -uo pipefail
R=localhost:5001/trustdeploy/sample-app
docker rm -f trustdeploy-app >/dev/null 2>&1
echo "### Attempt 1: deploy the attacker-signed image"
python3 -m trustdeploy.cli deploy $R:1.0.1-attacker --label DEPLOY-ATTACKER; echo "exit code: $?"
echo; echo "running containers named trustdeploy-app: $(docker ps -q --filter name=trustdeploy-app | wc -l | tr -d ' ')"
echo; echo "### Attempt 2: deploy the approved, signed image"
python3 -m trustdeploy.cli deploy $R:1.0.0 --label DEPLOY-TRUSTED; echo "exit code: $?"
sleep 2; echo
docker ps --filter name=trustdeploy-app --format 'running: {{.Names}}  image={{.Image}}'
echo "app response: $(curl -s localhost:18088)"
