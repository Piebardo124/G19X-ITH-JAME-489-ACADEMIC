from pydantic import BaseModel, UUID4, Field
from typing import List, Optional
from datetime import datetime

#Entrada
class FeedbackCreate(BaseModel):
    ##Input JSON requerido en POST /api/v1/nlp/analyze-feedback
    text_content: str = Field(..., min_length=5, max_length=3000, description="Comentario Random")
    is_anonymous: bool = True
    department_id: Optional[int] = None

#Salida
class SentimentSummary(BaseModel):
    label: str
    polarity_score: float

class RiskAssesment(BaseModel):
    risk_level: str
    risk_score: float
    red_flag_reason: Optional[str] = None

class FeedbackResponseData(BaseModel):
    entry_id: UUID4
    analyzed_add_at: datetime
    cleaned_text: str
    sentiment_summary: SentimentSummary
    emotions_detected: List[str]
    organizactional_axes:List[str]
    risk_assesment: RiskAssesment

class FeedbackResponse(BaseModel):
    ## Contrato de salida principal
    status: str = "success"
    data: FeedbackResponseData

