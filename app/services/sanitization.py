import re
import spacy

try:
    nlp = spacy.load("es_core_news_sm")
except OSError as exc:

    raise RuntimeError("Falta el modelo spaCy es_core_news_sm; instálalo durante el build.") from exc

_KNOWN_NON_PERSON_ENTITIES = {
    "react", "python", "azure", "postgresql", "docker", "typescript",
    "javascript", "fastapi", "vite", "node.js", "reunión", "reunion",
}


def sanitize_text(text: str) -> str:
    """Oculta patrones comunes de PII antes de guardar o analizar el comentario."""

    if not text:
        return ""

    # Detectar nombres y ubicaciones antes de insertar etiquetas para que spaCy
    # no vuelva a interpretar [CORREO OCULTO] como una entidad personal.
    doc = nlp(text)
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

    # Admitir formatos telefónicos comunes de México (10 dígitos, con o sin
    # clave de país), sin absorber espacios previos ni secuencias numéricas
    # cortas como folios o fechas.
    phone_pattern = (
        r'(?<!\w)(?:\+?52[\s-]?)?(?:\(\d{2,3}\)|\d{2,3})'
        r'[\s-]?\d{3,4}[\s-]?\d{4}(?!\w)'
    )
    texto_limpio = re.sub(phone_pattern, '[TELEFONO OCULTO]', texto_limpio)

    # Ocultar correo y RFC después de spaCy para mantener intactas las etiquetas.
    email_pattern = r'(?<![\w.+-])[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?![\w-])'
    texto_limpio = re.sub(email_pattern, '[CORREO OCULTO]', texto_limpio)
    rfc_pattern = r'\b[A-Za-zÑñ&]{3,4}\s?\d{6}\s?(?:[A-Za-z\d]{3})?\b'
    texto_limpio = re.sub(rfc_pattern, '[RFC OCULTO]', texto_limpio)
    return texto_limpio
