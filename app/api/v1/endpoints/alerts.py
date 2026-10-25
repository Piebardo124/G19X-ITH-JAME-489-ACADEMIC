import uuid
from datetime import date, datetime, time, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.db.database import get_db
from app.core.security import require_roles
from app.db.models import Alert, FeedbackEntry

router = APIRouter()

class AlertResponse(BaseModel):
    id: int
    feedback_id: uuid.UUID
    risk_level: str
    reason: str
    status: str

    class Config:
        from_attributes = True

@router.get("/", response_model=List[AlertResponse])
def list_alerts(
    response: Response,
    status_filter: Optional[str] = None,
    risk_level: Optional[str] = None,
    department_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "hr", "analyst"))
):
    """Devuelve las alertas que puede consultar el usuario autenticado."""
    query = db.query(Alert)

    if status_filter:
        query = query.filter(Alert.status == status_filter)
    if risk_level:
        query = query.filter(Alert.risk_level == risk_level)
    if department_id is not None:
        query = query.join(FeedbackEntry)
        if department_id == 0:
            query = query.filter(FeedbackEntry.department_id.is_(None))
        else:
            query = query.filter(FeedbackEntry.department_id == department_id)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from no puede ser posterior a date_to.")
    if date_from:
        query = query.filter(
            Alert.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to:
        query = query.filter(
            Alert.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    alerts = (
        query.order_by(Alert.created_at.desc(), Alert.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
        .all()
    )
    has_more = len(alerts) > page_size
    response.headers["X-Has-More"] = str(has_more).lower()
    return alerts[:page_size]

class AlertUpdate(BaseModel):
    status: str

@router.patch("/{alert_id}", response_model=AlertResponse)
def update_alert_status(
    alert_id: int,
    alert_update: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "hr", "analyst"))
):
    """Actualiza el estado de una alerta y registra quién hizo el cambio."""

    db_alert = db.query(Alert).filter(Alert.id == alert_id).first()
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
    db_alert.updated_by = current_user.get("email")
    db.commit()
    db.refresh(db_alert)

    return db_alert
