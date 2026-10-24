#!/usr/bin/env bash
# Phase 5 setup: create the untrusted images used by the negative tests.
set -euo pipefail
REG=localhost:5001/trustdeploy/sample-app
digest() { docker buildx imagetools inspect "$1" --format '{{json .Manifest}}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["digest"])'; }

echo "[TC02] unsigned image  -> $REG:1.1.0-unsigned"
docker build -q --provenance=false --sbom=false --build-arg APP_VERSION=1.1.0-unsigned -t $REG:1.1.0-unsigned app >/dev/null && docker push -q $REG:1.1.0-unsigned >/dev/null

echo "[TC03] attacker builds a malicious image and signs it with THEIR OWN key -> $REG:1.0.1-attacker"
mkdir -p $HOME/.trustdeploy/attacker && cd $HOME/.trustdeploy/attacker
[ -f cosign.key ] || COSIGN_PASSWORD=attacker cosign generate-key-pair >/dev/null 2>&1
cd - >/dev/null
docker build -q --provenance=false --sbom=false --build-arg APP_VERSION=1.0.1-backdoored -t $REG:1.0.1-attacker app >/dev/null && docker push -q $REG:1.0.1-attacker >/dev/null
COSIGN_PASSWORD=attacker cosign sign --key $HOME/.trustdeploy/attacker/cosign.key --tlog-upload=false --use-signing-config=false -y "$REG@$(digest $REG:1.0.1-attacker)" 2>&1 | grep -E "Pushing"
COSIGN_PASSWORD=attacker cosign sign --key $HOME/.trustdeploy/attacker/cosign.key --tlog-upload=false --use-signing-config=false --new-bundle-format=false -y "$REG@$(digest $REG:1.0.1-attacker)" 2>&1 | grep -E "Pushing"
echo "   attacker key fingerprint: $(shasum -a 256 $HOME/.trustdeploy/attacker/cosign.pub | cut -c1-16)  (trusted: $(shasum -a 256 trusted/cosign.pub | cut -c1-16))"

echo "[TC04a] attacker copies the GENUINE signature of 1.0.0 onto their image -> $REG:1.0.2-forged"
docker build -q --provenance=false --sbom=false --build-arg APP_VERSION=1.0.2-forged -t $REG:1.0.2-forged app >/dev/null && docker push -q $REG:1.0.2-forged >/dev/null
python3 scripts/forge_signature.py localhost:5001 trustdeploy/sample-app "$(digest $REG:1.0.0)" "$(digest $REG:1.0.2-forged)"

echo "[TC04b] attacker builds a tampered 1.0.0 (pushed during the test over the trusted :1.0.0 tag)"
docker build -q --provenance=false --sbom=false --build-arg APP_VERSION=1.0.0-tampered -t $REG:tampered-build app >/dev/null && docker push -q $REG:tampered-build >/dev/null

echo; echo "Registry tags now present:"
curl -s localhost:5001/v2/trustdeploy/sample-app/tags/list | python3 -c 'import json,sys;[print("  ",t) for t in json.load(sys.stdin)["tags"]]'
