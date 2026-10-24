#!/usr/bin/env python3
"""Build docs/PROGRESS.md and docs/PROGRESS.html (screenshot log of every significant step)."""
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

STEPS = [
    ("Phase 1 — Environment setup", "01-environment.png",
     "Docker, Cosign v3.1.3, Python, kind and kubectl are installed. A local OCI registry (registry:2) runs on localhost:5001, so no cloud resources are needed. The project tree separates the verifier, policy, audit and report components."),
    ("Phase 2 — Build the sample image and record its digest", "02-build-image.png",
     "The sample HTTP service is built and pushed with the versioned tag 1.0.0. The immutable manifest digest is recorded in trusted/approved-image.txt, and a smoke test confirms the container responds."),
    ("Phase 3a — Generate the trusted signing key pair", "03-key-generation.png",
     "Cosign generates an encrypted ECDSA P-256 key pair in ~/.trustdeploy/keys (mode 600, outside the project). Only the public key is copied into trusted/cosign.pub. Checks confirm there is no *.key file in the project tree or inside the image."),
    ("Phase 3b — Sign the approved image by digest", "04-sign-image.png",
     "The approved image is signed by digest, never by tag. Two signatures are stored: the Sigstore bundle (OCI referrer) used by the TrustDeploy gate, and the legacy .sig format read by the Kubernetes Policy Controller. The transparency-log upload is disabled for this offline prototype."),
    ("Phase 4 — Verify the trusted image (TC01)", "05-tc01-verify-trusted.png",
     "cosign verify validates the signature against trusted/cosign.pub. The TrustDeploy gate receives the mutable tag :1.0.0, resolves it to the digest, verifies it, checks that the signed payload names that exact digest, and returns ACCEPT. Result: TC01 passed."),
    ("Phase 5 — Prepare untrusted / attack images", "06-prepare-untrusted-images.png",
     "The negative tests use four images: an unsigned image; a backdoored image signed with an attacker's own key (a different fingerprint); an image carrying a genuine signature copied from 1.0.0 (scripts/forge_signature.py); and a tampered build used to hijack the :1.0.0 tag."),
    ("TC02 — Unsigned image", "07-tc02-unsigned.png", "Rejected with NO_SIGNATURE. Result: TC02 passed."),
    ("TC03 — Image signed with an untrusted key", "08-tc03-untrusted-key.png",
     "A signature exists, but it does not validate against the trusted key, so the image is rejected with UNTRUSTED_SIGNER. Result: TC03 passed."),
    ("TC04a — Genuine signature attached to a different image", "09-tc04a-copied-signature.png",
     "The copied signature is cryptographically valid, but its signed payload names a different digest, so the image is rejected with SIGNATURE_IMAGE_MISMATCH. Result: TC04 passed."),
    ("TC04b — Trusted tag overwritten with a tampered build", "10-tc04b-tag-hijack.png",
     "The attacker re-points :1.0.0 to a tampered build. The gate resolves the tag to the new digest, which carries no trusted signature, and rejects it. The tag is then restored."),
    ("TC05a — Verification tool unavailable", "11-tc05a-tool-missing.png",
     "Even for a validly signed image, a missing cosign binary results in VERIFICATION_TOOL_ERROR. The gate fails closed and deployment is blocked. Result: TC05 passed."),
    ("TC05b — Registry unreachable", "12-tc05b-registry-down.png",
     "With the registry stopped, the digest cannot be resolved, so the gate returns IMAGE_RESOLUTION_FAILED and blocks deployment."),
    ("TC05c — Registry outside the allow-list", "13-tc05c-registry-not-allowed.png",
     "docker.io is not in policy.json's allowed_registries, so the gate rejects the image before contacting the registry."),
    ("TC06 — Multiple images, separate audit records", "14-tc06-multiple-images.png",
     "Four images are checked in one batch, and four distinct audit entries are written, each with its own event ID, digest, decision and reason. Result: TC06 passed."),
    ("Unit tests — fail-closed logic", "15-unit-tests.png",
     "Eight unit tests, using a mocked cosign, cover acceptance, payload-digest mismatch, error classification, missing tool, timeout, unexpected exceptions, the registry allow-list, and the rule that the decision requires verified to be exactly True. All 8 passed."),
    ("Phase 6 — Policy enforcement in the deploy workflow", "16-deploy-gate-docker.png",
     "trustdeploy deploy blocks the attacker-signed image (exit code 2, nothing started). It deploys the trusted image pinned to the verified digest, and the running container answers on port 18088."),
    ("Phase 6 (K8s) — kind cluster + Sigstore Policy Controller", "17-k8s-setup.png",
     "A local kind cluster runs policy-controller 0.13.1 (Helm chart 0.10.8). The ClusterImagePolicy trustdeploy-signed-images requires the TrustDeploy release key for td-registry.local:5000/**, and the trustdeploy namespace is opted in."),
    ("Phase 6 (K8s) — admission-time enforcement", "18-k8s-admission.png",
     "The signed image is admitted and runs. The admission webhook denies the attacker-signed image ('invalid signature') and the unsigned image ('no signatures found'), so no pods are created for them."),
    ("Phase 7 — TC07 audit report export", "19-tc07-audit-report.png",
     "The audit log (JSONL) is exported to audit/report.html, report.csv and report.json. Each record holds the timestamp, image, digest, decision, reason code, policy, trusted-key fingerprint and a tool-evidence excerpt, and never any key material. Result: TC07 passed."),
    ("Phase 7 — Audit dashboard", "20-audit-dashboard.png",
     "The HTML dashboard summarises 14 verification events: 3 accepted and 11 rejected, broken down by reason, with per-event evidence."),
]

