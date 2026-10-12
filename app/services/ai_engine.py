import os
from dotenv import load_dotenv
# from langchain_openai import AzureChatOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List

# Cargar variables de entorno desde el archivo .env
load_dotenv() 

# Definicion de Contrato de salida
class AIAnalysisResult(BaseModel):
    polarity_score: float = Field (..., description="Puntuacion de -1.0 (muy negativo) a 1.0 (muy positivo)")
    sentiment_label: str = Field(..., description = "Positivo, Negativo o Neutral")
    emotions_detected: List[str] = Field(..., description = "Lista de emociones detectadas, ej: frustración, alegría")
    organizational_axes: List[str] = Field(..., description = "Ejes afectados. Solo usa: Liderazgo y management, Carga de trabajo, Ambiente laboral, Compensaciones, Herramientas")
    risk_burnout: bool = Field(..., description="True si hay indicios de burnout, estrés extremo, acoso o renuncia")
    red_flag_reason: str = Field(default="", description="Breve justificación si risk_burnout es True, de lo contrario vacío")
    key_phrases: List[str] = Field(..., description="Lista de 3 a 5 conceptos o frases clave (ej: 'comunicación nula', 'líder exige tiempos irreales')")
    



def analyze_sentiment_with_ai(text: str) -> dict:
    """
    Procesa el texto sanitizado utilizando LangChain y modelos LLM.
    evalua polaridad, ejes organizacionales y banderas rojas de riesgo.
    """

    # Verificacion de credenciales en .env; en caso de no, usa fallback
    if not os.getenv("AZURE_OPENAI_API_KEY"):
        return _fallback_simulation(text)

    print(f"DEBUG -> Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')} | Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}")
    try:
        # Configuracion del LLM
        llm = ChatOpenAI(
            base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-plurione"),
            temperature=0.0,  # Máxima precisión
            timeout=10.0,
            max_retries=0
        )

        # Obligando para que el modelo respete la estructura de Pydantic
        structured_llm = llm.with_structured_output(AIAnalysisResult)

        # Prompt de Ingenieria
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Eres un analista experto de Recursos Humanos y Psicología Organizacional en la empresa PluriOne S.A. de C.V. "
                       "Tu tarea es analizar comentarios de empleados de forma objetiva, identificar "
                       "el sentimiento general, las emociones subyacentes y clasificar el comentario "
                       "dentro de los ejes organizacionales establecidos. "
                       "CRÍTICO: Si detectas intenciones de renuncia, acoso, o burnout severo, DEBES "
                       "levantar una bandera roja (risk_burnout=True) y justificarla brevemente."),
            ("human", "Analiza el siguiente comentario del empleado:\n\n{texto_empleado}")
        ])

        chain = prompt | structured_llm
        result = chain.invoke({"texto_empleado": text})

        # Mapeado de salida para encajar Endpoint de FastAPI
        return {
            "polarity_score": result.polarity_score,
            "sentiment_label": result.sentiment_label,
            "key_phrases": result.key_phrases,
            "metadata_ai": {
                "emotions": result.emotions_detected,
                "organizational_axes": result.organizational_axes,
                "risk_burnout": result.risk_burnout,
                "red_flag_reason": result.red_flag_reason
            }
        }

    except Exception as e:
        print (f" Error conectando con Azure OpenAI: {e}")
        return _fallback_simulation(text)

def _fallback_simulation(text: str) -> dict:
    """
    Simulacion de respaldo
    solo se ejecutara si hay una falla en la API de Azure
    """

    texto_lower = text.lower()
    if any(palabra in texto_lower for palabra in ["mal", "pesado", "estrés", "renunciar", "problema"]):
        return {
            "polarity_score": -0.8,
            "sentiment_label": "Negativo",
            "key_phrases": ["fallback error"],
            "metadata_ai": {
                "emotions": ["frustración", "cansancio"],
                "organizational_axes": ["Carga de trabajo"],
                "risk_burnout": True,
                "red_flag_reason": "Fallback: Lenguaje asociado a estrés o renuncia"
            }
        }
        
    return {
        "polarity_score": 0.8,
        "sentiment_label": "Positivo",
        "key_phrases": ["fallback error"],
        "metadata_ai": {
            "emotions": ["motivación"],
            "organizational_axes": ["Ambiente laboral"],
            "risk_burnout": False,
            "red_flag_reason": ""
        }
    }

def generate_executive_summary(text_batch: str) -> str:
    """
    Genera un resumen ejecutivo cualitativo a partir de multiples comentarios.
    """
    if not os.getenv("AZURE_OPENAI_API_KEY"):
        return "Simulador: El clima laboral muestra áreas de oportunidad en carga de trabajo, pero buena motivación general."

    try:
        llm = ChatOpenAI(
            base_url=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-plurione"),
            temperature=0.3, 
            max_retries=0
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", "Eres un Consultor Ejecutivo de Recursos Humanos en PluriOne S.A. de C.V. "
                       "Tu tarea es leer una lista de comentarios anónimos de empleados y redactar un "
                       "resumen ejecutivo cualitativo de un solo párrafo. Destaca el sentir general, "
                       "los puntos fuertes y las alertas críticas si las hay."),
            ("human", "Comentarios de los empleados:\n\n{comentarios}")
        ])

        chain = prompt | llm
        result = chain.invoke({"comentarios": text_batch})

        return result.content
    except Exception as e:
        print(f"Error generando resumen: {e}")
        return "No se pudo generar el resumen debido a un error de conexión con la IA."
    
            
