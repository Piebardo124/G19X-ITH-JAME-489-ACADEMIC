import re
import spacy

# Carga NLP en español de spaCy
try:
    nlp = spacy.load("es_core_news_sm")
except OSError as exc:
    # No iniciar descargas de red implícitas al importar la aplicación.
    raise RuntimeError("Falta el modelo spaCy es_core_news_sm; instálalo durante el build.") from exc

_KNOWN_NON_PERSON_ENTITIES = {
    "react", "python", "azure", "postgresql", "docker", "typescript",
    "javascript", "fastapi", "vite", "node.js",
}


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
    # Aplicar solo sobre offsets detectados; str.replace podía ocultar otras
    # apariciones idénticas en palabras distintas (p. ej. "React" dentro de otra palabra).
    replacements = []
    for ent in doc.ents:
        entity_words = {token.casefold() for token in re.findall(r"[\w.]+", ent.text)}
        if entity_words.intersection(_KNOWN_NON_PERSON_ENTITIES):
            continue
        if ent.label_ == "PER":
            replacements.append((ent.start_char, ent.end_char, "[NOMBRE OCULTO]"))
        elif ent.label_ == "LOC":
            replacements.append((ent.start_char, ent.end_char, "[UBICACION OCULTA]"))

    texto_limpio = text
    for start, end, replacement in sorted(replacements, reverse=True):
        texto_limpio = texto_limpio[:start] + replacement + texto_limpio[end:]
    return texto_limpio
