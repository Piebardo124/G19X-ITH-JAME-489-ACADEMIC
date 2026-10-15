from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db, SessionLocal
from app.db.models import FeedbackEntry, SentimentAnalysis, Alert, KeyPhrase, CSVImport
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.sanitization import sanitize_text
from app.services.ai_engine import analyze_sentiment_with_ai, generate_executive_summary
from typing import Optional
from app.core.security import verify_token
from app.services.email_service import send_alert_email
from app.db.models import Department
from datetime import date, datetime, time, timedelta, timezone
import uuid
import csv
import io
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_CSV_UPLOAD_BYTES = 5 * 1024 * 1024

@router.post("/analyze-feedback", response_model=FeedbackResponse)
def analyze_feedback(
    feedback: FeedbackCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),

):
    try:
        # Validacion existente del departamento
        if feedback.department_id is not None:
            depto_existe = db.query(Department).filter(Department.id == feedback.department_id).first()
            if not depto_existe:
                raise HTTPException(
                    status_code=400,
                    detail=f"El departamento con ID {feedback.department_id} no existe."
                )

        texto_limpio = sanitize_text(feedback.text_content)

        new_feedback = FeedbackEntry(
            id=uuid.uuid4(),
            content_text=texto_limpio,
            is_anonymous=feedback.is_anonymous,
            department_id=feedback.department_id
        )

        db.add(new_feedback)

        ai_results = analyze_sentiment_with_ai(texto_limpio)

        new_analysis = SentimentAnalysis(
            feedback_entry_id=new_feedback.id,
            polarity_score=ai_results["polarity_score"],
            sentiment_label=ai_results["sentiment_label"],
            metadata_ai=ai_results["metadata_ai"]
        )
        db.add(new_analysis)
        db.flush()

        if "key_phrases" in ai_results:
            for phrase in ai_results["key_phrases"]:
                nueva_frase = KeyPhrase(
                    analysis_id=new_analysis.id,
                    phrase=phrase
                )
                db.add(nueva_frase)


        # Crear una alerta cuando el análisis detecta un riesgo.
        is_risk = ai_results["metadata_ai"].get("risk_burnout", False)
        nueva_alerta = None

        if is_risk:
            nueva_alerta = Alert(
                feedback_id=new_feedback.id,
                risk_level="ALTO",
                reason=ai_results["metadata_ai"].get("red_flag_reason", "Riesgo detectado por IA")
            )
            db.add(nueva_alerta)

        db.commit()

        if is_risk and nueva_alerta:
            db.refresh(nueva_alerta)
            background_tasks.add_task(
                send_alert_email,
                alert_id=nueva_alerta.id,
                reason=nueva_alerta.reason
            )

        analisis_no_disponible = (
            ai_results["sentiment_label"] == "NO_DISPONIBLE"
            or ai_results["metadata_ai"].get("is_simulation", False)
        )
        mensaje = (
            "Comentario guardado, pero no fue analizado porque el motor de IA no está disponible."
            if analisis_no_disponible
            else "Comentario recibido y analizado correctamente."
        )

        return {
            "status": "success",
            "message": mensaje,
            "entry_id": new_feedback.id,
        }

    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        logger.error("Error al procesar el comentario (tipo=%s).", type(e).__name__)

        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor. Por favor verificar departamento seleccionado o contactar soporte."
        )

