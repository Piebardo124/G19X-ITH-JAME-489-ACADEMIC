import getpass
import uuid
from passlib.context import CryptContext
from app.db.database import SessionLocal
from app.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_admin():
    email = input("Ingresa el correo del administrador: ").strip()
    password = getpass.getpass("Ingresa la contraseña: ")
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            print("El usuario ya existe.")
            return
        admin = User(
            user_id=str(uuid.uuid4()),
            email=email,
            role="admin",
            hashed_password=pwd_context.hash(password),
        )
        db.add(admin)
        db.commit()
        print(f"Administrador {email} creado exitosamente.")
    finally:
        db.close()

if __name__ == "__main__":
    # Comando de inicialización de un solo uso
    init_admin()