import re
from pydantic import BaseModel, UUID4, Field, field_validator
from typing import Optional, Literal

#Entrada
class FeedbackCreate(BaseModel):
    text_content: str = Field(..., min_length=5, max_length=3000, description="Comentario")
    is_anonymous: Literal[True] = True
    department_id: Optional[int] = None

    @field_validator("text_content", mode="before")
    @classmethod
    def trim_and_validate_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not re.search(r"[^\W\d_]{2,}", value):
                raise ValueError("El comentario debe incluir al menos una palabra con dos letras.")
            if len(value) < 5 or len(value) > 3000:
                raise ValueError("El comentario debe tener entre 5 y 3000 caracteres.")
        return value

#Salida
class FeedbackResponse(BaseModel):
    status: str
    message: str
    entry_id: UUID4


