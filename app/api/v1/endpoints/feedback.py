from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal
from app.db.models import FeedbackEntry, SentimentAnalysis, Alert, KeyPhrase
from app.schemas.feedback import FeedbackCreate
from app.services.sanitization import sanitize_text
from app.services.ai_engine import analyze_sentiment_with_ai, generate_executive_summary
from typing import Optional
from app.core.security import verify_token
from app.services.email_service import send_alert_email
from app.db.models import Department
import uuid
import csv
import io
import time
import traceback

router = APIRouter()

@router.post("/analyze-feedback")
def analyze_feedback(
    feedback: FeedbackCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),

):
    try:

        # Limpieza de texto con posibles datos sensibles.
        texto_limpio = sanitize_text(feedback.text_content)

        # Preparador de registros para tabla feedback_entries
        new_feedback = FeedbackEntry(
            id=uuid.uuid4(),
            content_text=texto_limpio,
            is_anonymous=feedback.is_anonymous,
            department_id=feedback.department_id
        )

        # Insercion de datos y guardado en PsotgreSQL
        db.add(new_feedback)
        db.commit()
        db.refresh(new_feedback)

        # Pasador de texto limpio en motor IA
        ai_results = analyze_sentiment_with_ai(texto_limpio)

        # Logica de guardado de resultados de la IA en sentimen_analysis
        new_analysis = SentimentAnalysis(
            feedback_entry_id=new_feedback.id,
            polarity_score=ai_results["polarity_score"],
            sentiment_label=ai_results["sentiment_label"],
            metadata_ai=ai_results["metadata_ai"]
        )
        db.add(new_analysis)
        db.commit()
        db.refresh(new_analysis)

        # Guardado de frases clave en su propia tabla
        if "key_phrases" in ai_results:
            for phrase in ai_results["key_phrases"]:
                nueva_frase = KeyPhrase(
                    analysis_id=new_analysis.id,
                    phrase=phrase
                )
                db.add(nueva_frase)
            db.commit()


        # Funcion para Alertas automaticas (Dichosas banderas rojas)
        alerta_id = None
        is_risk = ai_results["metadata_ai"].get("risk_burnout", False)

        if is_risk:
            nueva_alerta = Alert(
                feedback_id=new_feedback.id,
                risk_level="ALTO",
                reason=ai_results["metadata_ai"].get("red_flag_reason", "Riesgo detectado por IA")
            )
            db.add(nueva_alerta)
            db.commit()
            db.refresh(nueva_alerta)

            # En caso de riesgo, actualizador de varibale con el ID real de la base de datos
            alerta_id = nueva_alerta.id

            background_tasks.add_task(
                send_alert_email,
                alert_id=alerta_id,
                reason=nueva_alerta.reason
            )

        return {
            "status": "success",
            "message": "Feedback recibido, sanitizado y analizado correctamente",
            "entry_id": new_feedback.id,
            "alert_generated_id": alerta_id,
            "ai_analysis": {
                "label": ai_results["sentiment_label"],
                "polarity": ai_results["polarity_score"],
                "key_phrases": ai_results.get("key_phrases", []),
                "details": ai_results["metadata_ai"]
            }
        }

        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=str(e)
        )
    
def process_csv_background(file_content: str):
    """
    Funcion que procesa el CSV fila por fila en segundo plano.
    Crea su propia sesion de base de datos para no interferir con el hilo principal.
    """
    db = SessionLocal()
    try:
        # Lee el CSV (esperando columnas: text_content, is_anonymous, department_id)
        reader = csv.DictReader(io.StringIO(file_content))

        for index, row in enumerate(reader, start=1):
            try:
                texto = row.get("text_content")
                # Salto si el texto es muy corto
                if not texto or len(texto) < 5:
                    print(f"Registro {index} omitido por texto muy corto.")
                    continue
                
                # Normalizacion de datos del CSV
                is_anon = str(row.get("is_anonymous", "True")).strip().lower() == "true"
                dep_id_raw = row.get("department_id")
                dep_id = int(dep_id_raw) if dep_id_raw and dep_id_raw.isdigit() else None

                # Sanitizacion
                texto_limpio = sanitize_text(texto)

                # Guardado de entrada
                new_feedback = FeedbackEntry(
                    id=uuid.uuid4(),
                    content_text=texto_limpio,
                    is_anonymous=is_anon,
                    department_id=dep_id
                )
                db.add(new_feedback)
                db.commit()
                db.refresh(new_feedback)

                # Analisis de IA
                ai_results = analyze_sentiment_with_ai(texto_limpio)

                # Guardado de analisis
                new_analysis = SentimentAnalysis(
                    feedback_entry_id=new_feedback.id,
                    polarity_score=ai_results["polarity_score"],
                    sentiment_label=ai_results["sentiment_label"],
                    metadata_ai=ai_results["metadata_ai"]
                )
                db.add(new_analysis)
                db.commit()

                # Generacion de Banderas Rojas
                if ai_results["metadata_ai"].get("risk_burnout", False):
                    nueva_alerta = Alert(
                        feedback_id=new_feedback.id,
                        risk_level="ALTO",
                        reason=ai_results["metadata_ai"].get("red_flag_reason", "Riesgo detectado en carga masiva")
                    )
                    db.add(nueva_alerta)
                    # db.commit()

                print(f"Registro {index} procesado con exito.")

            except Exception as row_error:
                db.rollback()
                print(f"Error en registro {index}: {row_error}")
                traceback.print_exc()
                continue 
        db.commit()

    except Exception as e:
        print(f"Error general en procesamiento masivo en segundo plano: {e}")
    finally:
        db.close()

@router.post("/upload-csv")
async def upload_feeback_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
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
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="El archivo debe ser de tipo CSV.")

    try:
        # Leer el contenido del archivo a memoria.
        content = await file.read()
        decoded_content = content.decode ("utf-8")

        # Inyectar el proceso en la cola de tareas de segundo plano
        background_tasks.add_task(process_csv_background, decoded_content)

        return {
            "status": "success", 
            "message": f"El archivo '{file.filename}' se está analizando en segundo plano. Las alertas detectadas irán apareciendo en tu Dashboard de RH."
        }

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="El archivo CSV debe estar codificado en UTF-8.")

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

    # COnsulta a la base de datos
    query = db.query(FeedbackEntry)
    if department_id:
        query = query.filter(FeedbackEntry.department_id == department_id)

    comentarios = query.all()

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