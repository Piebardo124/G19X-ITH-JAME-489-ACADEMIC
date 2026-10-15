from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal
from app.db.models import FeedbackEntry, SentimentAnalysis, Alert, KeyPhrase, CSVImport
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.sanitization import sanitize_text
from app.services.ai_engine import analyze_sentiment_with_ai, generate_executive_summary
from typing import Optional
from app.core.security import verify_token
from app.services.email_service import send_alert_email
from app.db.models import Department
import uuid
import csv
import io
from datetime import datetime, timezone

router = APIRouter()
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
        alerta_id = None
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
            alerta_id = nueva_alerta.id
            background_tasks.add_task(
                send_alert_email,
                alert_id=alerta_id,
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
            "alert_generated_id": alerta_id,
            "ai_analysis": {
                "label": ai_results["sentiment_label"],
                "polarity": ai_results["polarity_score"],
                "key_phrases": ai_results.get("key_phrases", []),
                "details": ai_results["metadata_ai"]
            }
        }

    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        print(f"Error al procesar el comentario: {e}")

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
                texto = row.get("text_content")
                if not texto or len(texto) < 5 or len(texto) > 3000:
                    totals["skipped_rows"] += 1
                    continue

                is_anon = str(row.get("is_anonymous", "True")).strip().lower() == "true"
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
                    db.add(Alert(
                        feedback_id=new_feedback.id,
                        risk_level="ALTO",
                        reason=ai_results["metadata_ai"].get("red_flag_reason", "Riesgo detectado en carga masiva")
                    ))

                db.commit()
                totals["processed_rows"] += 1
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

@router.post("/upload-csv")
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
    if rol_usuario not in ["admin", "hr"]:
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
    if rol_usuario not in ["admin", "hr"]:
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
    if rol_usuario not in ["admin", "hr", "executive"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Solo roles directivos o RH pueden generar resúmenes."
        )

    # Consulta los comentarios más recientes.
    query = db.query(FeedbackEntry)
    if department_id:
        query = query.filter(FeedbackEntry.department_id == department_id)

    comentarios = query.order_by(FeedbackEntry.created_at.desc()).limit(50).all()

    if not comentarios:
        return {
            "status": "success",
            "executive_summary": "No hay comentarios registrados para el periodo o departamento seleccionado.",
            "total_analyzed": 0
        }

    # Concatenado de todos los textos en un bloque con viñetas
    textos_concatenados = "\n- ".join([c.content_text for c in comentarios if c.content_text])

    # Llamado a Azure OpenAI
    resumen_ia = generate_executive_summary(textos_concatenados)

    return {
        "status": "success",
        "total_analyzed": len(comentarios),
        "executive_summary": resumen_ia
    }

@router.get("/departments")
def get_departments(db: Session = Depends(get_db)):
    """
    Devuelve el catalogo de departamentos para llenar el select en frontend.
    """
    departamentos = db.query(Department).all()
    return departamentos
