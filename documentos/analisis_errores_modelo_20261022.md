# Análisis de errores de la evaluación oficial

## Fuente y resultados

Este análisis usa la corrida oficial `evaluacion_modelo_20261022_025516Z.json`, realizada sobre 200 comentarios sintéticos. El reporte obtuvo 173 clasificaciones correctas (accuracy 86.5%), recall de banderas rojas de 24/24 (100%), cobertura de 199/200 (99.5%) y latencia p95 de 1.9938 segundos. Los tres umbrales configurados se cumplieron. La latencia máxima fue 12.2637 segundos, un caso atípico que no cambia el resultado del p95.

Hubo 26 discrepancias de polaridad y un análisis no disponible:

| Etiqueta esperada | Predicción | Casos | Cantidad |
| --- | --- | --- | ---: |
| Positivo | Neutral | E008, E031, E038, E043, E048, E057, E059, E063, E067 | 9 |
| Positivo | Negativo | E006, E007, E019, E034, E054, E058 | 6 |
| Neutral | Negativo | E104, E120 | 2 |
| Negativo | Neutral | E142, E159, E161, E172, E184, E185, E197 | 7 |
| Negativo | Positivo | E164, E169 | 2 |
| Neutral | No disponible | E127 | 1 |

## Patrones observados

- **Modismos y regionalismos:** comentarios positivos con expresiones coloquiales como “se rifa” (E006), “está chido” (E007), “chévere” (E043), “bárbaro” (E057), “bacán” (E059) y “tela” (E054) se clasificaron como neutrales o negativos. Conviene medir el desempeño con español regional y coloquial.
- **Inglés:** E063 y E067 son comentarios positivos en inglés que se clasificaron como neutrales; E197 es negativo en inglés y también quedó neutral. Conviene medir por separado comentarios en inglés y declarar qué idiomas cubre el MVP.
- **Polaridad indirecta o moderada:** algunos mensajes expresan apoyo, mejoras o una condición laboral problemática sin adjetivos muy explícitos. Por ejemplo, E031 valora que se diera crédito al equipo, mientras E164 señala que el comedor es pequeño. Estos matices pueden confundirse con neutralidad.
- **Descripciones factuales interpretadas como negativas:** E104 (“El laburo del turno tarde comienza a las dos”) y E120 (“El periodo de prueba concluye después de noventa días”) eran neutrales, pero se predijeron como negativos. Conviene revisar si existen términos que el modelo asocia indebidamente con problemas.
- **Quejas operativas clasificadas como neutrales:** E159, E172, E184 y E185 describen duplicación de tareas, comunicación difícil, aprobaciones excesivas o fallas de una herramienta. El modelo no siempre separa esos problemas de una descripción neutral. La guía de etiquetado debería precisar qué nivel de impacto convierte una queja operativa en sentimiento negativo.
- **Análisis no disponible:** E127 (“My shift starts at seven and ends at three”) no recibió una polaridad. El proceso registró un timeout de Azure OpenAI durante el lote, pero el JSON no asocia el error a un `case_id`; el evaluador solo guarda `error_type` cuando la excepción sale del pipeline. En este caso, el pipeline devolvió el estado de análisis no disponible.

## Falsos positivos de bandera roja

El recall fue 100% (no hubo falsos negativos) y hubo dos falsos positivos:

| Caso | Polaridad esperada → predicha | Comentario | Observación |
| --- | --- | --- | --- |
| E161 | Negativo → Neutral | “Está pesado el jale cuando faltan instrucciones y nadie sabe a quién preguntar” | Expresa dificultad laboral y falta de orientación. Revisar si la definición de bandera roja incluye este problema operativo. |
| E169 | Negativo → Positivo | “La carga aumentó pero seguimos con el mismo número de personas” | Describe más carga sin aumentar el personal. Revisar si la definición de bandera roja excluye sobrecarga o posible agotamiento. |

Estos dos casos pueden apuntar tanto a límites del modelo como a una definición de bandera roja que necesita mayor precisión. Conviene acordar el criterio operacional antes de ajustar el prompt o la lógica.

## Conclusión

En esta corrida, las principales oportunidades de mejora están en el reconocimiento de modismos, comentarios en inglés, quejas expresadas indirectamente y continuidad ante timeouts. El modelo cumplió los umbrales de accuracy, recall y p95, aunque un caso quedó sin análisis y la latencia máxima fue mayor que el p95. Antes de ajustar el modelo, se recomienda precisar los criterios de etiquetado, revisar los casos límite con una segunda persona y seguir registrando cobertura y errores por caso.
