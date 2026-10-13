import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext

from app.db.database import get_db
from app.db.models import User
from app.core.security import create_access_token

router = APIRouter()

# Configuración para verificar contraseñas almacenadas.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRegister(BaseModel):
    email: str
    password: str


@router.post("/register-admin")
def create_admin_user(user: UserRegister, db: Session = Depends(get_db)):
    """Crea una cuenta de administrador para la instalación local."""
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")

    admin = User(
        user_id=str(uuid.uuid4()),
        email=user.email,
        role="admin",
        hashed_password=pwd_context.hash(user.password),
    )
    db.add(admin)
    db.commit()
    return {"message": "Administrador creado. Ya puedes iniciar sesión."}


@router.post("/login")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Busca la cuenta por correo electrónico.
    user = db.query(User).filter(User.email == form_data.username).first()

    # Rechaza credenciales incorrectas o cuentas sin contraseña local.
    if not user or not user.hashed_password or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Incluye el correo y el rol en el token.
    token_data = {
        "sub": user.email,
        "role": user.role
    }

    access_token = create_access_token(data=token_data)

    # Devuelve el token al frontend.
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }
