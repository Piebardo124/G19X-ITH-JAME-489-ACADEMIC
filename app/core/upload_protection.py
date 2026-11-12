"""Protege la carga CSV antes de que FastAPI analice el cuerpo multipart."""
from fastapi import HTTPException
from fastapi.security.utils import get_authorization_scheme_param
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.security import require_roles, verify_token
from app.db.database import SessionLocal

MAX_CSV_UPLOAD_BYTES = 5 * 1024 * 1024
# El límite de archivo se aplica también en el endpoint. Este margen admite
# cabeceras y delimitadores multipart sin aceptar cuerpos sin límite.
MAX_CSV_REQUEST_BYTES = MAX_CSV_UPLOAD_BYTES + 64 * 1024
CSV_UPLOAD_PATH = "/api/v1/nlp/upload-csv"


def verify_csv_upload_access(token: str):
    """Comprueba la identidad y el rol actuales sin leer el cuerpo de la carga."""
    with SessionLocal() as db:
        current_user = verify_token(token=token, db=db)
        return require_roles("admin", "hr", "analyst")(current_user=current_user)


class CSVUploadProtectionMiddleware:
    def __init__(self, app: ASGIApp, max_request_bytes: int = MAX_CSV_REQUEST_BYTES):
        self.app = app
        self.max_request_bytes = max_request_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != CSV_UPLOAD_PATH
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        scheme, token = get_authorization_scheme_param(headers.get("authorization"))
        try:
            if scheme.lower() != "bearer" or not token:
                raise HTTPException(
                    status_code=401,
                    detail="No autenticado",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # La sesión pertenece a esta operación síncrona y se cierra en el
            # mismo thread. El endpoint mantiene sus dependencias de seguridad.
            await run_in_threadpool(verify_csv_upload_access, token)
        except HTTPException as error:
            await JSONResponse(
                status_code=error.status_code,
                content={"detail": error.detail},
                headers=error.headers,
            )(scope, receive, send)
            return

        async def reject_oversize():
            await JSONResponse(
                status_code=413,
                content={"detail": "La solicitud excede el límite de carga. El CSV admite hasta 5 MB."},
            )(scope, receive, send)

        content_length = headers.get("content-length", "")
        if content_length.isdecimal():
            declared_length = content_length.lstrip("0") or "0"
            if (
                len(declared_length) > len(str(self.max_request_bytes))
                or int(declared_length) > self.max_request_bytes
            ):
                await reject_oversize()
                return

        # Contar los bytes reales protege también transferencias sin
        # Content-Length o con una longitud declarada inferior a la recibida.
        # El parser no crea archivos temporales hasta validar todo este cuerpo.
        chunks = []
        received_bytes = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            received_bytes += len(chunk)
            if received_bytes > self.max_request_bytes:
                await reject_oversize()
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        buffered_body = b"".join(chunks)
        chunks.clear()
        body_sent = False

        async def receive_buffered():
            nonlocal buffered_body, body_sent
            if not body_sent:
                body_sent = True
                message = {"type": "http.request", "body": buffered_body, "more_body": False}
                buffered_body = b""
                return message
            return await receive()

        await self.app(scope, receive_buffered, send)
