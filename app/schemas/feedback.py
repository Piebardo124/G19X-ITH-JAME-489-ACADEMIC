from pydantic import BaseModel, UUID4, Field
from typing import List, Optional, Dict, Any

#Entrada
class FeedbackCreate(BaseModel):
    ##Input JSON requerido en POST /api/v1/nlp/analyze-feedback
    text_content: str = Field(..., min_length=5, max_length=3000, description="Comentario Random")
    is_anonymous: bool = True
    department_id: Optional[int] = None

#Salida
class AIAnalysisResponse(BaseModel):
    label: str
    polarity: Optional[float]
    key_phrases: List[str]
    details: Dict[str, Any]
    
class FeedbackResponse(BaseModel):
    status: str
    message: str
    entry_id: UUID4
    alert_generated_id: Optional[int] = None
    ai_analysis: AIAnalysisResponse


