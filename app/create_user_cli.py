"""CLI interactivo para crear usuarios locales que no sean administradores."""

import getpass
import logging
import re
import uuid

from passlib.context import CryptContext
from sqlalchemy import func

from app.db.database import SessionLocal
from app.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

ALLOWED_ROLES = {"hr", "analyst", "executive"}
EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
MIN_PASSWORD_CHARACTERS = 12
MAX_BCRYPT_PASSWORD_BYTES = 72


def create_user(email: str, role: str, password: str) -> bool:
    """Valida y crea un usuario que no sea administrador. Indica si tuvo éxito."""
    normalized_email = email.strip().casefold()
    normalized_role = role.strip().casefold()

    if not EMAIL_PATTERN.fullmatch(normalized_email):
        logger.error("El correo no tiene un formato válido.")
        return False
    if normalized_role not in ALLOWED_ROLES:
        logger.error("Rol inválido. Usa hr, analyst o executive.")
        return False
    if len(password) < MIN_PASSWORD_CHARACTERS:
        logger.error("La contraseña debe tener al menos 12 caracteres.")
        return False
    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        logger.error("La contraseña no puede superar 72 bytes UTF-8 (límite de bcrypt).")
        return False

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(
            func.lower(User.email) == normalized_email
        ).first()
        if existing_user:
            logger.error("Ya existe una cuenta con ese correo.")
            return False

        user = User(
            user_id=str(uuid.uuid4()),
            email=normalized_email,
            role=normalized_role,
            hashed_password=pwd_context.hash(password),
        )
        db.add(user)
        db.commit()
        logger.info("La cuenta %s con rol %s quedó creada.", normalized_email, normalized_role)
        return True
    except Exception as error:
        db.rollback()
        logger.error("No se pudo crear el usuario (tipo=%s).", type(error).__name__)
        return False
    finally:
        db.close()


def init_user() -> bool:
    """Solicita los datos de la cuenta sin mostrar la contraseña al escribirla."""
    email = input("Correo del usuario: ").strip()
    role = input("Rol (hr, analyst, executive): ").strip()
    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirma la contraseña: ")
    if password != confirmation:
        logger.error("Las contraseñas no coinciden.")
        return False
    return create_user(email=email, role=role, password=password)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_user()
