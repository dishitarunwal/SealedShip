#!/usr/bin/env bash
# Phase 2: build the sample app and push it to the local registry; record its immutable digest.
set -euo pipefail
REG=localhost:5001
docker build -q --provenance=false --sbom=false --build-arg APP_VERSION=1.0.0 -t $REG/trustdeploy/sample-app:1.0.0 app >/dev/null
docker push -q $REG/trustdeploy/sample-app:1.0.0 >/dev/null
DIGEST=$(docker buildx imagetools inspect $REG/trustdeploy/sample-app:1.0.0 --format '{{json .Manifest}}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["digest"])')
echo "Built and pushed: $REG/trustdeploy/sample-app:1.0.0"
echo "Immutable digest: $DIGEST"
echo "$REG/trustdeploy/sample-app@$DIGEST" > trusted/approved-image.txt
echo
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}' $REG/trustdeploy/sample-app
echo
echo "Smoke test of the image:"
docker run --rm -d --name td-smoke -p 18080:8080 $REG/trustdeploy/sample-app:1.0.0 >/dev/null; sleep 2
curl -s localhost:18080; echo; docker rm -f td-smoke >/dev/null
