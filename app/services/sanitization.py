import re
import spacy

# Carga NLP en español de spaCy
try:
    nlp = spacy.load("es_core_news_sm")
except OSError:
    # En caso de no instalarse, se realiza descarga.
    from spacy.cli import download
    download("es_core_news_sm")
    nlp = spacy.load("es_core_news_sm")


def sanitize_text(text: str) -> str:
    """
    Filtra informacion de identificacion personal basica antes de persistir el texto o enviarlo a la IA
    """

    if not text:
        return ""

    # Enmarcar correos electronicos
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[CORREO OCULTO]', text)

    # Enmarcar numeros de telefono
    text = re.sub(r'\b\d{8,12}\b', '[TELEFONO OCULTO]', text)

    # Enmarcado de posible RFC o ID de empleado
    text = re.sub(r'\b[A-ZÑ&]{3,4}\d{6}(?:[A-Z\d]{3})?\b', '[RFC/ID OCULTO]', text, flags=re.IGNORECASE)

    # Filtrado inteligente con NLP
    doc = nlp(text)
    texto_limpio = text

    # Identificador y remplazador de entidades
    for ent in doc.ents:
        if ent.label_ == "PER":
            texto_limpio = texto_limpio.replace(ent.text, '[NOMBRE OCULTO]')
        elif ent.label_ == "LOC":
            texto_limpio = texto_limpio.replace(ent.text, '[UBICACION OCULTA]')

    return texto_limpio
