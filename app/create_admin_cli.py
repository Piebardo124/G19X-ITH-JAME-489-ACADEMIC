import getpass
import logging
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
        if db.query(User).filter(User.email == email).first():
            logger.warning("Ya existe una cuenta con ese correo.")
            return
        admin = User(
            user_id=str(uuid.uuid4()),
            email=email,
            role="admin",
            hashed_password=pwd_context.hash(password),
        )
        db.add(admin)
        db.commit()
        logger.info("La cuenta de administración para %s quedó creada.", email)
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_admin()
