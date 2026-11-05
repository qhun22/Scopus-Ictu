"""Small request guards applied to every route.

PostgreSQL text cannot hold a NUL (0x00) character: psycopg2 raises while adapting such a string
and the request used to end as an unhandled 500 (search boxes, path parameters, even the public
login form). The URL is checked once, here, and answered with a clear 422 in the project's flat
error envelope.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

INVALID_CHARACTER_CODE = "INVALID_CHARACTER"
INVALID_CHARACTER_DETAIL = "Đường dẫn hoặc tham số truy vấn chứa ký tự không hợp lệ."


def url_contains_nul(request: Request) -> bool:
    """True when the raw or decoded query string / path carries a NUL character."""

    scope = request.scope
    raw_query = scope.get("query_string", b"") or b""
    raw_path = scope.get("raw_path", b"") or b""
    path = scope.get("path", "") or ""
    return (
        b"%00" in raw_query.lower()
        or b"\x00" in raw_query
        or b"%00" in raw_path.lower()
        or b"\x00" in raw_path
        or "\x00" in path
    )


async def reject_nul_in_url(request: Request, call_next):
    """HTTP middleware: stop a NUL in the URL before it can reach the database."""

    if url_contains_nul(request):
        return JSONResponse(
            status_code=422,
            content={"detail": INVALID_CHARACTER_DETAIL, "code": INVALID_CHARACTER_CODE},
        )
    return await call_next(request)
