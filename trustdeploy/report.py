"""Audit reporting: exports the audit log as JSON, CSV and a static HTML dashboard."""
import csv
import html
import json
from collections import Counter
from datetime import datetime, timezone

from .audit import ROOT, read_all

COLUMNS = ["timestamp_utc", "test_label", "action", "image_ref", "resolved_digest", "decision", "reason_code", "reason"]


def write_reports():
    entries = read_all()
    out = ROOT / "audit"
    (out / "report.json").write_text(json.dumps(entries, indent=2))
    with (out / "report.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(entries)
    (out / "report.html").write_text(_html(entries))
    return [out / "report.html", out / "report.csv", out / "report.json"]


def _html(entries):
    counts = Counter(e["decision"] for e in entries)
    reasons = Counter(e["reason_code"] for e in entries)
    rows = []
    for e in reversed(entries):
        cls = "acc" if e["decision"] == "ACCEPT" else "rej"
        digest = e["resolved_digest"] or ""
        evidence = html.escape((e.get("tool_stderr_excerpt") or "").splitlines()[-1][:160]) if e.get("tool_stderr_excerpt") else ""
        rows.append(
            f"<tr><td>{html.escape(e['timestamp_utc'])}</td><td>{html.escape(e.get('test_label') or '')}</td>"
            f"<td>{html.escape(e['action'])}</td><td class=mono>{html.escape(e['image_ref'])}</td>"
            f"<td class=mono title='{html.escape(digest)}'>{html.escape(digest[:19]) + "…" if digest else "—"}</td>"
            f"<td><span class='pill {cls}'>{e['decision']}</span></td><td class=mono>{e['reason_code']}</td>"
            f"<td>{html.escape(e['reason'])}<div class=ev>{evidence}</div></td></tr>"
        )
    reason_list = "".join(f"<li><b>{k}</b>: {v}</li>" for k, v in reasons.most_common())
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""<!doctype html><html><head><meta charset=utf-8><title>TrustDeploy Audit Report</title>
<style>
body{{font:14px -apple-system,Segoe UI,sans-serif;margin:0;background:#f5f6f8;color:#1d2330}}
header{{background:#1d2330;color:#fff;padding:20px 32px}} header h1{{margin:0;font-size:22px}} header p{{margin:4px 0 0;color:#aab}}
main{{padding:24px 32px}} .cards{{display:flex;gap:16px;margin-bottom:20px}}
.card{{background:#fff;border-radius:10px;padding:16px 22px;box-shadow:0 1px 3px #0002;min-width:150px}}
.card .n{{font-size:30px;font-weight:700}} .card.a .n{{color:#18864b}} .card.r .n{{color:#c62828}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px #0002}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #e6e8ee;vertical-align:top}} th{{background:#eef0f4;font-size:12px;text-transform:uppercase}}
.mono{{font-family:Menlo,monospace;font-size:12px}} .pill{{padding:2px 9px;border-radius:10px;font-weight:700;font-size:12px}}
.acc{{background:#d9f2e3;color:#18864b}} .rej{{background:#fbe0e0;color:#c62828}} .ev{{font-family:Menlo,monospace;font-size:11px;color:#777;margin-top:3px}}
</style></head><body>
<header><h1>TrustDeploy — Image Verification Audit Report</h1><p>Generated {generated} · policy trustdeploy-default · source audit/audit-log.jsonl</p></header>
<main><div class=cards>
<div class=card><div class=n>{len(entries)}</div>verification events</div>
<div class="card a"><div class=n>{counts.get('ACCEPT', 0)}</div>accepted</div>
<div class="card r"><div class=n>{counts.get('REJECT', 0)}</div>rejected</div>
<div class=card><b>Reasons</b><ul style="margin:6px 0 0;padding-left:18px">{reason_list}</ul></div></div>
<table><tr><th>Time (UTC)</th><th>Test</th><th>Action</th><th>Image</th><th>Digest</th><th>Decision</th><th>Reason code</th><th>Reason / evidence</th></tr>
{''.join(rows)}</table></main></body></html>"""
