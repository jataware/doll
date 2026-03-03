import os

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import uvicorn

from doll.config import config
from doll.containerd_client import check_containerd
from doll.server import app

if __name__ == "__main__":
    check_containerd()
    uvicorn.run(app, host=config.host, port=config.port)
