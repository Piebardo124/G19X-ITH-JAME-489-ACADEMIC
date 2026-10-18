import time
import logging
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.endpoints import feedback, auth, alerts
from app.db.database import engine, SessionLocal
from app.db import models
from app.db.models import Department

logger = logging.getLogger(__name__)
DEFAULT_DEPARTMENTS = [
    (1, "Recursos Humanos"),
    (2, "Tecnología"),
    (3, "Marketing"),
    (4, "Ventas"),
    (5, "Finanzas"),
]

def init_db():
    for intento in range(5):
        try:
            models.Base.metadata.create_all(bind=engine)
            logger.info("Tablas de la base de datos listas.")
            return
        except OperationalError:
            logger.warning("Esperando a PostgreSQL (intento %s/5).", intento + 1)
            time.sleep(5)
    raise Exception("No se pudo conectar a la base de datos después de 5 intentos. Verifica que el contenedor de PostgreSQL esté en funcionamiento y que las credenciales sean correctas.")

def seed_departments():
    db = SessionLocal()
    try:
        for department_id, name in DEFAULT_DEPARTMENTS:
            existing_by_name = db.query(Department).filter(Department.name == name).first()
            if existing_by_name:
                continue

            existing_by_id = db.query(Department).filter(Department.id == department_id).first()
            if existing_by_id:
                logger.warning(
                    "No se pudo agregar el departamento semilla %s: el ID %s ya pertenece a otro departamento.",
                    name,
                    department_id,
                )
                continue

            db.add(Department(id=department_id, name=name))
        db.flush()
        # Los IDs de la semilla son explícitos; sincronizar la secuencia evita
        # que el siguiente INSERT automático reutilice uno ya ocupado.
        db.execute(text("""
            SELECT setval(
                pg_get_serial_sequence('departments', 'id')::regclass,
                COALESCE(MAX(id), 1),
                COUNT(*) > 0
            )
            FROM departments
        """))
        db.commit()
        logger.info("Se verificaron los departamentos iniciales.")
    except Exception as e:
        db.rollback()
        logger.error("Error al crear departamentos (tipo=%s).", type(e).__name__)
        raise e
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando la aplicación.")
    init_db()
    seed_departments()
    yield
    logger.info("Cerrando la aplicación.")
app = FastAPI(
    title="PluriOne Sentiment Analysis API",
    description="API RESTful para el analisis de sentimientos de comentarios de empleados",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def read_root():
    return {"status": "success", "message": "El middleware esta en funcion"}

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticacion"])
app.include_router(feedback.router, prefix="/api/v1/nlp", tags=["NLP Core"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Gestión de Alertas"])
