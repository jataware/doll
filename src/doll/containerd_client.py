import sys
from collections.abc import Iterator

import grpc
from containerd.services.images.v1 import images_pb2, images_pb2_grpc
from containerd.services.content.v1 import content_pb2, content_pb2_grpc
from containerd.services.namespaces.v1 import namespace_pb2, namespace_pb2_grpc

from doll.config import config


def _channel() -> grpc.Channel:
    return grpc.insecure_channel(config.containerd_socket)


def _metadata() -> list[tuple[str, str]]:
    return [("containerd-namespace", config.containerd_namespace)]


def _images_stub() -> images_pb2_grpc.ImagesStub:
    return images_pb2_grpc.ImagesStub(_channel())


def _content_stub() -> content_pb2_grpc.ContentStub:
    return content_pb2_grpc.ContentStub(_channel())


def check_containerd() -> None:
    """Verify that containerd is reachable and the configured namespace exists.

    Prints an error and exits if the check fails.
    """
    ns = config.containerd_namespace
    try:
        channel = _channel()
        stub = namespace_pb2_grpc.NamespacesStub(channel)
        stub.Get(namespace_pb2.GetNamespaceRequest(name=ns))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            print(
                f"Error: containerd namespace '{ns}' does not exist.\n"
                f"Docker may not be configured to use the containerd image store.\n"
                f"See: https://docs.docker.com/storage/containerd/",
                file=sys.stderr,
            )
        elif e.code() == grpc.StatusCode.UNAVAILABLE:
            print(
                f"Error: cannot connect to containerd at {config.containerd_socket}\n"
                f"Ensure containerd is running and the socket is accessible.",
                file=sys.stderr,
            )
        else:
            print(
                f"Error: unexpected containerd error: {e.details()}",
                file=sys.stderr,
            )
        sys.exit(1)


def _qualify_name(name: str, tag: str) -> str:
    """Convert a registry-style name + tag into a containerd fully-qualified name.

    OCI requests come in as e.g. "library/ubuntu" or "beakerhub/server",
    but containerd stores them as "docker.io/library/ubuntu:tag" or
    "docker.io/beakerhub/server:tag".

    The registry prefix is configurable via DOLL_REGISTRY (default: docker.io).
    """
    return f"{config.registry}/{name}:{tag}"


def get_image_target(name: str, reference: str) -> tuple[str, str, int] | None:
    """Resolve a repo name + tag/digest reference to (digest, media_type, size).

    If reference looks like a digest (starts with "sha256:"), returns it directly
    with info from the content store. Otherwise treats it as a tag and looks up
    the image by its fully-qualified containerd name.

    Returns None if the image/content is not found.
    """
    if reference.startswith("sha256:"):
        # Digest reference — go straight to the content store for info
        try:
            info = _content_stub().Info(
                content_pb2.InfoRequest(digest=reference),
                metadata=_metadata(),
            )
            # We don't know the media type from Info alone; the caller will
            # need to parse the content to determine it. Return empty string.
            return (info.info.digest, "", info.info.size)
        except grpc.RpcError:
            return None

    # Tag reference — look up via the images service
    fqn = _qualify_name(name, reference)
    try:
        resp = _images_stub().Get(
            images_pb2.GetImageRequest(name=fqn),
            metadata=_metadata(),
        )
        target = resp.image.target
        return (target.digest, target.media_type, target.size)
    except grpc.RpcError:
        return None


def stream_content(digest: str) -> Iterator[bytes] | None:
    """Stream content for a given digest from the content store, yielding chunks."""
    try:
        stream = _content_stub().Read(
            content_pb2.ReadContentRequest(digest=digest),
            metadata=_metadata(),
        )
        # Consume the first chunk to verify the stream is valid before
        # returning the generator (so callers get None on error, not a
        # generator that immediately raises).
        first = next(stream, None)
        if first is None:
            return None

        def _generate() -> Iterator[bytes]:
            yield first.data
            for chunk in stream:
                yield chunk.data

        return _generate()
    except grpc.RpcError:
        return None


def read_content(digest: str) -> bytes | None:
    """Read the full content for a given digest from the content store."""
    chunks = stream_content(digest)
    if chunks is None:
        return None
    return b"".join(chunks)


def get_content_info(digest: str) -> tuple[str, int] | None:
    """Get (digest, size) for a content object. Returns None if not found."""
    try:
        resp = _content_stub().Info(
            content_pb2.InfoRequest(digest=digest),
            metadata=_metadata(),
        )
        return (resp.info.digest, resp.info.size)
    except grpc.RpcError:
        return None
