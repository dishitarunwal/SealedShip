#!/usr/bin/env bash
# Reproduce the whole TrustDeploy demonstration from a clean registry and audit log,
# saving a screenshot of every significant step to docs/screenshots/.
set -uo pipefail
cd "$(dirname "$0")/.."
S=docs/screenshots; shot() { python3 scripts/termshot.py "$S/$1.png" "$2" "$3"; echo; }

# clean slate (signing keys are kept)
docker rm -f td-registry trustdeploy-app >/dev/null 2>&1
docker run -d --restart=always -p 127.0.0.1:5001:5000 --name td-registry registry:2 >/dev/null
docker network connect --alias td-registry.local kind td-registry 2>/dev/null
kubectl -n trustdeploy delete deployment,pod --all --ignore-not-found >/dev/null 2>&1
rm -f audit/audit-log.jsonl audit/report.* $S/*.png; sleep 1

shot 01-environment        "Phase 1: Environment setup" 'docker version --format "Docker {{.Server.Version}}"; cosign version 2>&1 | grep GitVersion; python3 --version; kind version; kubectl version --client | head -1; echo; docker ps --filter name=td-registry --format "local registry: {{.Names}} {{.Image}} {{.Ports}}"; echo; echo "Project layout:"; find app trustdeploy trusted tests k8s scripts -type f -not -name "*.pyc" -not -name "__init__.py" | sort'
shot 02-build-image        "Phase 2: Build image & record digest" ./scripts/02_build.sh
shot 03-key-generation     "Phase 3: Generate trusted signing key" ./scripts/03_keys.sh
shot 04-sign-image         "Phase 3: Sign approved image with Cosign" ./scripts/04_sign.sh
shot 05-tc01-verify-trusted "Phase 4: Verify trusted image (TC01)" ./scripts/05_verify.sh
shot 06-prepare-untrusted-images "Phase 5: Prepare untrusted / attack images" ./scripts/06_prepare_untrusted.sh
shot 07-tc02-unsigned      "Phase 5: TC02 unsigned image" "tests/cases.sh TC02"
shot 08-tc03-untrusted-key "Phase 5: TC03 untrusted signing key" "tests/cases.sh TC03"
shot 09-tc04a-copied-signature "Phase 5: TC04a signature copied to another image" "tests/cases.sh TC04a"
shot 10-tc04b-tag-hijack   "Phase 5: TC04b trusted tag overwritten" "tests/cases.sh TC04b"
shot 11-tc05a-tool-missing "Phase 5: TC05a verification tool error" "tests/cases.sh TC05a"
shot 12-tc05b-registry-down "Phase 5: TC05b registry unreachable" "tests/cases.sh TC05b"
shot 13-tc05c-registry-not-allowed "Phase 5: TC05c registry not allowed" "tests/cases.sh TC05c"
shot 14-tc06-multiple-images "Phase 5: TC06 batch, separate audit records" "tests/cases.sh TC06"
shot 15-unit-tests         "Phase 5: Unit tests (fail-closed logic)" "python3 -m unittest tests.test_gate -v 2>&1"
shot 16-deploy-gate-docker "Phase 6: Policy enforcement in deploy workflow" ./scripts/07_deploy_gate.sh
shot 17-k8s-setup          "Phase 6: kind + Sigstore Policy Controller" 'kubectl get nodes -o wide | cut -c1-110; echo; helm list -n cosign-system; echo; kubectl -n cosign-system get pods; echo; cat k8s/cluster-image-policy.yaml'
shot 18-k8s-admission      "Phase 6: Kubernetes admission enforcement" ./scripts/08_kubernetes.sh
shot 19-tc07-audit-report  "Phase 7: TC07 audit report export" 'python3 -m trustdeploy.cli report && echo && echo "audit-log.jsonl entries: $(wc -l < audit/audit-log.jsonl)" && python3 scripts/audit_tail.py 30 && echo && head -3 audit/report.csv && echo && echo "Sample audit record:" && tail -n 1 audit/audit-log.jsonl | python3 -m json.tool'
./scripts/htmlshot.sh audit/report.html $S/20-audit-dashboard.png 1700 1160
