import os
from dataclasses import dataclass


@dataclass
class Config:
    docker_host: str | None
    containerd_socket: str
    containerd_namespace: str
    host: str
    port: int
    tls_cert: str | None
    tls_key: str | None
    registry: str
    filter_registry: bool

    @classmethod
    def from_env(cls) -> "Config":
        tls_cert = os.environ.get("DOLL_TLS_CERT")
        tls_key = os.environ.get("DOLL_TLS_KEY")

        # Only use TLS if both env vars are set and files exist
        if tls_cert and tls_key:
            if not os.path.isfile(tls_cert) or not os.path.isfile(tls_key):
                tls_cert = None
                tls_key = None

        return cls(
            docker_host=os.environ.get("DOCKER_HOST"),
            containerd_socket=os.environ.get(
                "CONTAINERD_SOCKET", "unix:///run/containerd/containerd.sock"
            ),
            containerd_namespace=os.environ.get("CONTAINERD_NAMESPACE", "moby"),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "5000")),
            tls_cert=tls_cert,
            tls_key=tls_key,
            registry=os.environ.get("DOLL_REGISTRY", "docker.io"),
            filter_registry=os.environ.get("DOLL_FILTER_REGISTRY", "").lower()
            in ("1", "true", "yes"),
        )

    @property
    def tls_enabled(self) -> bool:
        return self.tls_cert is not None and self.tls_key is not None


config = Config.from_env()
