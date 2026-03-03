from typing import Any

from fastapi.responses import JSONResponse


# OCI Distribution Spec error codes
NAME_UNKNOWN = "NAME_UNKNOWN"
MANIFEST_UNKNOWN = "MANIFEST_UNKNOWN"
BLOB_UNKNOWN = "BLOB_UNKNOWN"
UNSUPPORTED = "UNSUPPORTED"


def oci_error(
    code: str,
    message: str,
    status_code: int,
    detail: Any = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        error["detail"] = detail
    return JSONResponse(
        status_code=status_code,
        content={"errors": [error]},
    )
