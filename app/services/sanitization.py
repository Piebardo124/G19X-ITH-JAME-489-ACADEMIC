import re
import unicodedata

import regex as unicode_regex
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
# Los espacios horizontales Unicode también se usan para disfrazar correos.
# Sólo la primera separación de dominio acepta espacio después del punto:
# tras un correo completo, «. Pedido ...» pertenece a la siguiente frase.
_HSPACE = r"[^\S\r\n]"
_EMAIL_LOCAL_CHARS = r"\w.!#$%&'*+/=?^`{|}~\-"
_EMAIL = unicode_regex.compile(
    rf'(?<![{_EMAIL_LOCAL_CHARS}])(?:[{_EMAIL_LOCAL_CHARS}]+|"(?:[^"\\\r\n]|\\.)+")'
    rf"{_HSPACE}*(?:@|\[arroba\]|\(arroba\)){_HSPACE}*[\w-]+"
    rf"{_HSPACE}*(?:\.|\[punto\]){_HSPACE}*[\w-]+"
    rf"(?:\.[\w-]+|{_HSPACE}*\[punto\]{_HSPACE}*[\w-]+)*(?![\w-])", re.I
)
_PHONE = re.compile(
    r"(?<!\w)(?:\+?(?:52|1)[\s./-]*)?(?:"
    r"(?:\(\d{2,3}\)|\d{2,3})[\s./-]*\d{3,4}[\s./-]*\d{4}"
    r"|(?:\d{2}[\s./-]+){4}\d{2})(?!\w)"
)
_UNICODE_DASH = unicode_regex.compile(r"\p{Dash}\Z")
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


def _normalize_for_detection(text):
    """Quita controles de formato invisibles antes de calcular posiciones.

    NFC conserva acentos. Los controles Cf, el combinador invisible y los
    selectores de variación no deben separar los caracteres de un identificador.
    No se eliminan los espacios ni los saltos de línea del relato.
    """
    if any(unicodedata.category(char) == "Cc" and char not in "\t\r\n" for char in text):
        raise SanitizationAmbiguityError("El texto contiene caracteres de control no admitidos.")
    return unicodedata.normalize("NFC", "".join(
        char for char in text
        if unicodedata.category(char) != "Cf"
        and char != "\u034f"
        and not "\ufe00" <= char <= "\ufe0f"
        and not "\U000e0100" <= char <= "\U000e01ef"
    ))


def _canonical_view(text):
    """Vista de detección NFKC con posiciones del relato, que no se reescribe.

    El mapa por grafema admite expansiones como ligaduras y conserva los
    offsets aunque la normalización cambie el número de caracteres.
    """
    characters, positions = [], []
    for cluster in unicode_regex.finditer(r"\X", text):
        for char in unicodedata.normalize("NFKC", cluster.group()):
            if char.isdecimal():
                char = str(unicodedata.decimal(char))
            elif _UNICODE_DASH.fullmatch(char):
                char = "-"
            elif char == "\u3002":
                # Separador de etiquetas IDNA; FF0E/FF61 llegan aquí por NFKC.
                char = "."
            elif unicodedata.name(char, "") in {"FRACTION SLASH", "DIVISION SLASH", "REVERSE SOLIDUS"}:
                char = "/"
            characters.append(char)
            positions.append((cluster.start(), cluster.end()))
    return "".join(characters), positions


def _project_span(start, end, positions):
    return positions[start][0], positions[end - 1][1]


def _without_labels(text):
    characters, positions = [], []
    start = 0
    for label in _LABEL.finditer(text):
        for index in range(start, label.start()):
            characters.append(text[index])
            positions.append((index, index + 1))
        start = label.end()
    for index in range(start, len(text)):
        characters.append(text[index])
        positions.append((index, index + 1))
    return "".join(characters), positions


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


def _detected_spans(text, include_names=True):
    """Detecta sobre una vista canónica; sus offsets aún no son los del relato."""
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
    if not include_names:
        return spans
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
        if entity.label_ == "PER" and all(
            token.pos_ in {"DET", "PRON"}
            and set(token.morph.get("PronType")) & {"Int", "Rel", "Exc"}
            for token in entity
        ):
            # Una palabra con función interrogativa/exclamativa (p. ej. «Qué»)
            # no se convierte en nombre sólo por el error de la etiqueta NER.
            continue
        if entity.label_ in {"PER", "LOC"}:
            label = "[NOMBRE OCULTO]" if entity.label_ == "PER" else "[UBICACION OCULTA]"
            spans.append((entity.start_char, entity.end_char, label, 50))
    return spans


def sanitize_text(text: str) -> str:
    """Reduce PII conocida; los nombres se detectan por heurísticas, sin garantía de anonimato."""
    if not text:
        return ""
    if "\x00" in text:
        raise SanitizationAmbiguityError("El texto contiene un carácter nulo no permitido.")
    text = _normalize_for_detection(text)
    canonical, positions = _canonical_view(text)
    if not canonical:
        return text

    labels = list(_LABEL.finditer(canonical))
    protected = [_project_span(label.start(), label.end(), positions) for label in labels]
    spans = [
        (*_project_span(start, end, positions), label, priority)
        for start, end, label, priority in _detected_spans(canonical)
    ]

    if labels:
        # Las etiquetas legítimas permanecen protegidas. Si se intercalan para
        # dividir un identificador, detectarlo sin ellas permite ocultarlo entero.
        joined, joined_positions = _without_labels(canonical)
        split_words = [
            label for label in labels
            if label.start() and label.end() < len(canonical)
            and unicode_regex.fullmatch(r"[\p{L}\p{M}]", canonical[label.start() - 1])
            and unicode_regex.fullmatch(r"[\p{L}\p{M}]", canonical[label.end()])
        ]
        for start, end, label, _priority in _detected_spans(joined, include_names=bool(split_words)):
            left, right = _project_span(start, end, joined_positions)
            crossed = [item for item in labels if left < item.start() and right > item.end()]
            if not crossed:
                continue
            if label in {"[NOMBRE OCULTO]", "[UBICACION OCULTA]"} and not any(
                item in split_words for item in crossed
            ):
                continue
            original_left, original_right = _project_span(left, right, positions)
            protected = [
                (first, last) for first, last in protected
                if not (original_left <= first and original_right >= last)
            ]
            spans.append((original_left, original_right, label, 120))

    # Los identificadores y nombres contextuales ganan a entidades amplias.
    accepted = []
    for start, end, label, priority in sorted(spans, key=lambda item: (-item[3], -(item[1] - item[0]), item[0])):
        occupied = protected + [(left, right) for left, right, _ in accepted]
        if not any(start < right and end > left for left, right in occupied):
            accepted.append((start, end, label))
    for start, end, label in sorted(accepted, reverse=True):
        text = text[:start] + label + text[end:]
    return text
