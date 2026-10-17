from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSON, UUID, JSONB
import uuid

from .database import Base

class User(Base):
    """Cuenta local usada para iniciar sesión y asignar permisos."""
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, index=True)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(String, default="analyst")
    hashed_password = Column(String, nullable=True)

class Department(Base):
    """Catálogo de áreas disponibles para los comentarios."""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    feedbacks = relationship("FeedbackEntry", back_populates="department")

class CSVImport(Base):
    __tablename__ = "csv_imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, default="QUEUED")
    total_rows = Column(Integer, nullable=False, default=0)
    processed_rows = Column(Integer, nullable=False, default=0)
    skipped_rows = Column(Integer, nullable=False, default=0)
    failed_rows = Column(Integer, nullable=False, default=0)
    error_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

class FeedbackEntry(Base):
    """Comentario recibido después de aplicar la sanitización de PII."""
    __tablename__ = "feedback_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    content_text = Column(Text, nullable=True)
    is_anonymous = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    department = relationship("Department", back_populates="feedbacks")
    analysis = relationship("SentimentAnalysis", back_populates="feedback", uselist=False)

class SentimentAnalysis(Base):
    """Resultado de sentimiento asociado a un comentario."""
    __tablename__ = "sentiment_analysis"

    id = Column(Integer, primary_key=True, index=True)
    feedback_entry_id = Column(UUID(as_uuid=True), ForeignKey("feedback_entries.id"), unique=True)
    polarity_score = Column(Float, nullable=True)
    sentiment_label = Column(String, nullable=True)

    metadata_ai = Column(JSONB, nullable=True)

    feedback = relationship("FeedbackEntry", back_populates="analysis")

class KeyPhrase(Base):
    """Frase clave extraída del análisis."""
    __tablename__ = "key_phrases"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("sentiment_analysis.id"))
    phrase = Column(String, nullable=False)

class Alert(Base):
    """Incidencia que Recursos Humanos debe revisar y gestionar."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    feedback_id = Column(UUID(as_uuid=True), ForeignKey("feedback_entries.id"))
    risk_level = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(String, default="OPEN")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by = Column(String, nullable=True)


