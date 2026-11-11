# Evaluación cuantitativa del modelo — 11 de noviembre de 2026

## Resultado

Se ejecutó el pipeline real **Azure AI Language + Azure OpenAI/LangChain** sobre los 200 casos etiquetados del repositorio, sin cambiar el código ni las etiquetas durante la evaluación. Se obtuvieron 200 análisis disponibles, sin fallos, y la ejecución terminó con código de salida **0**.

| Criterio | Resultado | Referencia | Dictamen para esta corrida |
| --- | --- | --- | --- |
| Tamaño de muestra | 200 casos | Al menos 200 | Cumple |
| Accuracy de polaridad | **87.00%**, 174/200 | ≥85% | Cumple |
| Recall de banderas rojas | **100.00%**, 24/24 | ≥95% | Cumple |
| Cobertura de análisis | **100.00%**, 200/200 | Reportar disponibilidad | Sin análisis no disponibles |
| Latencia p95 | **2.1595 s** | <3 s como referencia del evaluador | Cumple la referencia p95 |

El MVP expresa inferencia menor de 3 segundos sin fijar percentil. **Una solicitud tardó 3.6086 s**, por lo que no se acredita que todas las solicitudes estén por debajo de 3 segundos. Esta corrida acredita p95 <3 s; la interpretación del criterio de evaluación debe acordarse con el maestro.

Evidencias: [JSON con las 200 predicciones](evaluacion_modelo_20261111_180516Z.json) y [salida de ejecución con código de salida](evaluacion_modelo_20261111_180516Z.log).

## Versión, entorno y trazabilidad

| Dato | Registro |
| --- | --- |
| Commit de la aplicación | `a9b1cd52a986ba4bd57a3601098fd15e29dac262` |
| Mensaje | `Limpia de codigo y soluciones` |
| Inicio de la invocación | `2026-11-11T18:05:16.2292918Z` / 10:05:16 en America/Los_Angeles |
| Generación del JSON | `2026-11-11T18:14:06.744431+00:00` / 10:14:06 local |
| Fin del comando | `2026-11-11T18:14:07.8676658Z` / 10:14:07 local |
| Duración total aproximada | 8 minutos 52 segundos; incluye contenedor y pausas entre casos |
| Ejecución | Codex, a solicitud del responsable del proyecto |
| Entorno | Windows/PowerShell, Docker Compose `plurione-demo`, contenedor Linux con Python `3.12.15` |
| Deployment configurado | `gpt-4.1-mini-1`; es el nombre del deployment, no una versión de modelo verificada por separado |
| Datos | `documentos/evaluacion_ia_200.csv` |
| Cambios locales al iniciar | README y bitácora/evidencias del ensayo manual; sin cambios en código de aplicación, evaluador ni conjunto etiquetado |

Los hashes del evaluador, motor, sanitizador y CSV coincidieron antes y después de la corrida:

| Archivo | SHA-256 |
| --- | --- |
| `scripts/evaluar_modelo.py` | `4E92982FF58C8AF8BB754561CAC484A0CE3A38F1935B6BAE56FC6C0602EA22B0` |
| `app/services/ai_engine.py` | `6E60D80BFD1E697B52A472E34171EB894755BC9431B5EDCB94020F12B9DD5822` |
| `app/services/sanitization.py` | `B1768C251C904F182270C459EEB609ACCA5C1EC6C978BDB52BD3975AE5A66439` |
| `documentos/evaluacion_ia_200.csv` | `7C3F4B2D2CF1DA944869837F0C1D8FB7A91E5C285B5DA552B5165C37F7451182` |
| JSON de esta evaluación | `3F057D208E43E0278B69E6F5C7FEE0E1E1693399333EEE64374F21AFEE5282C4` |

## Método y comprobaciones previas

1. Se revisó el procedimiento del README y la lógica del evaluador. Sus dos pruebas automatizadas pasaron: `Ran 2 tests in 0.002s`, `OK`, salida 0.
2. Se validaron 200 identificadores únicos, los campos obligatorios y las etiquetas. No se encontraron textos duplicados. Las 50 muestras de revisión coinciden en texto y etiquetas con el conjunto completo.
3. Se revisaron los 200 comentarios sintéticos y se ejecutó la sanitización local sin solicitudes externas. No hubo excepciones ni patrones residuales de correo, teléfono largo o URL en esa comprobación. El sanitizador modificó 37 casos; varias modificaciones corresponden a ubicaciones y otras son falsos positivos descritos debajo.
4. Se ejecutó el evaluador con las credenciales de Azure configuradas en el entorno, pausa de un segundo, mínimo de 200 casos y referencia p95 de 3 segundos. No se usaron respuestas simuladas para puntuar esta corrida.
5. Se recalcularon desde las predicciones guardadas el accuracy, cobertura, matriz de confusión, recall, falsos positivos, falsos negativos y latencias media/p95. Los resultados coincidieron con el JSON, admitiendo el redondeo de cuatro decimales por caso.

