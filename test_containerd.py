"""Test script to explore containerd gRPC API capabilities.
Run as root: sudo python3 test_containerd.py
"""
import json

import grpc
from containerd.services.images.v1 import images_pb2, images_pb2_grpc
from containerd.services.content.v1 import content_pb2, content_pb2_grpc

NAMESPACE = "moby"
SOCKET = "unix:///run/containerd/containerd.sock"
MD = [("containerd-namespace", NAMESPACE)]

channel = grpc.insecure_channel(SOCKET)
images_stub = images_pb2_grpc.ImagesStub(channel)
content_stub = content_pb2_grpc.ContentStub(channel)

# 1. List first 5 images and their target descriptors
print("=" * 60)
print("1. IMAGES (first 5)")
print("=" * 60)
resp = images_stub.List(images_pb2.ListImagesRequest(), metadata=MD)
for img in resp.images[:5]:
    print(f"  name:       {img.name}")
    print(f"  media_type: {img.target.media_type}")
    print(f"  digest:     {img.target.digest}")
    print(f"  size:       {img.target.size}")
    print()

# 2. Pick the first image and read its target content (the manifest or index)
if resp.images:
    first = resp.images[0]
    digest = first.target.digest
    print("=" * 60)
    print(f"2. READ CONTENT for {first.name}")
    print(f"   digest: {digest}")
    print(f"   media_type: {first.target.media_type}")
    print("=" * 60)

    # Get info (size, labels) for this digest
    try:
        info_resp = content_stub.Info(
            content_pb2.InfoRequest(digest=digest), metadata=MD
        )
        print(f"  Info.digest: {info_resp.info.digest}")
        print(f"  Info.size:   {info_resp.info.size}")
        labels = dict(info_resp.info.labels)
        if labels:
            print(f"  Info.labels: {json.dumps(labels, indent=4)}")
    except Exception as e:
        print(f"  Info error: {e}")

    # Read the raw content bytes
    try:
        read_resp = content_stub.Read(
            content_pb2.ReadContentRequest(digest=digest), metadata=MD
        )
        data = b""
        for chunk in read_resp:
            data += chunk.data
        print(f"  Content length: {len(data)} bytes")
        # Try to parse as JSON (manifests/indexes are JSON)
        try:
            parsed = json.loads(data)
            print(f"  Content (JSON, pretty):")
            print(json.dumps(parsed, indent=2)[:2000])
        except json.JSONDecodeError:
            print(f"  Content (raw, first 500 bytes): {data[:500]}")
    except Exception as e:
        print(f"  Read error: {e}")

    # 3. If it's a manifest list/index, read one of its child manifests
    print()
    print("=" * 60)
    print("3. WALK ONE LEVEL DEEPER (if index/manifest list)")
    print("=" * 60)
    try:
        parsed = json.loads(data)
        manifests = parsed.get("manifests", [])
        if manifests:
            child = manifests[0]
            child_digest = child["digest"]
            print(f"  Child manifest digest: {child_digest}")
            print(f"  Child media_type: {child.get('mediaType')}")
            print(f"  Child platform: {child.get('platform')}")

            child_data = b""
            for chunk in content_stub.Read(
                content_pb2.ReadContentRequest(digest=child_digest), metadata=MD
            ):
                child_data += chunk.data
            child_parsed = json.loads(child_data)
            print(f"  Child content ({len(child_data)} bytes):")
            print(json.dumps(child_parsed, indent=2)[:2000])
        else:
            # It's already a manifest (not an index), show its layers
            layers = parsed.get("layers", [])
            config = parsed.get("config", {})
            print(f"  Config digest: {config.get('digest')}")
            print(f"  Layers ({len(layers)}):")
            for l in layers[:3]:
                print(f"    {l['digest']} ({l.get('size', '?')} bytes, {l.get('mediaType')})")
    except Exception as e:
        print(f"  Walk error: {e}")
