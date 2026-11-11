import re
import unicodedata

import spacy

try:
    nlp = spacy.load("es_core_news_sm")
except OSError as exc:
    raise RuntimeError("Falta el modelo spaCy es_core_news_sm; instálalo durante el build.") from exc

_KNOWN_NON_PERSON_ENTITIES = {
    "react", "python", "azure", "postgresql", "docker", "typescript",
    "javascript", "fastapi", "vite", "node.js", "reunión", "reunion",
}
_TECHNOLOGY = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(word) for word in sorted(_KNOWN_NON_PERSON_ENTITIES)) + r")(?!\w)",
    re.I,
)
_LABEL = re.compile(r"\[(?:NOMBRE|UBICACION|CORREO|TELEFONO|NUMERO|RFC|CURP) OCULT[OA]\]")
_EMAIL = re.compile(
    r"(?<![\w.+-])[\w.+-]+[ \t]*(?:@|\[arroba\]|\(arroba\))[ \t]*[\w-]+"
    r"(?:\.[\w-]+|[ \t]+\.[ \t]+[\w-]+|[ \t]*\[punto\][ \t]*[\w-]+)+(?![\w-])", re.I
)
_PHONE = re.compile(
    r"(?<!\w)(?:\+?(?:52|1)[ \t.-]?)?(?:\(\d{2,3}\)|\d{2,3})"
    r"[ \t.-]?\d{3,4}[ \t.-]?\d{4}(?!\w)"
)
_RFC = re.compile(
    r"(?<!\w)(?P<base>[A-Za-zÑñ&]{3,4}[ \t]?\d{6})"
    # Homoclave contigua: mixta. Separada: mayúsculas, sin palabras comunes.
    r"(?P<suffix>[A-Za-z\d]{3}|[ \t]+[A-Z\d]{3})?(?!\w)"
)
_CURP = re.compile(r"(?<!\w)[A-Z][AEIOUX][A-Z]{2}\d{6}[HM][A-Z]{5}[A-Z\d]\d(?!\w)", re.I)
_TITLE = re.compile(
    r"(?<!\w)(?:jefe|jefa|gerente|supervisor|supervisora|director|directora|"
    r"compañero|compañera|coordinador|coordinadora|líder|lider|sr\.|sra\.|don|doña)(?!\w)",
    re.I,
)
_NAME_WORD = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")
_NAME_CONNECTORS = {"de", "del", "la", "las", "los", "y"}
_NON_NAME_WORDS = {"teléfono", "telefono", "correo", "contacto", "rfc", "curp", "pedido", "folio"}
_SELF_NAME = re.compile(r"(?i)(?<!\w)(?:me llamo|mi nombre es|la persona)(?!\w)")
_FOLIO = re.compile(r"(?i)\b(?:pedido|folio|orden)\s+(\d{10})\b")


class SanitizationAmbiguityError(ValueError):
    """Entrada que no puede modificarse sin arriesgar pérdida de contexto."""


def _contextual_names(doc, text):
    """Complementa NER con nombres propios tras cargos, sin borrar verbos."""
    tokens = [token for token in doc if not token.is_space]

    def is_name(token, continuation=False):
        return (
            (token.pos_ == "PROPN" or (
                continuation and token.pos_ == "NOUN" and token.dep_ in {"flat", "appos"}
                and not _TITLE.fullmatch(token.text)
            ))
            and _NAME_WORD.fullmatch(token.text) is not None
            and token.text.casefold() not in _NON_NAME_WORDS
        )

    for title in sorted(list(_TITLE.finditer(text)) + list(_SELF_NAME.finditer(text)), key=lambda match: match.start()):
        index = next((i for i, token in enumerate(tokens) if token.idx >= title.end()), len(tokens))
        if index < len(tokens) and tokens[index].text == ":":
            index += 1
        if index >= len(tokens):
            continue
        first = tokens[index]
        # No cruzar líneas ni frases al buscar el nombre posterior al cargo.
        if not re.fullmatch(r"\s*:?[ \t\r\n]*", text[title.end():first.idx]) or not is_name(first):
            continue
        start, end = first.idx, first.idx + len(first.text)
        index += 1
        while index < len(tokens):
            candidate = index
            while candidate < len(tokens) and tokens[candidate].text.casefold() in _NAME_CONNECTORS:
                candidate += 1
            if candidate >= len(tokens) or not is_name(tokens[candidate], continuation=True):
                break
            # Un conector pertenece al nombre solo si sigue otro nombre propio.
            if any(not re.fullmatch(r"\s+", text[tokens[i - 1].idx + len(tokens[i - 1].text):tokens[i].idx])
                   for i in range(index, candidate + 1)):
                break
            end = tokens[candidate].idx + len(tokens[candidate].text)
            index = candidate + 1
        yield start, end, "[NOMBRE OCULTO]", 80


