"""Audit logger: one JSON line per verification decision. Never records key material."""
import getpass
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "audit" / "audit-log.jsonl"


def record(result, decision, policy, key_fps, action, label=None):
    entry = {
        "event_id": str(uuid.uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "action": action,
        "test_label": label,
        "image_ref": result.image_ref,
        "resolved_digest": result.digest,
        "verified_ref": result.pinned_ref,
        "decision": decision,
        "reason_code": result.reason_code,
        "reason": result.message,
        "policy": policy["policy_name"],
        "trusted_key_sha256": key_fps,
        "tool_exit_code": result.tool_exit_code,
        "tool_stderr_excerpt": result.tool_stderr,
        "duration_ms": result.duration_ms,
        "operator": getpass.getuser(),
    }
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_all():
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]
