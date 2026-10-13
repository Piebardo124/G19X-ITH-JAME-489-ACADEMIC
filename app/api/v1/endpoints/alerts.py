import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.db.database import get_db
from app.core.security import verify_token
from app.db.models import Alert

router = APIRouter()

# Esquema de salida 
class AlertResponse(BaseModel):
    id: int
    feedback_id: uuid.UUID
    risk_level: str
    reason: str
    status: str

    class Config:
        from_attributes = True

# EndPoit
@router.get("/", response_model=List[AlertResponse])
def list_alerts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token) # Token valido
):
    """
    Lista todas las laertas generadas por el sistema.
    Acceso restringido a roles de Administracion y RH
    """
    # Validacion que el usuario tenga el rol correcto.
    rol_usuario = current_user.get("role")
    if rol_usuario not in ["admin", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Solo Recursos Humanos y Administradores pueden ver la bandeja"
        )

    # Consulta a PostgreSQL
    # Alertas ordenadas
    alerts = db.query(Alert).all()

    # Retorno de lista
    return alerts

# Esquema de actualizacion
class AlertUpdate(BaseModel):
    status: str

# Endpoint para actualizar estatus
@router.patch("/{alert_id}", response_model=AlertResponse)
def update_alert_status(
    alert_id: int,
    alert_update: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token)
):
    """
    Actualiza el estatus de un ticket de alerta.
    Solo accesible para admin y hr.
    """
    # Validador de rol
    rol_usuario = current_user.get("role")
    if rol_usuario not in ["admin", "hr"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Solo Recursos Humanos y Administradores pueden gestionar tickets."
        )

    db_alert = db.query(Alert).filter(Alert.id == alert_id).first()
    # En caso de existir error, arrojar error 404
    if not db_alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerta con id {alert_id} no encontrada."
        )

    ESTADOS_VALIDOS = ["OPEN", "IN_PROGRESS", "CLOSED", "FALSE_POSITIVE"]

    if alert_update.status not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Estatus inválido. Use: {ESTADOS_VALIDOS}"
        )

    db_alert.status = alert_update.status
    db.commit()
    db.refresh(db_alert)

    # Alerta actualizada
    return db_alert





















