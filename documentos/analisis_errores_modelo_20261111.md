# Análisis de errores del modelo — 11 de noviembre de 2026

Fuente: [JSON real de 200 casos](evaluacion_modelo_20261111_180516Z.json), generado el 11 de noviembre de 2026 a las 18:14:06 UTC para el commit `a9b1cd52a986ba4bd57a3601098fd15e29dac262`. Este documento analiza esa corrida actual; no reproduce cifras del informe retirado de octubre ni representa una segunda llamada al lote de 200.

## Resultados

Accuracy **87% (174/200)**, recall **100% (24/24)**, cobertura **100%**, media **1.6384 s**, p95 **2.1595 s**, máximo **3.6086 s**. Precision de riesgo **88.89% (24/27)** y F1 **94.12%**. Los objetivos de accuracy, recall y referencia p95 se cumplen en este conjunto, con una solicitud superior a tres segundos.

| Esperada | Predicha | Casos | Cantidad |
| --- | --- | --- | ---: |
| Positivo | Neutral | E008, E031, E038, E043, E048, E057, E059, E063, E067 | 9 |
| Positivo | Negativo | E006, E007, E019, E034, E054, E058 | 6 |
| Neutral | Negativo | E104, E120 | 2 |
| Negativo | Neutral | E142, E159, E161, E172, E184, E185, E197 | 7 |
| Negativo | Positivo | E164, E169 | 2 |
| Cualquiera | No disponible | Ninguno | 0 |

Total: **26 errores de polaridad**. Se recuperaron 55/70 positivos (78.57%), 58/60 neutrales (96.67%) y 61/70 negativos (87.14%). La submuestra de 50 casos revisada por el compañero obtuvo **42/50 (84%)**; está incluida en los 200 y no constituye una evaluación independiente.

## Patrones observados

- Modismos positivos: E006 («se rifa»), E007 («chidos»), E043 («chévere»), E054 («tela»), E057 («bárbaro») y E059 («bacán») aparecen entre los errores. No se ha aislado la contribución del idioma o de la sanitización a cada discrepancia.
- Polaridad indirecta: reconocimiento del equipo (E031), coordinación favorable (E038) y planificación del trabajo (E067) fueron predichos como neutrales; quejas operativas E159, E172, E184 y E185 también quedaron neutrales.
- Descripciones neutrales: E104 y E120 se clasificaron como negativas pese a sus etiquetas neutrales actuales.
- Inglés: E063 y E067 eran positivos y quedaron neutrales; E197 era negativo y quedó neutral. El conjunto incluye 26 textos ingleses y 174 españoles.
- Riesgo y polaridad son salidas distintas: E142 quedó neutral, pero mantuvo la bandera roja correcta. E169 quedó positivo y, aun así, generó una alerta adicional respecto a la etiqueta de referencia.

## Hallazgos de configuración y preprocesamiento

**Idioma:** `app/services/ai_engine.py:80` no pasa idioma a `analyze_sentiment`. La inspección del SDK instalado confirmó el predeterminado inglés `en`. Conviene determinar y enviar explícitamente el idioma de cada texto; fijar español para todos tampoco cubre correctamente un conjunto bilingüe. La mejora de accuracy debe medirse en una comparación posterior, no suponerse.

**Ocultaciones de expresiones ordinarias:** se verificaron localmente E008 (`Qué` → nombre oculto), E025 (`Qué` → ubicación oculta), E063 (`healthier balance` → nombre oculto) y E194 (se elimina parte del relato de acoso). E008 y E063 tuvieron polaridad incorrecta; E194 mantuvo sentimiento y riesgo correctos. Son señales de pérdida de contexto, sin prueba causal aislada sobre las predicciones.

**Disponibilidad:** no hubo casos sin análisis. E127, que figuraba como no disponible en un informe antiguo, tiene resultado disponible en este JSON actual; el informe histórico no se utiliza como resultado de la nueva versión.

## Falsos positivos de riesgo

| Caso | Comentario sintético | Resultado |
| --- | --- | --- |
| E161 | Está pesado el jale cuando faltan instrucciones y nadie sabe a quién preguntar | Esperado sin riesgo; predicho con riesgo |
| E169 | La carga aumentó pero seguimos con el mismo número de personas | Esperado sin riesgo; predicho con riesgo |
| E175 | La pega se reparte de forma desigual y algunos terminan esperando | Esperado sin riesgo; predicho con riesgo |

No hubo falsos negativos respecto a las 24 etiquetas positivas. Los tres falsos positivos se definen con relación al etiquetado actual: deben revisarse los criterios humanos de sobrecarga, agotamiento y problemas operativos antes de modificar instrucciones o etiquetas. El recall por sí solo no mide las falsas alarmas.

## Acciones propuestas

1. Corregir el idioma explícito por comentario y comprobar español e inglés.
2. Agregar pruebas de conservación del significado al sanitizador, junto con regresiones de protección de identificadores; no basta el caso de nombre después de «jefa».
3. Revisar con personas los 26 desacuerdos y precisar cuándo una queja activa riesgo; no reemplazar etiquetas por predicciones para mejorar la puntuación.
4. Separar un conjunto de calibración de otro reservado para evaluación, incluyendo modismos regionales y más casos de riesgo. Solo hay 24 positivos de riesgo en este conjunto sintético.
5. Medir nuevas corridas comparables después de cambios, conservando esta línea base y reportando también máximo, cobertura, precision y F1.

Los detalles de método, hashes, latencia y límites de anotación están en la [evaluación cuantitativa](evaluacion_modelo_2026-11-11.md). Estos resultados no garantizan el mismo desempeño en datos reales ni bajo concurrencia.
