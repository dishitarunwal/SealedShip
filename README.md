# TrustDeploy

A container image supply-chain gate: images must carry a valid Cosign signature from the trusted
release key before they can be deployed. Verification fails closed, and every decision is audited.

## Layout
| Path | Purpose |
|---|---|
| `app/` | Sample containerised HTTP service |
| `trustdeploy/verifier.py` | Resolves tag → digest, runs `cosign verify`, classifies failures |
| `trustdeploy/policy.py` | Policy loading and the ACCEPT/REJECT gate (accepts only explicit success) |
| `trustdeploy/audit.py` | Append-only JSONL audit log (`audit/audit-log.jsonl`) |
| `trustdeploy/report.py` | HTML / CSV / JSON audit report |
| `trustdeploy/cli.py` | `verify`, `deploy --target docker|kind`, `report` |
| `trusted/` | Trusted public key and `policy.json` (private key lives in `~/.trustdeploy/keys`) |
| `k8s/` | kind config, namespace, Sigstore Policy Controller `ClusterImagePolicy`, deployment |
| `tests/cases.sh`, `tests/test_gate.py` | End-to-end cases TC01–TC06 and unit tests |
| `scripts/` | Step scripts, attack simulation, screenshot tooling, `run_all.sh` |
| `docs/PROGRESS.{md,html,pdf}` | Screenshot log of every step |

## Usage
```bash
python3 -m trustdeploy.cli verify localhost:5001/trustdeploy/sample-app:1.0.0
python3 -m trustdeploy.cli deploy localhost:5001/trustdeploy/sample-app:1.0.0      # exit 2 = blocked
python3 -m trustdeploy.cli report
python3 -m unittest tests.test_gate -v
./scripts/run_all.sh        # full reproducible demo + screenshots
```

## Cleanup
```bash
kind delete cluster --name trustdeploy
docker rm -f td-registry trustdeploy-app
```
