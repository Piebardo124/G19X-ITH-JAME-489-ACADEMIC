import getpass
import logging
import re
import uuid
from passlib.context import CryptContext
from app.db.database import SessionLocal
from app.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

def init_admin():
    email = input("Correo del administrador: ").strip()
    password = getpass.getpass("Contraseña del administrador: ")
    db = SessionLocal()
    try:
        if db.query(User).filter(User.role == "admin").first():
            logger.error("Ya existe un administrador. El asistente solo permite crear el administrador inicial.")
            return False
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            logger.error("El correo no tiene un formato válido.")
            return False
        if len(password) < 12:
            logger.error("La contraseña debe tener al menos 12 caracteres.")
            return False
        if db.query(User).filter(User.email == email).first():
            logger.warning("Ya existe una cuenta con ese correo.")
            return False
        admin = User(
            user_id=str(uuid.uuid4()),
            email=email,
            role="admin",
            hashed_password=pwd_context.hash(password),
        )
        db.add(admin)
        db.commit()
        logger.info("La cuenta de administración para %s quedó creada.", email)
        return True
    except Exception:
        db.rollback()
        logger.exception("No se pudo crear el administrador inicial.")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_admin()
