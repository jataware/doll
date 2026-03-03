"""Run as root: sudo PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 test_endpoints.py"""
import os
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PORT", "5111")

import json
import threading
import time
import urllib.request

import uvicorn
from doll.server import app
from doll.config import config

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=config.port, log_level="warning")

t = threading.Thread(target=start_server, daemon=True)
t.start()
time.sleep(2)

BASE = f"http://127.0.0.1:{config.port}"

def fetch(path: str, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()

print("=" * 60)
print("GET /v2/")
status, headers, body = fetch("/v2/")
print(f"  {status} -> {body.decode()}")

print()
print("GET /v2/_catalog")
status, headers, body = fetch("/v2/_catalog")
catalog = json.loads(body)
print(f"  {status} -> {catalog['repositories'][:5]}...")

repo = catalog["repositories"][0] if catalog["repositories"] else None
if repo:
    print()
    print(f"GET /v2/{repo}/tags/list")
    status, headers, body = fetch(f"/v2/{repo}/tags/list")
    tags = json.loads(body)
    print(f"  {status} -> {tags}")

    tag = tags["tags"][0]
    print()
    print(f"HEAD /v2/{repo}/manifests/{tag}")
    status, headers, _ = fetch(f"/v2/{repo}/manifests/{tag}", method="HEAD")
    print(f"  {status}")
    print(f"  Content-Type: {headers.get('Content-Type')}")
    print(f"  Docker-Content-Digest: {headers.get('Docker-Content-Digest')}")
    print(f"  Content-Length: {headers.get('Content-Length')}")

    print()
    print(f"GET /v2/{repo}/manifests/{tag}")
    status, headers, body = fetch(f"/v2/{repo}/manifests/{tag}")
    manifest = json.loads(body)
    print(f"  {status} ({len(body)} bytes)")
    print(f"  mediaType: {manifest.get('mediaType')}")
    print(f"  config digest: {manifest.get('config', {}).get('digest', 'N/A')}")
    layers = manifest.get("layers", [])
    print(f"  layers: {len(layers)}")

    # Fetch config blob
    config_digest = manifest.get("config", {}).get("digest")
    if config_digest:
        print()
        print(f"HEAD /v2/{repo}/blobs/{config_digest}")
        status, headers, _ = fetch(f"/v2/{repo}/blobs/{config_digest}", method="HEAD")
        print(f"  {status}")
        print(f"  Content-Length: {headers.get('Content-Length')}")
        print(f"  Docker-Content-Digest: {headers.get('Docker-Content-Digest')}")

        print()
        print(f"GET /v2/{repo}/blobs/{config_digest}")
        status, headers, body = fetch(f"/v2/{repo}/blobs/{config_digest}")
        print(f"  {status} ({len(body)} bytes)")
        blob_json = json.loads(body)
        print(f"  architecture: {blob_json.get('architecture')}")
        print(f"  os: {blob_json.get('os')}")

    # Fetch first layer blob (just HEAD to confirm it works)
    if layers:
        layer_digest = layers[0]["digest"]
        print()
        print(f"HEAD /v2/{repo}/blobs/{layer_digest}")
        status, headers, _ = fetch(f"/v2/{repo}/blobs/{layer_digest}", method="HEAD")
        print(f"  {status}")
        print(f"  Content-Length: {headers.get('Content-Length')}")

    # Test digest-based manifest fetch
    manifest_digest = headers.get("Docker-Content-Digest") or manifest.get("config", {}).get("digest")
    # Use the actual manifest digest from the HEAD call above
    print()
    print(f"GET /v2/{repo}/manifests/{tag} (get digest for by-digest test)")
    status, h, _ = fetch(f"/v2/{repo}/manifests/{tag}", method="HEAD")
    real_manifest_digest = h.get("Docker-Content-Digest")
    if real_manifest_digest:
        print(f"GET /v2/{repo}/manifests/{real_manifest_digest}")
        status, headers, body = fetch(f"/v2/{repo}/manifests/{real_manifest_digest}")
        print(f"  {status} ({len(body)} bytes)")

print()
print("GET /v2/nonexistent/tags/list (should be 404)")
status, _, body = fetch("/v2/nonexistent/tags/list")
print(f"  {status} -> {body.decode()}")

print()
print("GET /v2/nonexistent/manifests/latest (should be 404)")
status, _, body = fetch("/v2/nonexistent/manifests/latest")
print(f"  {status} -> {body.decode()}")

print()
print("GET /v2/nonexistent/blobs/sha256:0000 (should be 404)")
status, _, body = fetch("/v2/nonexistent/blobs/sha256:0000")
print(f"  {status} -> {body.decode()}")
