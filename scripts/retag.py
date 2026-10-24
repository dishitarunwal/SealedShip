#!/usr/bin/env python3
"""Point a tag at an existing manifest in the same repository, byte-for-byte (digest preserved).
Usage: retag.py <registry> <repo> <source-tag-or-digest> <new-tag>"""
import sys
import urllib.request

ACCEPT = ",".join([
    "application/vnd.oci.image.manifest.v1+json", "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json", "application/vnd.docker.distribution.manifest.list.v2+json",
])
reg, repo, src, tag = sys.argv[1:5]
base = f"http://{reg}/v2/{repo}/manifests/"
with urllib.request.urlopen(urllib.request.Request(base + src, headers={"Accept": ACCEPT})) as r:
    body, ctype = r.read(), r.headers["Content-Type"]
urllib.request.urlopen(urllib.request.Request(base + tag, data=body, method="PUT", headers={"Content-Type": ctype}))
