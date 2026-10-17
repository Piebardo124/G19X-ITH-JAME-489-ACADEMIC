import os
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise ValueError("La variable de entorno JWT_SECRET_KEY no está configurada.")
if len(SECRET_KEY.encode("utf-8")) < 32:
    raise ValueError("JWT_SECRET_KEY debe tener al menos 32 bytes para HS256.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

oauth2_schema = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def create_access_token(data: dict):
    """Crea un token de acceso con los datos del usuario y su expiración."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str = Depends(oauth2_schema)):
    """Valida el token y devuelve la identidad y el rol incluidos en él."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")

        if email is None or role is None:
            raise credentials_exception

        return {"email": email, "role": role}

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion de 8 horas expiro, Inicia sesion nuevamente."
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