def process_csv_background(file_content: str, import_id: uuid.UUID):
    """Procesa el CSV y persiste un resumen consultable de la importación."""
    db = SessionLocal()
    totals = {"total_rows": 0, "processed_rows": 0, "skipped_rows": 0, "failed_rows": 0}
    errors = []
    try:
        job = db.query(CSVImport).filter(CSVImport.id == import_id).first()
        if not job:
            return
        job.status = "PROCESSING"
        db.commit()

        reader = csv.DictReader(io.StringIO(file_content))
        for index, row in enumerate(reader, start=1):
            totals["total_rows"] += 1
            try:
                texto = (row.get("text_content") or "").strip()
                if len(texto) < 5 or len(texto) > 3000:
                    totals["skipped_rows"] += 1
                    continue

                raw_anonymous = str(row.get("is_anonymous", "true")).strip().casefold()
                if raw_anonymous not in {"true", "1", "yes", "si", "sí"}:
                    raise ValueError("El MVP solo admite comentarios anónimos; is_anonymous debe ser true.")
                is_anon = True
                dep_id_raw = (row.get("department_id") or "").strip()
                if dep_id_raw and not dep_id_raw.isdigit():
                    raise ValueError("department_id debe ser un entero.")
                dep_id = int(dep_id_raw) if dep_id_raw else None
                if dep_id is not None and not db.query(Department).filter(Department.id == dep_id).first():
                    raise ValueError("department_id no existe.")

                texto_limpio = sanitize_text(texto)
                new_feedback = FeedbackEntry(
                    id=uuid.uuid4(),
                    content_text=texto_limpio,
                    is_anonymous=is_anon,
                    department_id=dep_id
                )
                db.add(new_feedback)

                ai_results = analyze_sentiment_with_ai(texto_limpio)
                new_analysis = SentimentAnalysis(
                    feedback_entry_id=new_feedback.id,
                    polarity_score=ai_results["polarity_score"],
                    sentiment_label=ai_results["sentiment_label"],
                    metadata_ai=ai_results["metadata_ai"]
                )
                db.add(new_analysis)
                db.flush()

                for phrase in ai_results.get("key_phrases", []):
                    db.add(KeyPhrase(analysis_id=new_analysis.id, phrase=phrase))

                if ai_results["metadata_ai"].get("risk_burnout", False):
                    alert = Alert(
                        feedback_id=new_feedback.id,
                        risk_level="ALTO",
                        reason=ai_results["metadata_ai"].get("red_flag_reason", "Riesgo detectado en carga masiva")
                    )
                    db.add(alert)

                db.commit()
                analysis_unavailable = (
                    ai_results["sentiment_label"] == "NO_DISPONIBLE"
                    or ai_results["metadata_ai"].get("is_simulation", False)
                )
                if analysis_unavailable:
                    totals["failed_rows"] += 1
                    if len(errors) < 10:
                        errors.append(f"Fila {index}: análisis de IA no disponible")
                else:
                    totals["processed_rows"] += 1
                if ai_results["metadata_ai"].get("risk_burnout", False):
                    db.refresh(alert)
                    send_alert_email(alert_id=alert.id, reason=alert.reason)
            except Exception as row_error:
                db.rollback()
                totals["failed_rows"] += 1
                if len(errors) < 10:
                    errors.append(f"Fila {index}: {type(row_error).__name__}")

        job = db.query(CSVImport).filter(CSVImport.id == import_id).first()
        if job:
            for key, value in totals.items():
                setattr(job, key, value)
            job.error_summary = "\n".join(errors) or None
            job.status = "COMPLETED_WITH_WARNINGS" if totals["skipped_rows"] or totals["failed_rows"] else "COMPLETED"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as error:
        db.rollback()
        job = db.query(CSVImport).filter(CSVImport.id == import_id).first()
        if job:
            job.status = "FAILED"
            job.error_summary = f"Error general: {type(error).__name__}"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()

@router.post("/upload-csv", status_code=status.HTTP_202_ACCEPTED)
async def upload_feeback_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token)
):
    """
    Endpoint protegido para subir archivos CSV historicos de clima laboral.
    """
    # Verificacion estricta de roles
    rol_usuario = current_user.get("role")
    if rol_usuario not in ["admin", "hr", "analyst"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo Recursos Humanos y Administradores pueden realizar cargas masivas."
        )

    # Validacion del formato del archivo
    filename = file.filename or ""
    if not filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="El archivo debe ser de tipo CSV.")

    try:
        content = await file.read(MAX_CSV_UPLOAD_BYTES + 1)
        if len(content) > MAX_CSV_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="El CSV excede el límite de 5 MB.")
        decoded_content = content.decode("utf-8-sig")

        headers = next(csv.reader(io.StringIO(decoded_content)), None)
        if not headers or "text_content" not in headers:
            raise HTTPException(status_code=400, detail="El CSV debe incluir la columna text_content.")

        import_job = CSVImport(filename=filename[:255], status="QUEUED")
        db.add(import_job)
        db.commit()
        db.refresh(import_job)

        background_tasks.add_task(process_csv_background, decoded_content, import_job.id)

        return {
            "status": "accepted",
            "import_id": str(import_job.id),
            "message": f"El archivo '{filename}' se está analizando en segundo plano."
        }

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="El archivo CSV debe estar codificado en UTF-8.")

@router.get("/upload-csv/{import_id}")
def get_csv_import_status(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token)
):
    rol_usuario = current_user.get("role")
    if rol_usuario not in ["admin", "hr", "analyst"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo Recursos Humanos y Administradores pueden consultar cargas masivas."
        )

    import_job = db.query(CSVImport).filter(CSVImport.id == import_id).first()
    if not import_job:
        raise HTTPException(status_code=404, detail="Carga CSV no encontrada.")

    return {
        "import_id": str(import_job.id),
        "filename": import_job.filename,
        "status": import_job.status,
        "total_rows": import_job.total_rows,
        "processed_rows": import_job.processed_rows,
        "skipped_rows": import_job.skipped_rows,
        "failed_rows": import_job.failed_rows,
        "errors": import_job.error_summary,
        "created_at": import_job.created_at,
        "finished_at": import_job.finished_at,
    }

@router.get("/summary")
def get_executive_summary(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token)
):
    """
    Genera un resumen ejecutivo mediante IA de los comentarios registrados.
    Permite filtrar por departamento
    """

    # Validacion de rol (Solo Directivos o RH)
    rol_usuario = current_user.get("role")
    if rol_usuario not in ["admin", "hr", "executive", "analyst"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Solo roles directivos o RH pueden generar resúmenes."
        )

    # Consulta los comentarios más recientes.
    query = db.query(FeedbackEntry)
    if department_id is not None:
        query = query.filter(FeedbackEntry.department_id == department_id)

    comentarios = query.filter(
        FeedbackEntry.content_text.isnot(None),
        func.length(func.trim(FeedbackEntry.content_text)) > 0,
    ).order_by(FeedbackEntry.created_at.desc()).limit(50).all()

    if not comentarios:
        return {
            "status": "success",
            "executive_summary": "No hay comentarios registrados para el periodo o departamento seleccionado.",
            "total_analyzed": 0
        }

    if len(comentarios) < 5:
        return {
            "status": "insufficient_data",
            "executive_summary": "Se requieren al menos 5 comentarios para generar un resumen agregado.",
            "total_analyzed": len(comentarios),
        }

    # Re-sanitizar protege también los registros históricos y limitar el lote
    # mantiene acotado el costo y el tiempo de la llamada al proveedor.
    textos_concatenados = "\n- ".join(
        sanitize_text(c.content_text) for c in comentarios
    )[:20000]

    # Llamado a Azure OpenAI
    resumen_ia = generate_executive_summary(textos_concatenados)

    return {
        "status": "success" if resumen_ia else "unavailable",
        "total_analyzed": len(comentarios),
        "executive_summary": resumen_ia or "No se pudo generar el resumen: el servicio de IA no está disponible.",
    }

@router.get("/analytics")
def get_dashboard_analytics(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token)
):

    if current_user.get("role") not in ["admin", "hr", "executive", "analyst"]:
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    query = db.query(SentimentAnalysis).join(
        FeedbackEntry, SentimentAnalysis.feedback_entry_id == FeedbackEntry.id
    )

    if department_id is not None:
        query = query.filter(FeedbackEntry.department_id == department_id)

    valid_query = query.filter(SentimentAnalysis.polarity_score.isnot(None))
    total_responses = valid_query.count()
    if 0 < total_responses < 5:
        raise HTTPException(
            status_code=403,
            detail="Volumen insuficiente. Se requieren al menos 5 respuestas para mostrar datos agregados."
        )

    if total_responses == 0:
        return {"total_responses": 0, "average_polarity": None, "distribution": {}}

    avg_polarity = valid_query.with_entities(func.avg(SentimentAnalysis.polarity_score)).scalar()

    distribucion = valid_query.with_entities(
        SentimentAnalysis.sentiment_label,
        func.count(SentimentAnalysis.id)
    ).group_by(SentimentAnalysis.sentiment_label).all()

    dist_dict = {label.capitalize() if label else "No_Disponible": count for label, count in distribucion}

    return {
        "total_responses": total_responses,
        "average_polarity": round(avg_polarity, 2) if avg_polarity is not None else None,
        "distribution": dist_dict
    }

