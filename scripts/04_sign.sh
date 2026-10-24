#!/usr/bin/env bash
# Phase 3b: sign the APPROVED image by digest (never by tag) with the trusted release key.
set -euo pipefail
REF=$(cat trusted/approved-image.txt)
echo "Approved image (digest-pinned): $REF"; echo
export COSIGN_PASSWORD="$(cat $HOME/.trustdeploy/keys/password)"
echo "-- Sigstore bundle format (OCI referrer), used by the TrustDeploy gate"
cosign sign --key $HOME/.trustdeploy/keys/cosign.key --tlog-upload=false --use-signing-config=false -y "$REF" 2>&1 | grep -v deprecated
echo "-- legacy .sig format, read by the Kubernetes Policy Controller admission webhook"
cosign sign --key $HOME/.trustdeploy/keys/cosign.key --tlog-upload=false --use-signing-config=false --new-bundle-format=false -y "$REF" 2>&1 | grep -v deprecated
echo; echo "Signature artifacts now attached to the image in the registry:"
cosign tree "$REF" 2>&1
