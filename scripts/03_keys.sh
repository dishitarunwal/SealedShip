#!/usr/bin/env bash
# Phase 3a: generate the trusted release key pair. The private key lives OUTSIDE the project.
set -euo pipefail
KEYDIR=$HOME/.trustdeploy/keys
mkdir -p "$KEYDIR" && chmod 700 "$KEYDIR"
[ -f "$KEYDIR/password" ] || (openssl rand -base64 24 > "$KEYDIR/password" && chmod 600 "$KEYDIR/password")
cd "$KEYDIR"
[ -f cosign.key ] || COSIGN_PASSWORD="$(cat password)" cosign generate-key-pair 2>&1
chmod 600 cosign.key
cp cosign.pub "$OLDPWD/trusted/cosign.pub"
cd "$OLDPWD"
echo "Private key (encrypted, never in repo/image):"; ls -l "$KEYDIR" | sed 's/^/  /'
echo; echo "Trusted public key committed to the project: trusted/cosign.pub"; cat trusted/cosign.pub
echo "SHA-256 fingerprint: $(shasum -a 256 trusted/cosign.pub | cut -c1-16)"
echo; echo "Is the private key anywhere in the project or the image?"
echo "  *.key files in project tree: $(find . -name "*.key" | grep -c . || true)"
docker run --rm localhost:5001/trustdeploy/sample-app:1.0.0 sh -c 'find / -name "*.key" 2>/dev/null | grep -c . || true' | sed 's/^/  *.key files inside image: /'
