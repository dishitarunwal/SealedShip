#!/usr/bin/env python3
"""Print the last N audit entries as a compact table. Usage: audit_tail.py [N]"""
import json
import sys
from pathlib import Path

n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
lines = (Path(__file__).resolve().parent.parent / "audit" / "audit-log.jsonl").read_text().splitlines()[-n:]
for l in lines:
    e = json.loads(l)
    print(f"  {e['event_id'][:8]}  {e['timestamp_utc']}  {(e['test_label'] or ''):<6} {e['image_ref'].split('/')[-1]:<28} {e['decision']:<7} {e['reason_code']}")
