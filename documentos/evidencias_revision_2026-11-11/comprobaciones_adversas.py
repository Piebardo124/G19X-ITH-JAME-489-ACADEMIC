"""Comprobaciones locales sobre la base QA; Azure y SMTP deshabilitados."""
import calendar
import io
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
qa_name = os.environ.get("QA_DATABASE", "")
original = make_url(os.environ["DATABASE_URL"])
assert re.fullmatch(r"plurione_qa_[a-z0-9_]+", qa_name) and qa_name != original.database
original_engine = create_engine(original)
def original_counts():
    with original_engine.connect() as connection:
        return dict(zip(("users", "feedback", "alerts"), connection.execute(text(
            "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM feedback_entries), (SELECT count(*) FROM alerts)"
        )).one()))
before = original_counts()
os.environ["DATABASE_URL"] = original.set(database=qa_name).render_as_string(hide_password=False)
os.environ["AZURE_OPENAI_API_KEY"] = ""
os.environ["SMTP_EMAIL"] = ""
os.environ["SMTP_PASSWORD"] = ""
from fastapi.testclient import TestClient
from app.main import app
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.database import SessionLocal
from app.db.models import Department, FeedbackEntry, SentimentAnalysis
from app.api.v1.endpoints import feedback
from app.services.sanitization import sanitize_text

result = {"qa_database": qa_name, "azure_requests": 0, "smtp_delivery": "disabled"}
result["unicode_phone"] = sanitize_text("Mi telefono es 662\u200b123\u200b4567.")
result["ordinary_expression"] = sanitize_text("The new schedule gives me a healthier balance between work and home")
result["job_title_name"] = sanitize_text("Mi jefa Ana López me humilla en las juntas.")
with TestClient(app, raise_server_exceptions=False) as client:
    headers = {"Authorization": "Bearer " + create_access_token({"sub": "qa-admin@example.test"})}
    limiter.reset()
    response = client.post("/api/v1/nlp/analyze-feedback", json={"text_content": "Comentario QA con byte nulo \x00 al final", "department_id": 1})
    result["nul_feedback"] = {"http_status": response.status_code, "body": response.json()}
    captured = io.StringIO()
    handler = logging.StreamHandler(captured)
    feedback.logger.addHandler(handler)
    limiter.reset()
    response = client.post("/api/v1/nlp/upload-csv", headers=headers, files={"file": ("qa_nul.csv", b"text_content\nComentario QA NUL\x00 de prueba\n", "text/csv")})
    job = client.get("/api/v1/nlp/upload-csv/" + response.json()["import_id"], headers=headers).json()
    feedback.logger.removeHandler(handler)
    result["nul_csv"] = {"status": job["status"], "failed_rows": job["failed_rows"], "sql_parameters_in_server_log": "[parameters:" in captured.getvalue()}
    with SessionLocal() as db:
        result["database_role"] = dict(db.execute(text("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user")).mappings().one())
        department = Department(name="QA privacidad temporal " + uuid.uuid4().hex[:8])
        db.add(department)
        db.flush()
        department_id = department.id
        for _ in range(5):
            entry = FeedbackEntry(content_text="Comentario sintético QA", department_id=department_id)
            db.add(entry)
            db.flush()
            db.add(SentimentAnalysis(feedback_entry_id=entry.id, polarity_score=0.0, sentiment_label="Neutral", metadata_ai={}))
        db.commit()
    now = datetime.now(timezone.utc)
    params = {"department_id": department_id, "start_date": f"{now:%Y-%m}-01", "end_date": f"{now:%Y-%m}-{calendar.monthrange(now.year, now.month)[1]}"}
    first = client.get("/api/v1/nlp/stats", params=params, headers=headers).json()
    with SessionLocal() as db:
        entry = FeedbackEntry(content_text="Otro comentario sintético QA", department_id=department_id)
        db.add(entry)
        db.flush()
        db.add(SentimentAnalysis(feedback_entry_id=entry.id, polarity_score=0.9, sentiment_label="Positivo", metadata_ai={}))
        db.commit()
    second = client.get("/api/v1/nlp/stats", params=params, headers=headers).json()
    result["temporal_differencing"] = {"before_total": first["total_responses"], "before_average": first["average_polarity"], "after_total": second["total_responses"], "after_average": second["average_polarity"], "inferred_added_score": round(second["average_polarity"]*second["total_responses"]-first["average_polarity"]*first["total_responses"], 4)}
    limiter.reset()
    result["sql_injection_login_status"] = client.post("/api/v1/auth/login", data={"username": "' OR 1=1 --@example.test", "password": "incorrecta"}).status_code
    result["unauthorized_csv_status"] = client.post("/api/v1/nlp/upload-csv", files={"file": ("qa.csv", b"text_content\n", "text/csv")}).status_code
    result["malformed_multipart_before_auth_status"] = client.post("/api/v1/nlp/upload-csv", content=b"not-a-multipart", headers={"Content-Type": "multipart/form-data; boundary=qa"}).status_code
    root = client.get("/")
    result["response_security_headers"] = {name: root.headers.get(name) for name in ("content-security-policy", "x-content-type-options", "strict-transport-security")}
    limiter.reset()
result["original_counts_before"] = before
result["original_counts_after"] = original_counts()
result["original_counts_unchanged"] = result["original_counts_before"] == result["original_counts_after"]
print(json.dumps(result, ensure_ascii=False, indent=2))
