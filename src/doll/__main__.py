import os

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import uvicorn

from doll.config import config
from doll.containerd_client import check_containerd
from doll.server import app

if __name__ == "__main__":
    check_containerd()

    kwargs: dict = {"host": config.host, "port": config.port}
    if config.tls_enabled:
        kwargs["ssl_certfile"] = config.tls_cert
        kwargs["ssl_keyfile"] = config.tls_key
        kwargs["port"] = 443

    uvicorn.run(app, **kwargs)