@router.get("/stats")
def get_dashboard_stats(
    department_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token)
):
    """
    Devuelve métricas agregadas para el panel, sin exponer comentarios.
    """
    if current_user.get("role") not in ["admin", "hr", "executive", "analyst"]:
        raise HTTPException(status_code=403, detail="Acceso denegado.")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date no puede ser posterior a end_date.")

    query = db.query(
        SentimentAnalysis,
        FeedbackEntry.department_id,
        Department.name,
        FeedbackEntry.created_at,
    ).join(
        FeedbackEntry, SentimentAnalysis.feedback_entry_id == FeedbackEntry.id
    ).outerjoin(Department, FeedbackEntry.department_id == Department.id).filter(
        SentimentAnalysis.polarity_score.isnot(None)
    )

    if department_id is not None:
        query = query.filter(FeedbackEntry.department_id == department_id)
    if start_date:
        query = query.filter(
            FeedbackEntry.created_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )
    if end_date:
        query = query.filter(
            FeedbackEntry.created_at < datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    rows = query.all()
    total_responses = len(rows)
    filters = {
        "department_id": department_id,
        "start_date": start_date,
        "end_date": end_date,
        "minimum_sample": 5,
    }
    if total_responses < 5:
        return {
            "status": "insufficient_data",
            "total_responses": 0 if total_responses == 0 else None,
            "filters": filters,
            "distribution": {},
            "average_polarity": None,
            "department_averages": [],
            "emotions": [],
            "organizational_axes": [],
            "key_phrases": [],
            "daily_trend": [],
        }

    label_counts = {}
    department_totals = {}
    emotion_counts = {}
    axis_counts = {}
    daily_totals = {}
    polarity_sum = 0.0

    for analysis, row_department_id, department_name, created_at in rows:
        polarity_sum += analysis.polarity_score
        label = analysis.sentiment_label or "Sin clasificar"
        label_counts[label] = label_counts.get(label, 0) + 1

        if row_department_id is not None:
            item = department_totals.setdefault(
                row_department_id,
                {"department_id": row_department_id, "department": department_name or "Sin nombre", "count": 0, "sum": 0.0},
            )
            item["count"] += 1
            item["sum"] += analysis.polarity_score

        day = created_at.date().isoformat() if created_at else "Sin fecha"
        day_item = daily_totals.setdefault(day, {"count": 0, "sum": 0.0})
        day_item["count"] += 1
        day_item["sum"] += analysis.polarity_score

        metadata = analysis.metadata_ai or {}
        for emotion in set(metadata.get("emotions") or []):
            if isinstance(emotion, str) and emotion.strip():
                emotion_counts[emotion.strip()] = emotion_counts.get(emotion.strip(), 0) + 1
        for axis in set(metadata.get("organizational_axes") or []):
            if isinstance(axis, str) and axis.strip():
                axis_counts[axis.strip()] = axis_counts.get(axis.strip(), 0) + 1

    def ranked_items(counter, minimum_count=2):
        return [
            {"name": name, "count": count}
            for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0].casefold()))
            if count >= minimum_count
        ][:10]

    phrase_query = db.query(
        func.lower(func.trim(KeyPhrase.phrase)).label("phrase"),
        func.count(func.distinct(SentimentAnalysis.id)).label("frequency"),
    ).join(
        SentimentAnalysis, KeyPhrase.analysis_id == SentimentAnalysis.id
    ).join(
        FeedbackEntry, SentimentAnalysis.feedback_entry_id == FeedbackEntry.id
    ).filter(
        SentimentAnalysis.polarity_score.isnot(None),
        func.length(func.trim(KeyPhrase.phrase)) > 0,
    )
    if department_id is not None:
        phrase_query = phrase_query.filter(FeedbackEntry.department_id == department_id)
    if start_date:
        phrase_query = phrase_query.filter(
            FeedbackEntry.created_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )
    if end_date:
        phrase_query = phrase_query.filter(
            FeedbackEntry.created_at < datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )
    phrase_key = func.lower(func.trim(KeyPhrase.phrase))
    phrases = phrase_query.group_by(phrase_key).having(
        func.count(func.distinct(SentimentAnalysis.id)) >= 2
    ).order_by(func.count(func.distinct(SentimentAnalysis.id)).desc(), phrase_key).limit(10).all()

    return {
        "status": "success",
        "total_responses": total_responses,
        "filters": filters,
        "distribution": label_counts,
        "average_polarity": round(polarity_sum / total_responses, 2),
        "department_averages": [
            {
                "department_id": item["department_id"],
                "department": item["department"],
                "total_responses": item["count"],
                "average_polarity": round(item["sum"] / item["count"], 2),
            }
            for item in sorted(department_totals.values(), key=lambda value: value["department"].casefold())
            if item["count"] >= 5
        ],
        "emotions": ranked_items(emotion_counts),
        "organizational_axes": ranked_items(axis_counts),
        "key_phrases": [
            {"name": phrase, "count": frequency} for phrase, frequency in phrases
        ],
        "daily_trend": [
            {"date": day, "total_responses": item["count"], "average_polarity": round(item["sum"] / item["count"], 2)}
            for day, item in sorted(daily_totals.items())[-30:]
            if item["count"] >= 5
        ],
    }

@router.get("/departments")
def get_departments(db: Session = Depends(get_db)):
    """
    Devuelve el catalogo de departamentos para llenar el select en frontend.
    """
    departamentos = db.query(Department).all()
    return departamentos
