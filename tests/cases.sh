#!/usr/bin/env bash
# TrustDeploy end-to-end test cases. Usage: tests/cases.sh TC01|TC02|...|TC06
# Each case runs the real gate and asserts the expected decision from the exit code (0 = ACCEPT, 2 = REJECT).
set -uo pipefail
cd "$(dirname "$0")/.."
R=localhost:5001/trustdeploy/sample-app
GATE="python3 -m trustdeploy.cli"

expect() {  # expect <ACCEPT|REJECT> <label> <command...>
  local want=$1 label=$2; shift 2
  "$@"; local code=$?
  local got=REJECT; [ $code -eq 0 ] && got=ACCEPT
  if [ "$got" = "$want" ]; then echo "RESULT $label: PASS (expected $want, got $got)"; else echo "RESULT $label: FAIL (expected $want, got $got)"; return 1; fi
}

case "$1" in
TC01) echo "TC01 - correctly signed image (by mutable tag; gate resolves the digest)"; echo
      expect ACCEPT TC01 $GATE verify $R:1.0.0 --label TC01 ;;
TC02) echo "TC02 - unsigned image"; echo
      expect REJECT TC02 $GATE verify $R:1.1.0-unsigned --label TC02 ;;
TC03) echo "TC03 - image signed with an attacker's (untrusted) key"; echo
      expect REJECT TC03 $GATE verify $R:1.0.1-attacker --label TC03 ;;
TC04a) echo "TC04a - genuine trusted signature copied onto a different image"; echo
      expect REJECT TC04a $GATE verify $R:1.0.2-forged --label TC04a ;;
TC04b) echo "TC04b - attacker overwrites the trusted tag :1.0.0 with a tampered build"; echo
      python3 scripts/retag.py localhost:5001 trustdeploy/sample-app tampered-build 1.0.0
      echo "tag :1.0.0 now points to the tampered image"; echo
      expect REJECT TC04b $GATE verify $R:1.0.0 --label TC04b; rc=$?
      python3 scripts/retag.py localhost:5001 trustdeploy/sample-app "$(cut -d@ -f2 trusted/approved-image.txt)" 1.0.0
      echo; echo "(tag :1.0.0 restored to the approved digest for later tests)"; exit $rc ;;
TC05a) echo "TC05a - verification tool unavailable (cosign binary missing) on a VALID image"; echo
      TRUSTDEPLOY_COSIGN=/nonexistent/cosign expect REJECT TC05a $GATE deploy $R:1.0.0 --label TC05a ;;
TC05b) echo "TC05b - registry unreachable during verification of a VALID image"; echo
      docker stop td-registry >/dev/null; echo "registry stopped"; echo
      expect REJECT TC05b $GATE deploy $R:1.0.0 --label TC05b; rc=$?
      docker start td-registry >/dev/null; sleep 1; echo; echo "(registry restarted)"; exit $rc ;;
TC05c) echo "TC05c - image from a registry outside the policy allow-list"; echo
      expect REJECT TC05c $GATE verify docker.io/library/nginx:latest --label TC05c ;;
TC06) echo "TC06 - several images checked in one batch; each decision recorded separately"; echo
      before=$(wc -l < audit/audit-log.jsonl)
      for t in 1.0.0 1.1.0-unsigned 1.0.1-attacker 1.0.2-forged; do
        $GATE verify $R:$t --label TC06 | grep -E "image|decision"; echo
      done
      after=$(wc -l < audit/audit-log.jsonl)
      echo "audit entries added: $((after - before)) (expected 4)"
      python3 scripts/audit_tail.py 4
      [ $((after - before)) -eq 4 ] && echo "RESULT TC06: PASS" || { echo "RESULT TC06: FAIL"; exit 1; } ;;
*) echo "unknown case $1"; exit 1 ;;
esac