Comando ejecutado desde la raíz, con el repositorio montado en lectura y la carpeta de resultados habilitada para escritura:

```powershell
docker compose -p plurione-demo run --rm --no-deps -T `
  -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUNBUFFERED=1 `
  -v "${PWD}:/workspace:ro" -v "${PWD}/documentos:/results" -w /workspace `
  web python -u scripts/evaluar_modelo.py `
  --csv documentos/evaluacion_ia_200.csv `
  --output /results/evaluacion_modelo_20261111_180516Z.json `
  --delay-seconds 1 --min-samples 200 --target-latency-seconds 3
```

Para una nueva corrida debe utilizarse otro nombre de salida para conservar esta evidencia. El evaluador no insertó comentarios ni alertas en PostgreSQL. Los tres servicios de la demo siguieron activos al terminar, con la base de datos healthy.

## Composición y procedencia del conjunto

| Clase esperada | Casos |
| --- | --- |
| Positivo | 70 |
| Neutral | 60 |
| Negativo | 70 |
| Bandera roja esperada | 24, incluidos dentro de los 70 negativos |
| Sin bandera roja esperada | 176 |

El conjunto contiene 174 textos en español y 26 en inglés. Los ingleses corresponden a E061–E070, E123–E130 y E193–E200.

El README documenta generación con asistencia de Codex, revisión inicial del autor de los 200 casos y revisión de polaridad de 50 muestras por un compañero. Esta procedencia no demuestra una doble anotación ciega de los 200 ni una revisión independiente de todas las etiquetas de riesgo. Los resultados se comparan con las etiquetas existentes, que no se modificaron a partir de predicciones.

## Polaridad: matriz de confusión y errores

Filas: etiqueta esperada. Columnas: predicción del pipeline.

| Esperada / Predicha | Positivo | Neutral | Negativo | No disponible | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Positivo | 55 | 9 | 6 | 0 | 70 |
| Neutral | 0 | 58 | 2 | 0 | 60 |
| Negativo | 2 | 7 | 61 | 0 | 70 |

Se clasificaron correctamente 55/70 positivos (**78.57%**), 58/60 neutrales (**96.67%**) y 61/70 negativos (**87.14%**). El accuracy global cumple, aunque la identificación de positivos es el punto más débil.

Los **26 errores de polaridad** corresponden a: E006, E007, E008, E019, E031, E034, E038, E043, E048, E054, E057, E058, E059, E063, E067, E104, E120, E142, E159, E161, E164, E169, E172, E184, E185 y E197. El JSON conserva por caso la etiqueta esperada y la obtenida.

En el subconjunto de 50 casos revisados por el compañero se acertaron **42/50, 84.00%**. Es un resultado descriptivo de esa muestra incluida en los 200, no una segunda corrida ni una muestra suficiente para acreditar por separado el criterio de 200 casos. Conviene conservar este desglose junto al global.

## Banderas rojas

| Métrica | Resultado |
| --- | --- |
| Verdaderos positivos | 24 |
| Falsos negativos | 0 |
| Falsos positivos respecto a las etiquetas actuales | 3 |
| Verdaderos negativos | 173 |
| Recall | **100.00%** = 24/24 |
| Precision | **88.89%** = 24/27 |
| F1 | **94.12%** |

Las tres alertas adicionales fueron:

| Caso | Texto del conjunto sintético | Etiqueta esperada / predicción de riesgo |
| --- | --- | --- |
| E161 | Está pesado el jale cuando faltan instrucciones y nadie sabe a quién preguntar | Sin riesgo / Con riesgo |
| E169 | La carga aumentó pero seguimos con el mismo número de personas | Sin riesgo / Con riesgo |
| E175 | La pega se reparte de forma desigual y algunos terminan esperando | Sin riesgo / Con riesgo |

