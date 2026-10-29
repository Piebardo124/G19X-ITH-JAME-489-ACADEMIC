"""Pruebas integradas en una base temporal; nunca usa las tablas de la base original.

Ejecutar dentro de Compose con QA_DATABASE=plurione_qa_<identificador>.
Modos: api (crea y prueba), serve (UI en puerto 8000), cleanup (borra solo QA).
"""
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

name = os.environ.get("QA_DATABASE", "")
if not re.fullmatch(r"plurione_qa_[a-z0-9_]+", name):
    raise SystemExit("QA_DATABASE debe identificar explícitamente una base temporal plurione_qa_.")
original = make_url(os.environ["DATABASE_URL"])
if name == original.database:
    raise SystemExit("La base QA debe ser diferente de la original.")
mode = sys.argv[1] if len(sys.argv) > 1 else "api"
if mode in {"api", "cleanup"}:
    maintenance = create_engine(original, isolation_level="AUTOCOMMIT")
    with maintenance.connect() as connection:
        if mode == "api":
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        else:
            connection.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()"), {"name": name})
            connection.execute(text(f'DROP DATABASE "{name}"'))
    maintenance.dispose()
    if mode == "cleanup":
        print("Base temporal eliminada; base original conservada.")
        raise SystemExit()

os.environ["DATABASE_URL"] = original.set(database=name).render_as_string(hide_password=False)
os.environ["SMTP_EMAIL"] = ""
os.environ["SMTP_PASSWORD"] = ""
os.environ["SMTP_ALERT_RECIPIENT"] = ""
sys.path.insert(0, "/workspace")
from app.main import app
from app.db.database import SessionLocal
from app.db.models import User, FeedbackEntry, SentimentAnalysis, Alert
from app.api.v1.endpoints import feedback
from app.core.rate_limit import limiter
from app.core.security import SECRET_KEY

if mode == "serve":
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:15173"], allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"], expose_headers=["X-Has-More"])
    uvicorn.run(app, host="0.0.0.0", port=8000)
    raise SystemExit()

import jwt
from fastapi.testclient import TestClient
from app.create_user_cli import create_user
from app.create_admin_cli import init_admin

PASSWORD = "QaTemporal-2026-Only!"  # Solo cuentas desechables de esta base QA.
passed = failed = 0
def check(label, value):
    global passed, failed
    if value:
        passed += 1
        print("PASS", label, flush=True)
    else:
        failed += 1
        print("FAIL", label, flush=True)

def request(client, method, path, **kwargs):
    return getattr(client, method)("/api/v1" + path, **kwargs)

