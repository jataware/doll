import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from doll import docker_client, containerd_client
from doll.errors import (
    BLOB_UNKNOWN,
    MANIFEST_UNKNOWN,
    NAME_UNKNOWN,
    oci_error,
)

app = FastAPI(title="doll", docs_url=None, redoc_url=None)


@app.get("/v2/")
async def v2_base() -> JSONResponse:
    return JSONResponse(content={})


@app.get("/v2/_catalog")
async def catalog() -> JSONResponse:
    repos = docker_client.list_repositories()
    return JSONResponse(content={"repositories": sorted(repos.keys())})


@app.get("/v2/{name:path}/tags/list")
async def tags_list(name: str) -> JSONResponse:
    tags = docker_client.get_tags(name)
    if tags is None:
        return oci_error(NAME_UNKNOWN, f"repository name not known to registry: {name}", 404)
    return JSONResponse(content={"name": name, "tags": sorted(tags)})


@app.api_route("/v2/{name:path}/manifests/{reference}", methods=["GET", "HEAD"])
async def manifests(name: str, reference: str, request: Request) -> Response:
    target = containerd_client.get_image_target(name, reference)
    if target is None:
        return oci_error(MANIFEST_UNKNOWN, f"manifest unknown: {name}:{reference}", 404)

    digest, media_type, size = target

    # For digest references we don't get media_type from the images service,
    # so read the content and sniff it.
    if not media_type:
        data = containerd_client.read_content(digest)
        if data is None:
            return oci_error(MANIFEST_UNKNOWN, f"manifest unknown: {digest}", 404)
        try:
            parsed = json.loads(data)
            media_type = parsed.get("mediaType", "application/vnd.oci.image.manifest.v1+json")
        except (json.JSONDecodeError, KeyError):
            media_type = "application/vnd.oci.image.manifest.v1+json"

        headers = {
            "Content-Type": media_type,
            "Content-Length": str(len(data)),
            "Docker-Content-Digest": digest,
        }
        if request.method == "HEAD":
            return Response(status_code=200, headers=headers)
        return Response(content=data, media_type=media_type, headers=headers)

    # Tag reference — we have media_type from the image target
    headers = {
        "Content-Type": media_type,
        "Content-Length": str(size),
        "Docker-Content-Digest": digest,
    }
    if request.method == "HEAD":
        return Response(status_code=200, headers=headers)

    data = containerd_client.read_content(digest)
    if data is None:
        return oci_error(MANIFEST_UNKNOWN, f"manifest content not found: {digest}", 404)
    return Response(content=data, media_type=media_type, headers=headers)


@app.api_route("/v2/{name:path}/blobs/{digest}", methods=["GET", "HEAD"])
async def blobs(name: str, digest: str, request: Request) -> Response:
    info = containerd_client.get_content_info(digest)
    if info is None:
        return oci_error(BLOB_UNKNOWN, f"blob unknown to registry: {digest}", 404)

    content_digest, size = info
    headers = {
        "Content-Length": str(size),
        "Docker-Content-Digest": content_digest,
    }

    if request.method == "HEAD":
        return Response(status_code=200, headers=headers)

    chunks = containerd_client.stream_content(digest)
    if chunks is None:
        return oci_error(BLOB_UNKNOWN, f"blob not found: {digest}", 404)
    return StreamingResponse(
        content=chunks,
        media_type="application/octet-stream",
        headers=headers,
    )
