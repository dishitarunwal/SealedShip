"""TrustDeploy web console: a local demo UI over the real verification gate.

  python3 -m trustdeploy.web            then open http://127.0.0.1:8765

Binds to localhost only. Every action calls the same code paths as the CLI, so each
decision is real and is written to the audit log.
"""
import hashlib
import json
import subprocess
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import audit
from .cli import deploy_command, evaluate
from .policy import ACCEPT, ROOT, key_fingerprints, load_policy

PORT = 8765
REGISTRY, REPO = "localhost:5001", "trustdeploy/sample-app"
UI = Path(__file__).with_name("ui.html")

# Demo scenarios map to the end-to-end test cases (some need setup, e.g. stopping the registry).
SCENARIOS = {
    "TC01": "Correctly signed image",
    "TC02": "Unsigned image",
    "TC03": "Signed with attacker's key",
    "TC04a": "Genuine signature copied to another image",
    "TC04b": "Trusted tag overwritten (tampered build)",
    "TC05a": "Cosign binary missing",
    "TC05b": "Registry unreachable",
    "TC05c": "Registry not in allow-list",
    "TC06": "Batch of 4 images",
}
DESCRIPTIONS = {
    "1.0.0": "Approved release, signed with the TrustDeploy key",
    "1.1.0-unsigned": "Built but never signed",
    "1.0.1-attacker": "Backdoored build signed with an attacker's key",
    "1.0.2-forged": "Carries a genuine signature copied from 1.0.0",
    "tampered-build": "Tampered build used to hijack the 1.0.0 tag",
}


def run(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"


def registry_images():
    try:
        with urllib.request.urlopen(f"http://{REGISTRY}/v2/{REPO}/tags/list", timeout=3) as r:
            tags = json.load(r)["tags"] or []
    except Exception as e:
        return {"online": False, "error": str(e), "images": []}
    tags = sorted(t for t in tags if not t.startswith("sha256-"))
    return {"online": True, "images": [
        {"ref": f"{REGISTRY}/{REPO}:{t}", "tag": t, "about": DESCRIPTIONS.get(t, "")} for t in tags
    ] + [{"ref": "docker.io/library/nginx:latest", "tag": "nginx:latest (Docker Hub)", "about": "Public image from a registry outside the allow-list"}]}


def policy_info():
    policy = load_policy()
    return {
        "name": policy["policy_name"],
        "description": policy["description"],
        "allowed_registries": policy["allowed_registries"],
        "keys": [{"path": str(Path(k).relative_to(ROOT)), "sha256": fp}
                 for k, fp in zip(policy["trusted_public_keys"], key_fingerprints(policy))],
        "public_key": Path(policy["trusted_public_keys"][0]).read_text(),
        "tlog": policy["transparency_log"],
    }


def gate_json(decision, result, entry):
    return {
        "decision": decision, "reason_code": result.reason_code, "reason": result.message,
        "image": result.image_ref, "digest": result.digest, "pinned_ref": result.pinned_ref,
        "evidence": result.tool_stderr, "duration_ms": result.duration_ms,
        "event_id": entry["event_id"], "timestamp": entry["timestamp_utc"],
    }


def do_verify(body):
    decision, result, entry, _ = evaluate(body["image"], "verify", "WEB-UI")
    return gate_json(decision, result, entry)


def do_deploy(body):
    target = body.get("target", "docker")
    decision, result, entry, _ = evaluate(body["image"], "deploy", "WEB-UI")
    out = gate_json(decision, result, entry)
    if decision != ACCEPT:
        out["deployment"] = {"status": "BLOCKED", "output": "Deployment blocked by the TrustDeploy policy gate. Nothing was deployed."}
        return out
    cmd = deploy_command(result.pinned_ref, target)
    code, output = run(cmd)
    if target == "docker" and code == 0:
        output += "\n\nApp is reachable at http://localhost:18088"
    out["deployment"] = {"status": "DEPLOYED" if code == 0 else "FAILED", "command": " ".join(cmd), "output": output}
    return out


def do_k8s_admission(body):
    """Ask the cluster to admit a pod directly, bypassing the TrustDeploy gate, to show the admission webhook."""
    image = body["image"]
    code, digest_out = run(["docker", "buildx", "imagetools", "inspect", image, "--format", "{{json .Manifest}}"], 30)
    if code != 0:
        return {"status": "ERROR", "output": digest_out}
    digest = json.loads(digest_out)["digest"]
    if not image.startswith(REGISTRY):
        return {"status": "ERROR", "output": "Only images from the TrustDeploy registry are mirrored into the cluster."}
    incluster = f"td-registry.local:5000/{REPO}@{digest}"
    name = "demo-" + hashlib.sha1(digest.encode()).hexdigest()[:8]
    run(["kubectl", "-n", "trustdeploy", "delete", "pod", name, "--ignore-not-found", "--wait=false"], 30)
    code, output = run(["kubectl", "-n", "trustdeploy", "run", name, "--restart=Never", f"--image={incluster}"], 60)
    return {"status": "ADMITTED" if code == 0 else "DENIED", "image": incluster, "output": output}


def k8s_status():
    code, out = run(["kubectl", "-n", "trustdeploy", "get", "pods", "-o", "json"], 15)
    if code != 0:
        return {"online": False, "error": out}
    pods = [{"name": p["metadata"]["name"], "phase": p["status"].get("phase"),
             "image": p["spec"]["containers"][0]["image"].split("/")[-1]} for p in json.loads(out)["items"]]
    _, pc = run(["kubectl", "-n", "cosign-system", "get", "pods", "-o", "jsonpath={.items[0].status.phase}"], 15)
    return {"online": True, "policy_controller": pc or "unknown", "pods": pods}


def do_scenario(body):
    sid = body["id"]
    if sid not in SCENARIOS:
        raise ValueError("unknown scenario")
    code, output = run(["bash", "tests/cases.sh", sid], 300)
    return {"id": sid, "title": SCENARIOS[sid], "passed": code == 0 and "FAIL" not in output, "output": output}


def do_report(_):
    from . import report
    return {"paths": [str(p.relative_to(ROOT)) for p in report.write_reports()]}


GET_ROUTES = {
    "/api/images": lambda: registry_images(),
    "/api/policy": lambda: policy_info(),
    "/api/audit": lambda: list(reversed(audit.read_all())),
    "/api/k8s": lambda: k8s_status(),
    "/api/scenarios": lambda: SCENARIOS,
}
POST_ROUTES = {
    "/api/verify": do_verify, "/api/deploy": do_deploy, "/api/k8s/admit": do_k8s_admission,
    "/api/scenario": do_scenario, "/api/report": do_report,
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
        if path == "/report":
            f = ROOT / "audit" / "report.html"
            return self._send(200, f.read_bytes() if f.exists() else b"Generate the report first.", "text/html; charset=utf-8")
        if path in GET_ROUTES:
            try:
                return self._send(200, GET_ROUTES[path]())
            except Exception as e:
                return self._send(500, {"error": str(e)})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in POST_ROUTES:
            return self._send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            self._send(200, POST_ROUTES[self.path](body))
        except Exception as e:
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} {fmt % args}")


def main():
    print(f"TrustDeploy console on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
