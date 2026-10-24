"""Verification engine: resolves an image to its digest and checks its Cosign signature.

Every failure path returns a failed VerificationResult; nothing here raises to the
caller, so the policy gate can fail closed.
"""
import json
import os
import subprocess
import time
from dataclasses import dataclass, field

COSIGN = os.environ.get("TRUSTDEPLOY_COSIGN", "cosign")
DOCKER = os.environ.get("TRUSTDEPLOY_DOCKER", "docker")

# Reason codes recorded in the audit log.
VERIFIED = "SIGNATURE_VERIFIED"
UNSIGNED = "NO_SIGNATURE"
UNTRUSTED_KEY = "UNTRUSTED_SIGNER"
DIGEST_MISMATCH = "SIGNATURE_IMAGE_MISMATCH"
RESOLVE_ERROR = "IMAGE_RESOLUTION_FAILED"
TOOL_ERROR = "VERIFICATION_TOOL_ERROR"
REGISTRY_NOT_ALLOWED = "REGISTRY_NOT_ALLOWED"


@dataclass
class VerificationResult:
    image_ref: str
    digest: str | None = None
    pinned_ref: str | None = None
    verified: bool = False
    reason_code: str = TOOL_ERROR
    message: str = ""
    signatures: list = field(default_factory=list)
    tool_exit_code: int | None = None
    tool_stderr: str = ""
    duration_ms: int = 0


def split_ref(image_ref):
    """Return (repository, tag_or_None, digest_or_None) for an image reference."""
    digest = None
    if "@" in image_ref:
        image_ref, digest = image_ref.split("@", 1)
    tag = None
    last = image_ref.rsplit("/", 1)[-1]
    if ":" in last:
        image_ref, tag = image_ref.rsplit(":", 1)
    return image_ref, tag, digest


def registry_of(image_ref):
    first = image_ref.split("/", 1)[0]
    return first if ("." in first or ":" in first or first == "localhost") else "docker.io"


def resolve_digest(image_ref, timeout):
    """Resolve a (possibly mutable) tag to the immutable manifest digest in the registry."""
    repo, _, digest = split_ref(image_ref)
    if digest:
        return digest, None
    proc = subprocess.run(
        [DOCKER, "buildx", "imagetools", "inspect", image_ref, "--format", "{{json .Manifest}}"],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        return None, proc.stderr.strip() or proc.stdout.strip()
    return json.loads(proc.stdout)["digest"], None


def classify_failure(stderr):
    s = stderr.lower()
    if "no signatures found" in s or "no matching signatures: no signatures" in s:
        return UNSIGNED, "The image has no Cosign signature in the registry."
    if "does not match any digest in statement" in s or "invalid or missing digest in claim" in s:
        return DIGEST_MISMATCH, "A signature exists, but it was issued for a different image digest."
    if any(m in s for m in ("no matching signatures", "no matching attestations", "do not match threshold", "invalid signature")):
        return UNTRUSTED_KEY, "Signature(s) exist, but none validate against the trusted public key."
    return TOOL_ERROR, "Cosign could not complete verification; failing closed."


def _cosign_verify(pinned_ref, key, timeout):
    cmd = [COSIGN, "verify", "--key", key, "--insecure-ignore-tlog=true", "--output", "json", pinned_ref]
    env = dict(os.environ, COSIGN_EXPERIMENTAL="0")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def verify_image(image_ref, policy):
    start = time.monotonic()
    res = VerificationResult(image_ref=image_ref)
    timeout = policy.get("verification_timeout_seconds", 60)
    try:
        if registry_of(image_ref) not in policy["allowed_registries"]:
            res.reason_code = REGISTRY_NOT_ALLOWED
            res.message = f"Registry '{registry_of(image_ref)}' is not in the policy allow-list."
            return res

        digest, err = resolve_digest(image_ref, timeout)
        if not digest:
            res.reason_code = RESOLVE_ERROR
            res.message = "Could not resolve the image to a digest; failing closed."
            res.tool_stderr = (err or "")[-600:]
            return res
        res.digest = digest
        res.pinned_ref = f"{split_ref(image_ref)[0]}@{digest}"

        failures = []
        for key in policy["trusted_public_keys"]:
            proc = _cosign_verify(res.pinned_ref, key, timeout)
            res.tool_exit_code = proc.returncode
            if proc.returncode == 0:
                payloads = json.loads(proc.stdout)
                # Defence in depth: every accepted payload must name the exact digest we resolved.
                claimed = {p["critical"]["image"]["docker-manifest-digest"] for p in payloads}
                if claimed != {digest}:
                    res.reason_code = DIGEST_MISMATCH
                    res.message = f"Signed payload names {sorted(claimed)}, expected {digest}."
                    return res
                res.verified = True
                res.reason_code = VERIFIED
                res.message = f"Valid signature from trusted key {os.path.relpath(key)} for {digest[:19]}…"
                res.signatures = [p.get("optional") or {} for p in payloads]
                return res
            failures.append(proc.stderr.strip())

        res.tool_stderr = "\n".join(failures)[-600:]
        res.reason_code, res.message = classify_failure(res.tool_stderr)
        return res
    except FileNotFoundError as e:
        res.reason_code = TOOL_ERROR
        res.message = f"Verification tool not available ({e.filename}); failing closed."
        return res
    except subprocess.TimeoutExpired:
        res.reason_code = TOOL_ERROR
        res.message = "Verification timed out; failing closed."
        return res
    except Exception as e:  # any unexpected error must still deny
        res.reason_code = TOOL_ERROR
        res.message = f"Unexpected verification error ({type(e).__name__}: {e}); failing closed."
        return res
    finally:
        res.duration_ms = int((time.monotonic() - start) * 1000)
