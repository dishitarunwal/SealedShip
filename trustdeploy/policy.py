"""Deployment policy gate: turns a verification result into ACCEPT or REJECT."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACCEPT, REJECT = "ACCEPT", "REJECT"


def load_policy(path=ROOT / "trusted" / "policy.json"):
    policy = json.loads(Path(path).read_text())
    policy["trusted_public_keys"] = [str(ROOT / k) for k in policy["trusted_public_keys"]]
    return policy


def key_fingerprints(policy):
    """SHA-256 of each trusted public key file, so the audit log shows which key was trusted."""
    return [hashlib.sha256(Path(k).read_bytes()).hexdigest()[:16] for k in policy["trusted_public_keys"]]


def decide(result):
    # Fail closed: only an explicit, successful verification is accepted.
    return ACCEPT if result.verified is True else REJECT
