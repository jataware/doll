import os
from dataclasses import dataclass


@dataclass
class Config:
    docker_host: str | None
    containerd_socket: str
    containerd_namespace: str
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            docker_host=os.environ.get("DOCKER_HOST"),
            containerd_socket=os.environ.get(
                "CONTAINERD_SOCKET", "unix:///run/containerd/containerd.sock"
            ),
            containerd_namespace=os.environ.get("CONTAINERD_NAMESPACE", "moby"),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "5000")),
        )


config = Config.from_env()
