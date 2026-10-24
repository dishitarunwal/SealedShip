"""TrustDeploy command line.

  python -m trustdeploy.cli verify <image>            verify and record a decision
  python -m trustdeploy.cli deploy <image> [--target docker|kind]
                                                      verify, then deploy only on ACCEPT
  python -m trustdeploy.cli report                    write audit/report.{html,csv,json}

Exit codes: 0 accepted/deployed, 2 rejected (deployment blocked), 1 usage error.
"""
import argparse
import subprocess
import sys

from . import audit, report
from .policy import ACCEPT, decide, key_fingerprints, load_policy
from .verifier import verify_image

GREEN, RED, BOLD, END = ("\033[32m", "\033[31m", "\033[1m", "\033[0m") if sys.stdout.isatty() else ("",) * 4


def evaluate(image, action, label=None):
    """Verify, decide and audit one image; shared by the CLI and the web console."""
    policy = load_policy()
    result = verify_image(image, policy)
    decision = decide(result)
    entry = audit.record(result, decision, policy, key_fingerprints(policy), action, label)
    return decision, result, entry, policy


def deploy_command(ref, target):
    """The deployment command for an already verified, digest-pinned reference."""
    if target == "docker":
        subprocess.run(["docker", "rm", "-f", "trustdeploy-app"], capture_output=True)
        return ["docker", "run", "-d", "--name", "trustdeploy-app", "-p", "18088:8080", ref]
    incluster = ref.replace("localhost:5001", "td-registry.local:5000")
    return ["kubectl", "-n", "trustdeploy", "set", "image", "deployment/sample-app", f"app={incluster}"]


def gate(image, action, label=None):
    decision, result, entry, policy = evaluate(image, action, label)
    colour = GREEN if decision == ACCEPT else RED
    print(f"{BOLD}TrustDeploy policy gate{END}  (policy: {policy['policy_name']})")
    print(f"  image     : {image}")
    print(f"  digest    : {result.digest or '-'}")
    print(f"  decision  : {colour}{BOLD}{decision}{END}  [{result.reason_code}]")
    print(f"  reason    : {result.message}")
    if result.tool_stderr and decision != ACCEPT:
        print(f"  evidence  : {result.tool_stderr.splitlines()[-1][:140]}")
    print(f"  audit id  : {entry['event_id']}  @ {entry['timestamp_utc']}")
    return decision, result


def deploy(image, target, label=None):
    decision, result = gate(image, "deploy", label)
    if decision != ACCEPT:
        print(f"{RED}{BOLD}DEPLOYMENT BLOCKED{END}: {image} did not satisfy the trust policy. Nothing was deployed.")
        return 2
    # always deploy the exact digest that was verified, never the tag
    cmd = deploy_command(result.pinned_ref, target)
    print(f"{GREEN}{BOLD}DEPLOYING{END} verified digest -> {target}: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print((proc.stdout + proc.stderr).strip())
    return 0 if proc.returncode == 0 else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="trustdeploy")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("image")
    v.add_argument("--label")
    d = sub.add_parser("deploy")
    d.add_argument("image")
    d.add_argument("--target", choices=["docker", "kind"], default="docker")
    d.add_argument("--label")
    sub.add_parser("report")
    args = p.parse_args(argv)

    if args.cmd == "verify":
        decision, _ = gate(args.image, "verify", args.label)
        return 0 if decision == ACCEPT else 2
    if args.cmd == "deploy":
        return deploy(args.image, args.target, args.label)
    paths = report.write_reports()
    print("Audit report written:\n  " + "\n  ".join(str(p) for p in paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