with TestClient(app, raise_server_exceptions=False) as client:
    with patch("builtins.input", return_value="qa-admin@example.test"), patch("getpass.getpass", return_value=PASSWORD):
        check("CLI administrador inicial", init_admin())
        check("CLI rechaza segundo administrador", init_admin() is False)
    for role in ["hr", "analyst", "executive"]:
        check("CLI crea " + role, create_user("qa-" + role + "@example.test", role, PASSWORD))
    for label, values in [
        ("rol admin no permitido", ("otra@example.test", "admin", PASSWORD)),
        ("correo inválido", ("no-es-correo", "hr", PASSWORD)),
        ("contraseña corta", ("otra@example.test", "hr", "corta")),
        ("bcrypt más de 72 bytes", ("otra@example.test", "hr", "a" * 73)),
        ("correo duplicado normalizado", (" QA-HR@EXAMPLE.TEST ", "hr", PASSWORD)),
    ]:
        check("CLI rechaza " + label, create_user(*values) is False)
    with SessionLocal() as db:
        check("contraseñas persistidas con hash", all(u.hashed_password.startswith("$2") and u.hashed_password != PASSWORD for u in db.query(User).all()))
    tokens = {}
    for role in ["admin", "hr", "analyst", "executive"]:
        limiter.reset()
        r = request(client, "post", "/auth/login", data={"username": " QA-" + role.upper() + "@EXAMPLE.TEST ", "password": PASSWORD})
        check("login normalizado " + role, r.status_code == 200 and r.json().get("role") == role)
        if r.status_code == 200:
            tokens[role] = {"Authorization": "Bearer " + r.json()["access_token"]}
    limiter.reset()
    check("login contraseña incorrecta 401", request(client, "post", "/auth/login", data={"username": "qa-hr@example.test", "password": "incorrecta"}).status_code == 401)
    check("JWT ausente 401", request(client, "get", "/alerts/").status_code == 401)
    check("JWT inválido 401", request(client, "get", "/alerts/", headers={"Authorization": "Bearer falso"}).status_code == 401)
    expired = jwt.encode({"sub": "qa-admin@example.test", "exp": datetime.now(timezone.utc)-timedelta(seconds=1)}, SECRET_KEY, algorithm="HS256")
    check("JWT expirado 401", request(client, "get", "/alerts/", headers={"Authorization": "Bearer " + expired}).status_code == 401)
    spoofed = jwt.encode({"sub": "qa-executive@example.test", "role": "admin", "exp": datetime.now(timezone.utc)+timedelta(minutes=1)}, SECRET_KEY, algorithm="HS256")
    check("rol real de BD prevalece sobre claim JWT", request(client, "get", "/alerts/", headers={"Authorization": "Bearer " + spoofed}).status_code == 403)
    now = datetime.now(timezone.utc)
    import calendar
    params = {"department_id": 1, "start_date": f"{now:%Y-%m}-01", "end_date": f"{now:%Y-%m}-{calendar.monthrange(now.year, now.month)[1]}"}
    for role, headers in tokens.items():
        limiter.reset()
        check("métricas permitidas " + role, request(client, "get", "/nlp/stats", headers=headers, params=params).status_code == 200)
        check("alertas permiso " + role, request(client, "get", "/alerts/", headers=headers).status_code == (403 if role == "executive" else 200))
        r = request(client, "post", "/nlp/upload-csv", headers=headers, files={"file": ("empty.csv", b"text_content\n", "text/csv")})
        check("CSV permiso " + role, r.status_code == (403 if role == "executive" else 202))
    headers = tokens["admin"]
    limiter.reset()
    for label, body, expected in [
        ("texto corto", {"text_content": "hola"}, 422),
        ("texto largo", {"text_content": "a"*3001}, 422),
        ("solo dígitos", {"text_content": "123456"}, 422),
        ("no anónimo", {"text_content": "Comentario de prueba", "is_anonymous": False}, 422),
        ("departamento inexistente", {"text_content": "Comentario de prueba", "department_id": 9999}, 400),
    ]:
        limiter.reset()
        check("validación " + label, request(client, "post", "/nlp/analyze-feedback", json=body).status_code == expected)
    sent = []
    with patch.object(feedback, "send_alert_email", side_effect=lambda **kw: sent.append(kw) or True):
        for index in range(6):
            limiter.reset()
            message = "El equipo colabora muy bien y me siento satisfecho con el ambiente laboral."
            if index == 5:
                message = "PRUEBA SINTÉTICA: La carga laboral excesiva me tiene agotado y quiero renunciar. Contacto qa.persona@example.test y teléfono 6621234567."
            started = time.perf_counter()
            r = request(client, "post", "/nlp/analyze-feedback", json={"text_content": message, "department_id": 1})
            check(f"buzón con Azure caso {index+1} HTTP 200", r.status_code == 200)
            if r.status_code == 200:
                with SessionLocal() as db:
                    entry = db.get(FeedbackEntry, uuid.UUID(r.json()["entry_id"]))
                    analysis = db.query(SentimentAnalysis).filter_by(feedback_entry_id=entry.id).one()
                    check(f"Azure real disponible caso {index+1}", analysis.polarity_score is not None)
                    if index == 5:
                        check("PII no persistida", "qa.persona@" not in entry.content_text and "6621234567" not in entry.content_text)
            print(f"LATENCIA caso {index+1}: {time.perf_counter()-started:.3f}s", flush=True)
        limiter.reset()
        csv_body = "text_content,is_anonymous,department_id\nEl equipo colabora y tiene buena comunicación,true,2\nLa carga de trabajo me provoca agotamiento y deseo renunciar,true,2\nx,true,2\nComentario inválido,true,99999\n".encode()
        r = request(client, "post", "/nlp/upload-csv", headers=headers, files={"file": ("qa.csv", csv_body, "text/csv")})
        check("CSV aceptación 202", r.status_code == 202)
        if r.status_code == 202:
            status = request(client, "get", "/nlp/upload-csv/" + r.json()["import_id"], headers=headers).json()
            check("CSV resumen correcto 2/1/1", status.get("processed_rows") == 2 and status.get("skipped_rows") == 1 and status.get("failed_rows") == 1)
            check("CSV advertencias visibles", status.get("status") == "COMPLETED_WITH_WARNINGS")
    check("alerta real generada y correo interceptado", len(sent) >= 1)
    r = request(client, "get", "/nlp/stats", headers=headers, params=params)
    check("métricas con muestra mínima", r.status_code == 200 and r.json().get("status") == "success")
    check("métricas sin texto de comentarios", "content_text" not in r.text)
    small = dict(params, department_id=2)
    r = request(client, "get", "/nlp/stats", headers=headers, params=small)
    check("privacidad menos de cinco respuestas", r.json().get("status") == "insufficient_data" and r.json().get("average_polarity") is None)
    partial = dict(params, start_date=f"{now:%Y-%m}-02")
    check("métricas rechazan mes parcial", request(client, "get", "/nlp/stats", headers=headers, params=partial).status_code == 400)
    alerts = request(client, "get", "/alerts/", headers=headers).json()
    if alerts:
        aid = alerts[0]["id"]
        for state in ["IN_PROGRESS", "CLOSED", "FALSE_POSITIVE", "OPEN"]:
            r = request(client, "patch", f"/alerts/{aid}", headers=headers, json={"status": state})
            check("cambio de alerta " + state, r.status_code == 200 and r.json().get("status") == state)
        check("estado de alerta inválido 400", request(client, "patch", f"/alerts/{aid}", headers=headers, json={"status": "INVALID"}).status_code == 400)
        check("executive no modifica alerta", request(client, "patch", f"/alerts/{aid}", headers=tokens["executive"], json={"status": "CLOSED"}).status_code == 403)
    check("alertas page_size inválido 422", request(client, "get", "/alerts/?page_size=101", headers=headers).status_code == 422)
    check("alertas fechas invertidas 400", request(client, "get", "/alerts/?date_from=2026-10-10&date_to=2026-10-01", headers=headers).status_code == 400)
    for label, filename, content, expected in [
        ("extensión", "file.txt", b"text_content\n", 400),
        ("cabecera", "file.csv", b"otra\n", 400),
        ("UTF8", "file.csv", b"text_content\n\xff", 400),
        ("más de 5MB", "file.csv", b"x"*(5*1024*1024+1), 413),
    ]:
        limiter.reset()
        check("CSV valida " + label, request(client, "post", "/nlp/upload-csv", headers=headers, files={"file": (filename, content, "text/csv")}).status_code == expected)
    limiter.reset()
    r = request(client, "post", "/nlp/upload-csv", headers=headers, files={"file": ("many.csv", b"text_content\n"+b"x\n"*1001, "text/csv")})
    result = request(client, "get", "/nlp/upload-csv/"+r.json()["import_id"], headers=headers).json()
    check("CSV límite de 1000 filas", result.get("total_rows") == 1000 and result.get("status") == "COMPLETED_WITH_WARNINGS")
    limiter.reset()
    for i in range(6):
        r = request(client, "post", "/auth/login", data={"username": "unknown@example.test", "password": "incorrect"})
    check("login 429 con detail español", r.status_code == 429 and "detail" in r.json())
    limiter.reset()
    with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": ""}):
        for i in range(6):
            r = request(client, "post", "/nlp/analyze-feedback", json={"text_content": "Comentario sintético para prueba de límite", "department_id": 5})
            if i == 0:
                check("fallback IA guarda y avisa", r.status_code == 200 and "no fue analizado" in r.json().get("message", ""))
    check("buzón 429 con detail español", r.status_code == 429 and "detail" in r.json())
    for origin in ["http://localhost:5173", "https://evil.example.test"]:
        r = client.options("/api/v1/alerts/", headers={"Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
        check("CORS " + origin, (r.headers.get("access-control-allow-origin") == origin) == origin.endswith(":5173"))
    limiter.reset()
print(f"RESULTADO: {passed} PASS, {failed} FAIL", flush=True)
raise SystemExit(1 if failed else 0)
