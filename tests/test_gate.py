"""Unit tests for the fail-closed policy gate (no registry or cosign needed)."""
import subprocess
import unittest
from unittest import mock

from trustdeploy import verifier
from trustdeploy.policy import ACCEPT, REJECT, decide

POLICY = {"trusted_public_keys": ["k.pub"], "allowed_registries": ["localhost:5001"], "verification_timeout_seconds": 5}
IMG = "localhost:5001/app@sha256:" + "a" * 64


def cosign(code, stdout="", stderr=""):
    return mock.patch.object(verifier, "_cosign_verify", return_value=subprocess.CompletedProcess([], code, stdout, stderr))


class GateTests(unittest.TestCase):
    def test_valid_signature_accepted(self):
        out = '[{"critical":{"image":{"docker-manifest-digest":"sha256:%s"}}}]' % ("a" * 64)
        with cosign(0, out):
            r = verifier.verify_image(IMG, POLICY)
        self.assertEqual((decide(r), r.reason_code), (ACCEPT, verifier.VERIFIED))

    def test_payload_for_other_digest_rejected_even_if_cosign_passes(self):
        out = '[{"critical":{"image":{"docker-manifest-digest":"sha256:%s"}}}]' % ("b" * 64)
        with cosign(0, out):
            r = verifier.verify_image(IMG, POLICY)
        self.assertEqual((decide(r), r.reason_code), (REJECT, verifier.DIGEST_MISMATCH))

    def test_failure_reasons_classified(self):
        cases = {
            "Error: no signatures found": verifier.UNSIGNED,
            "no matching attestations: accepted signatures do not match threshold": verifier.UNTRUSTED_KEY,
            "provided artifact digest does not match any digest in statement": verifier.DIGEST_MISMATCH,
            "something unexpected": verifier.TOOL_ERROR,
        }
        for err, code in cases.items():
            with self.subTest(err=err), cosign(1, stderr=err):
                r = verifier.verify_image(IMG, POLICY)
                self.assertEqual((decide(r), r.reason_code), (REJECT, code))

    def test_missing_tool_fails_closed(self):
        with mock.patch.object(verifier, "_cosign_verify", side_effect=FileNotFoundError(2, "x", "cosign")):
            r = verifier.verify_image(IMG, POLICY)
        self.assertEqual((decide(r), r.reason_code), (REJECT, verifier.TOOL_ERROR))

    def test_timeout_fails_closed(self):
        with mock.patch.object(verifier, "_cosign_verify", side_effect=subprocess.TimeoutExpired("cosign", 5)):
            r = verifier.verify_image(IMG, POLICY)
        self.assertEqual(decide(r), REJECT)

    def test_unexpected_exception_fails_closed(self):
        with cosign(0, "not json"):
            r = verifier.verify_image(IMG, POLICY)
        self.assertEqual((decide(r), r.reason_code), (REJECT, verifier.TOOL_ERROR))

    def test_registry_not_allowed(self):
        r = verifier.verify_image("docker.io/library/nginx:latest", POLICY)
        self.assertEqual((decide(r), r.reason_code), (REJECT, verifier.REGISTRY_NOT_ALLOWED))

    def test_decide_requires_explicit_true(self):
        r = verifier.VerificationResult(image_ref=IMG, verified="yes")
        self.assertEqual(decide(r), REJECT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
