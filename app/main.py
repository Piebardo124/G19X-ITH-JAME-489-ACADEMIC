from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.endpoints import feedback, auth, alerts
from app.db.database import engine, SessionLocal
from app.db import models
from app.db.models import Department

#Generador de tablas en base de datos segun models.py
models.Base.metadata.create_all(bind=engine)

def seed_departments():
    db = SessionLocal()
    try:
        # Verificar si ya existen departamentos
        existing_departments = db.query(Department).count()
        if existing_departments == 0:
            # Crear departamentos iniciales
            departments = [
                Department(id=1,name="Recursos Humanos"),
                Department(id=2, name="Tecnología"),
                Department(id=3, name="Marketing"),
                Department(id=4, name="Ventas"),
                Department(id=5, name="Finanzas")
            ]
            db.add_all(departments)
            db.commit()
            print("Departamentos iniciales creados.")
    except Exception as e:
        db.rollback()
        print(f"Error al crear departamentos: {e}")
        raise e
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print ("iniciando la aplicacion")
    seed_departments()
    yield
    print ("cerrando la aplicacion")
app = FastAPI(
    title="PluriOne Sentiment Analysis API",
    description="API RESTful para el analisis de sentimientos de comentarios de empleados",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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