RESULTS = [
    ("TC01", "Correctly signed image", "Accepted", "ACCEPT — SIGNATURE_VERIFIED", "PASS"),
    ("TC02", "Unsigned image", "Rejected", "REJECT — NO_SIGNATURE", "PASS"),
    ("TC03", "Signed with untrusted key", "Rejected", "REJECT — UNTRUSTED_SIGNER", "PASS"),
    ("TC04", "Signature does not match image (copied signature / tag hijack)", "Rejected",
     "REJECT — SIGNATURE_IMAGE_MISMATCH / NO_SIGNATURE", "PASS"),
    ("TC05", "Tool error / registry down / registry not allowed", "Deployment denied",
     "REJECT — VERIFICATION_TOOL_ERROR / IMAGE_RESOLUTION_FAILED / REGISTRY_NOT_ALLOWED", "PASS"),
    ("TC06", "Multiple images checked", "Each recorded separately", "4 images → 4 audit entries", "PASS"),
    ("TC07", "Audit report generated", "Displayed / exported", "HTML + CSV + JSON written", "PASS"),
]

INTRO = ("This document records every significant step of the TrustDeploy implementation, with a screenshot taken "
         "immediately after each step. All screenshots come from a single clean run of scripts/run_all.sh on 2026-10-20 "
         "(local macOS, no cloud resources). Each one shows the exact command executed, its real output, its exit code "
         "and the capture time.")


def markdown():
    out = ["# TrustDeploy — Implementation Progress Log", "", INTRO, "", "## Test results summary", "",
           "| Test | Condition | Expected | Observed | Result |", "|---|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in RESULTS]
    out += ["", "## Step-by-step log", ""]
    for i, (title, img, text) in enumerate(STEPS, 1):
        out += [f"### {i}. {title}", "", text, "", f"![{title}](screenshots/{img})", ""]
    out += ["## Reproduce", "", "```bash", "cd ~/TrustDeploy && ./scripts/run_all.sh", "```", ""]
    return "\n".join(out)


def html_doc():
    rows = "".join(f"<tr><td>{a}</td><td>{html.escape(b)}</td><td>{c}</td><td>{html.escape(d)}</td><td class=pass>{e}</td></tr>"
                   for a, b, c, d, e in RESULTS)
    steps = "".join(
        f"<section><h3>{i}. {html.escape(t)}</h3><p>{html.escape(x)}</p><img src='screenshots/{img}'></section>"
        for i, (t, img, x) in enumerate(STEPS, 1))
    return f"""<!doctype html><html><head><meta charset=utf-8><title>TrustDeploy Progress Log</title><style>
body{{font:15px/1.5 -apple-system,Segoe UI,sans-serif;max-width:1000px;margin:32px auto;padding:0 20px;color:#1d2330}}
h1{{font-size:26px}} table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border:1px solid #d7dbe3;padding:6px 8px;text-align:left}}
th{{background:#eef0f4}} .pass{{color:#18864b;font-weight:700}} img{{width:100%;border-radius:8px;box-shadow:0 2px 8px #0003}}
section{{break-inside:avoid;margin:28px 0}} h3{{margin-bottom:4px}}</style></head><body>
<h1>TrustDeploy — Implementation Progress Log</h1><p>{html.escape(INTRO)}</p>
<h2>Test results summary</h2><table><tr><th>Test</th><th>Condition</th><th>Expected</th><th>Observed</th><th>Result</th></tr>{rows}</table>
<h2>Step-by-step log</h2>{steps}</body></html>"""


if __name__ == "__main__":
    (DOCS / "PROGRESS.md").write_text(markdown())
    (DOCS / "PROGRESS.html").write_text(html_doc())
    print("wrote docs/PROGRESS.md and docs/PROGRESS.html")