def _visible_fragments(start, end, excluded, text):
    """Dividir una entidad alrededor de etiquetas/PII sin borrarlas ni saltarse el resto."""
    fragments = [(start, end)]
    for left, right in excluded:
        remaining = []
        for first, last in fragments:
            if first < right and last > left:
                if first < left:
                    remaining.append((first, left))
                if last > right:
                    remaining.append((right, last))
            else:
                remaining.append((first, last))
        fragments = remaining
    for first, last in fragments:
        while first < last and text[first].isspace():
            first += 1
        while last > first and text[last - 1].isspace():
            last -= 1
        if first < last:
            yield first, last


def sanitize_text(text: str) -> str:
    """Reduce PII conocida; los nombres se detectan por heurísticas, sin garantía de anonimato."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    # Posiciones siempre sobre el mismo original. Los espacios conservan
    # offsets y evitan que spaCy reinterprete etiquetas o identificadores.
    protected = [(match.start(), match.end()) for match in _LABEL.finditer(text)]
    spans = []
    for pattern, label in (
        (_EMAIL, "[CORREO OCULTO]"), (_CURP, "[CURP OCULTA]"),
        (_RFC, "[RFC OCULTO]"), (_PHONE, "[TELEFONO OCULTO]"),
    ):
        for match in pattern.finditer(text):
            if not any(match.start() < end and match.end() > start for start, end in protected):
                end = match.end()
                match_label = label
                if pattern is _RFC:
                    suffix = match.group("suffix") or ""
                    # Una palabra separada de tres letras puede ser homoclave
                    # o contexto. No adivinar ni borrar palabras silenciosamente.
                    if suffix[:1].isspace():
                        if suffix.strip().casefold() in nlp.Defaults.stop_words:
                            end = match.end("base")
                        else:
                            raise SanitizationAmbiguityError(
                                "El RFC separado es ambiguo. Retira el identificador personal antes de enviar."
                            )
                if pattern is _PHONE and any(
                    folio.start(1) == match.start() and folio.end(1) == end
                    for folio in _FOLIO.finditer(text)
                ):
                    match_label = "[NUMERO OCULTO]"
                spans.append((match.start(), end, match_label, 100))
    masked = list(text)
    technology = [(match.start(), match.end()) for match in _TECHNOLOGY.finditer(text)]
    # Una tecnología usada explícitamente como nombre tras un cargo no queda
    # exenta por la lista de términos técnicos.
    technology = [(start, end) for start, end in technology if not any(
        re.fullmatch(r"[ \t]*:?[ \t]*", text[title.end():start])
        for title in list(_TITLE.finditer(text, 0, start)) + list(_SELF_NAME.finditer(text, 0, start))
    )]
    excluded = protected + technology + [(start, end) for start, end, _, _ in spans]
    for start, end in excluded:
        masked[start:end] = " " * (end - start)
    safe_input = "".join(masked)
    doc = nlp(safe_input)
    for start, end, label, priority in _contextual_names(doc, safe_input):
        spans.extend((left, right, label, priority)
                     for left, right in _visible_fragments(start, end, excluded, text))
    for entity in doc.ents:
        # Una entidad que incluye un hueco enmascarado no es fiable: spaCy
        # puede extender PER desde «teléfono» hasta una etiqueta ya oculta.
        # Los nombres contextuales sí se dividen explícitamente arriba.
        if any(entity.start_char < right and entity.end_char > left for left, right in excluded):
            if entity.label_ in {"PER", "LOC"}:
                label = "[NOMBRE OCULTO]" if entity.label_ == "PER" else "[UBICACION OCULTA]"
                for token in entity:
                    if token.pos_ == "PROPN" and token.text.casefold() not in _NON_NAME_WORDS:
                        spans.extend((left, right, label, 50) for left, right in
                                     _visible_fragments(token.idx, token.idx + len(token.text), excluded, text))
            continue
        words = {token.casefold() for token in re.findall(r"[\w.]+", entity.text)}
        if words and words.issubset(_KNOWN_NON_PERSON_ENTITIES):
            continue
        if entity.label_ in {"PER", "LOC"}:
            label = "[NOMBRE OCULTO]" if entity.label_ == "PER" else "[UBICACION OCULTA]"
            spans.append((entity.start_char, entity.end_char, label, 50))
    # Los identificadores y nombres contextuales ganan a entidades amplias.
    accepted = []
    for start, end, label, priority in sorted(spans, key=lambda item: (-item[3], -(item[1] - item[0]), item[0])):
        occupied = protected + [(left, right) for left, right, _ in accepted]
        if not any(start < right and end > left for left, right in occupied):
            accepted.append((start, end, label))
    for start, end, label in sorted(accepted, reverse=True):
        text = text[:start] + label + text[end:]
    return text
