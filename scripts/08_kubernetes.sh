#!/usr/bin/env bash
# Phase 6 (Kubernetes extension): admission-time enforcement with Sigstore Policy Controller on kind.
set -uo pipefail
IN=td-registry.local:5000/trustdeploy/sample-app
digest() { docker buildx imagetools inspect "localhost:5001/trustdeploy/sample-app:$1" --format '{{json .Manifest}}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["digest"])'; }
echo "Cluster: $(kubectl config current-context)   Policy Controller: $(kubectl -n cosign-system get pods -o jsonpath='{.items[0].status.phase}')"
kubectl get clusterimagepolicy; kubectl get ns trustdeploy --show-labels | tail -1; echo
echo "### 1. Deploy the trusted, signed image (by digest)"
sed "s|IMAGE|$IN@$(digest 1.0.0)|" k8s/deployment.yaml | kubectl apply -f - 2>&1
kubectl -n trustdeploy rollout status deployment/sample-app --timeout=90s 2>&1 | tail -1
kubectl -n trustdeploy get pods -o wide | awk '{print $1, $2, $3}'; echo
echo "### 2. Try to deploy the attacker-signed image"
kubectl -n trustdeploy run attacker --restart=Never --image=$IN@$(digest 1.0.1-attacker) 2>&1 | fold -w 145; echo
echo "### 3. Try to deploy the unsigned image"
kubectl -n trustdeploy run unsigned --restart=Never --image=$IN@$(digest 1.1.0-unsigned) 2>&1 | fold -w 145; echo
echo "Pods in namespace trustdeploy:"; kubectl -n trustdeploy get pods --no-headers | awk '{print "  "$1, $3}'