El recall alto no equivale a ausencia de falsas alarmas. Estas diferencias deben revisarse con un criterio humano estable sobre cuándo una queja organizacional amerita bandera roja; no deben cambiarse las etiquetas únicamente para mejorar el resultado.

## Latencia y disponibilidad

| Medida | Segundos |
| --- | ---: |
| Media | 1.6384 |
| p50 | 1.5739 |
| p95 | 2.1595 |
| Mínima | 1.2064 |
| Máxima | 3.6086 |

Solo E001 superó o igualó 3 segundos: **3.6086 s**. No se excluyó ese caso del cálculo. No se atribuye su demora a una causa específica sin una prueba adicional. El p95 utiliza el método de rango más próximo del evaluador.

La medición incluye sanitización local y las dos etapas de IA, con la sanitización de sus salidas. Excluye importación inicial de módulos, pausas entre casos, HTTP/UI de la aplicación y escritura en PostgreSQL. Fue una ejecución secuencial, no una prueba de concurrencia, carga sostenida ni entrega SMTP. Hubo **0 análisis no disponibles**, **0 excepciones reportadas** y salida de proceso **0**.

## Problemas observados y mejoras propuestas

### 1. Idioma implícito inglés en Azure AI Language

En [ai_engine.py, línea 80](../app/services/ai_engine.py#L80), `analyze_sentiment(documents=[texto_seguro])` no especifica idioma. Se inspeccionó el código y la documentación del SDK instalado: `TextAnalyticsClient` usa `en` cuando no se establece `default_language` ni un idioma por documento. Por tanto, los 174 textos españoles de esta corrida se enviaron con esa configuración implícita.

**Propuesta:** determinar el idioma de cada comentario y pasarlo explícitamente a Azure, conservando soporte para español e inglés. Verificar ambos idiomas con casos de regresión y repetir la evaluación en una corrida nueva. No se demuestra en esta corrida cuánto cambiaría el accuracy al corregirlo, porque no se efectuó una comparación controlada.

### 2. Falsos positivos del sanitizador que eliminan contenido útil

La inspección local de `sanitize_text`, usado en [evaluar_modelo.py, línea 104](../scripts/evaluar_modelo.py#L104), produjo estos ejemplos:

| Caso | Fragmento original | Resultado observado |
| --- | --- | --- |
| E008 | Qué padre que la empresa… | `[NOMBRE OCULTO] padre que la empresa…` |
| E025 | Qué buena onda que nos den tiempo… | `[UBICACION OCULTA] buena onda que nos den tiempo…` |
| E063 | The new schedule gives me a healthier balance between work and home | `The new schedule gives me a [NOMBRE OCULTO] between work and home` |
| E194 | My supervisor keeps making humiliating comments and I dread coming to work | `My supervisor [NOMBRE OCULTO] I dread coming to work` |

Son ocultaciones de expresiones ordinarias, no nombres de personas en esos casos. La corrección del caso del nombre después de «jefa», documentada en el ensayo manual, no acredita ausencia de estos falsos positivos.

**Propuesta:** mejorar las reglas y la selección lingüística del reconocimiento de entidades, y agregar regresiones que comprueben conservación del significado en ambos idiomas junto con la protección de nombres reales. E008 y E063 quedaron con polaridad incorrecta, pero no se atribuye causalidad exclusiva al sanitizador sin una comparación controlada. E194 conservó la detección de riesgo pese a perder contenido.

### 3. Margen de mejora de clasificación y falsas alarmas

Se mantienen 26 discrepancias de polaridad y tres de riesgo frente a las etiquetas existentes. La clase positiva presenta 78.57% de recuperación y la muestra de revisión de 50 casos alcanza 84% de accuracy.

**Propuesta:** revisar los desacuerdos con personas, definir mejor los criterios de riesgo y separar datos de calibración de un conjunto de evaluación independiente. Ajustar idioma, umbrales o instrucciones sobre el conjunto de calibración y medir después en datos reservados; conservar esta corrida como línea base.

## Alcance de la conclusión

El código actual cumple **accuracy ≥85% y recall ≥95% en este conjunto de 200**, y cumple la **referencia p95 <3 s**. Se conservan los errores y limitaciones sin modificar las etiquetas ni el código para aprobar la prueba. El resultado no sustituye las comprobaciones manuales de roles, CSV, persistencia de alertas ni una auditoría de seguridad, y no garantiza esos porcentajes en comentarios reales o bajo carga.
