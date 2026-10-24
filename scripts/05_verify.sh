#!/usr/bin/env bash
# Phase 4: verify the signed image, first directly with cosign, then through the TrustDeploy gate (by tag).
set -uo pipefail
REF=$(cat trusted/approved-image.txt)
echo "== cosign verify against trusted/cosign.pub =="
cosign verify --key trusted/cosign.pub --insecure-ignore-tlog=true "$REF" 2>&1 | grep -v "^WARNING" | python3 -c 'import sys
for l in sys.stdin:
    print(l.rstrip()[:200])'
echo; echo "== TrustDeploy gate, given the mutable tag :1.0.0 (resolved to digest first) =="
python3 -m trustdeploy.cli verify localhost:5001/trustdeploy/sample-app:1.0.0 --label TC01
