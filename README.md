# Sistema de análisis de sentimiento organizacional

PluriOne es una aplicación web para recopilar comentarios sobre el entorno laboral, sanitizar datos personales comunes, analizarlos con IA y presentar resultados agregados y alertas para Recursos Humanos.

## Funciones

- Buzón anónimo con selección opcional de departamento.
- Sanitización de correos, teléfonos, RFC y entidades detectadas por spaCy.
- Análisis con LangChain y Azure OpenAI. Si el proveedor no está disponible, el comentario se guarda sin inventar una puntuación.
- Persistencia en PostgreSQL de comentarios sanitizados, análisis, frases clave, alertas e importaciones CSV.
- Inicio de sesión local con JWT y permisos por rol: admin, hr, analyst y executive.
- Panel React con volumen, distribución y promedio de polaridad, emociones, ejes, frases frecuentes, promedios por departamento y tendencia diaria.
- Gestión de alertas y carga de CSV.

## Flujo

~~~text
Buzón → validación y sanitización → análisis IA → PostgreSQL → métricas y alertas
~~~

Los comentarios no se asocian a una cuenta de empleado. La sanitización es heurística y puede no detectar todos los datos identificables. El análisis apoya la revisión humana; no constituye una conclusión sobre una persona.

## Requisitos

- Docker Desktop con Docker Compose v2, o Docker Engine y el complemento docker compose.
- Acceso a Azure AI Language y Azure OpenAI para análisis real. Si falta cualquiera de las cuatro variables de servicio requeridas o falla una llamada, el comentario se guarda sin análisis disponible.
- Credenciales SMTP válidas para enviar correos de alerta.

## Configurar el entorno

1. Copia .env.example como .env desde la raíz del repositorio.

   PowerShell:

   ~~~powershell
   Copy-Item .env.example .env
   ~~~

   macOS/Linux:

   ~~~sh
   cp .env.example .env
   ~~~

2. Completa en .env estas variables:

   | Variables | Uso |
   | --- | --- |
   | JWT_SECRET_KEY | Clave de firma JWT de al menos 32 bytes. Genera una con python -c "import secrets; print(secrets.token_urlsafe(48))". |
   | POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB | Credenciales y nombre de la base PostgreSQL. |
   | POSTGRES_USER_URLENCODED, POSTGRES_PASSWORD_URLENCODED, POSTGRES_DB_URLENCODED | Los mismos valores codificados para URL; Compose los usa para crear DATABASE_URL. Codifica caracteres especiales, por ejemplo @ como %40. |
   | AZURE_OPENAI_ENDPOINT | Endpoint Azure OpenAI v1, incluido el sufijo `/openai/v1/`; por ejemplo `https://<recurso>.openai.azure.com/openai/v1/`. |
   | AZURE_OPENAI_API_KEY | Llave del servicio de IA. |
   | AZURE_OPENAI_DEPLOYMENT_NAME | Nombre exacto del despliegue disponible en el recurso. Si se omite, el código usa `gpt-4.1-mini-1`, que debe existir como deployment. |
   | AZURE_LANGUAGE_ENDPOINT | Endpoint del recurso Azure AI Language, por ejemplo `https://<recurso>.cognitiveservices.azure.com/`. |
   | AZURE_LANGUAGE_KEY | Llave del recurso Azure AI Language. |
   | SMTP_HOST, SMTP_PORT, SMTP_TIMEOUT_SECONDS | Servidor y parámetros SMTP. Los valores predeterminados usan Gmail con STARTTLS. |
   | SMTP_EMAIL, SMTP_PASSWORD | Cuenta remitente y contraseña aceptada por SMTP. Para Gmail usa una contraseña de aplicación. |
   | SMTP_ALERT_RECIPIENT | Destinatario de alertas; si queda vacío, el código usa rh@plurione.com. |

Para codificar valores URL, usa Python: python -c "from urllib.parse import quote; print(quote('valor', safe=''))". En Docker Compose, DATABASE_URL se construye con las variables URLENCODED y puede quedar vacía en .env. Si ejecutas el backend fuera de Docker, configura DATABASE_URL directamente.

No compartas ni subas .env al repositorio. Usa secretos distintos para desarrollo y producción. Una contraseña SMTP incompatible con el servidor provoca un error de autenticación.

## Iniciar con Docker

Desde la raíz del proyecto:

~~~sh
docker compose up --build
~~~

La primera ejecución construye la imagen e instala dependencias. Revisa los servicios con:

~~~sh
docker compose ps
~~~

Los servicios `db`, `web` y `frontend` deben aparecer como activos. La API espera a que PostgreSQL pase su healthcheck antes de iniciar. Si `web` no inicia, revisa `docker compose logs web` y `docker compose logs db`.

Direcciones locales:

- Buzón: http://localhost:5173/
- Inicio de sesión: http://localhost:5173/login
- Panel: http://localhost:5173/dashboard
- Swagger/OpenAPI: http://localhost:8000/docs
- API: http://localhost:8000/

Registros del backend:

~~~sh
docker compose logs -f web
~~~

Detener los contenedores sin borrar el volumen de datos:

~~~sh
docker compose down
~~~

PostgreSQL conserva datos en postgres_data. Al iniciar, la aplicación ejecuta Base.metadata.create_all() y completa los departamentos de muestra que falten si sus IDs están disponibles. create_all() crea tablas faltantes, pero no sustituye migraciones para cambios en tablas existentes.

Para una instalación antigua que todavía no tenga `alerts.updated_at` y `alerts.updated_by`, ejecuta una vez la migración manual incluida:

~~~sh
docker compose exec web python -m app.migrate_db
~~~

Este script agrega únicamente esas dos columnas. Haz respaldo de la base antes de ejecutar cambios de esquema y revisa `docker compose logs web` si la operación falla. No es un sistema general de migraciones versionadas; `create_all()` tampoco modifica tablas existentes.

## Crear el primer administrador

Con los servicios activos, inicia el asistente dentro del contenedor:

~~~sh
docker compose exec web python -m app.create_admin_cli
~~~

Escribe el correo y la contraseña cuando se soliciten. La contraseña se almacena con hash bcrypt. Entra al sistema desde http://localhost:5173/login. No hay una ruta pública para registrar administradores.

El asistente CLI solo permite crear el administrador inicial y rechaza contraseñas de menos de 12 caracteres. No expongas el acceso al contenedor a usuarios no confiables.

## Buzón y carga CSV

El buzón es público. Acepta comentarios de 5 a 3000 caracteres y requiere al menos una palabra de dos letras. El departamento es opcional. El texto se sanitiza antes de almacenarlo y analizarlo.

El CSV debe estar en UTF-8 e incluir la columna text_content. El límite es 5 MB. También se admiten is_anonymous y department_id; el MVP solo importa comentarios anónimos.

~~~csv
text_content,is_anonymous,department_id
"La carga de trabajo ha sido muy alta esta semana",true,2
"El equipo tiene buena comunicación",true,1
~~~

La importación corre en segundo plano dentro del proceso web, procesa filas secuencialmente y no tiene una cola durable. Si el backend se reinicia durante la tarea, no existe garantía de reanudación. El tamaño del archivo está limitado a 5 MB, pero el código no fija un máximo de filas.

## Métricas y privacidad

El panel filtra por departamento y fechas. Los agregados generales se ocultan cuando hay menos de cinco análisis válidos. La distribución por sentimiento se oculta completa si alguna categoría tiene menos de cinco respuestas, para evitar deducir su valor por diferencia. Emociones, ejes, frases clave, promedios por departamento y tendencia diaria sólo muestran grupos con al menos cinco respuestas. El endpoint no devuelve el texto de los comentarios.

Polaridad: negativa hasta -0.25; neutral de -0.24 a +0.24; positiva desde +0.25. Las métricas son descriptivas y dependen de la calidad del análisis de IA.

## Rutas principales

La documentación interactiva y los esquemas completos están en http://localhost:8000/docs.

| Método y ruta | Descripción |
| --- | --- |
| POST /api/v1/auth/login | Inicia sesión y devuelve un JWT. |
| GET /api/v1/nlp/departments | Lista los departamentos. |
| POST /api/v1/nlp/analyze-feedback | Valida, sanitiza, analiza y guarda un comentario. |
| GET /api/v1/nlp/stats | Agregados de sentimiento, temas y tendencia para un departamento y un mes calendario completos; requiere JWT. `department_id=0` representa comentarios sin departamento. |
| POST /api/v1/nlp/upload-csv | Inicia una importación CSV; requiere JWT y rol autorizado. |
| GET /api/v1/nlp/upload-csv/{import_id} | Consulta el estado de una importación; requiere JWT y rol autorizado. |
| GET /api/v1/alerts/ | Consulta alertas; requiere JWT y rol autorizado. |
| PATCH /api/v1/alerts/{alert_id} | Actualiza el estado de una alerta; requiere JWT y rol autorizado. |

La bandeja de alertas y la carga CSV están permitidas a `admin`, `hr` y `analyst`. Las métricas aceptan además `executive`. El buzón y el catálogo de departamentos son públicos. No hay actualmente filtros de autorización por departamento asociados a cada usuario.

Las métricas se consultan por celdas no solapadas (departamento y mes calendario) para impedir comparaciones entre filtros superpuestos. Si algún día del mes tiene entre una y cuatro respuestas, se oculta toda la tendencia diaria. La distribución de sentimiento también se oculta completa si alguna etiqueta tiene menos de cinco respuestas. Los resúmenes ejecutivos y la exportación no forman parte de este MVP.

## Verificaciones

Desde frontend:

~~~sh
npm run lint
npm run build
~~~

En el contenedor del backend:

~~~sh
docker compose exec web pip check
docker compose exec web python -m compileall -q app
~~~

Estas comprobaciones verifican dependencias y sintaxis; no sustituyen una validación funcional integral.

La suite de regresión de privacidad se ejecuta desde la raíz con `python -m unittest -v test_privacy`. Cubre sanitización de PII, salidas generadas por IA y supresión de distribuciones pequeñas.

Para ejecutar todas las suites actuales desde la raíz del repositorio:

~~~sh
python -m unittest -v test_privacy test_mvp_acceptance test_csv_import test_alerts test_email_service test_model_evaluation
~~~

`npm run lint` y `npm run build` se ejecutan desde `frontend/`. Las pruebas unitarias usan datos de prueba y dobles; no sustituyen la evaluación del modelo con comentarios etiquetados.

### Evaluación cuantitativa del modelo

#### Procedencia y revisión de las etiquetas

Los 200 comentarios del conjunto `documentos/evaluacion_ia_200.csv` fueron generados con asistencia de Codex. Julio Alfonso Monteverde Esquer realizó una primera revisión de los 200 comentarios y sus etiquetas el 21 de octubre de 2026. En esa revisión no se modificó el archivo. Se aplicaron estos criterios para la polaridad:

- **Positivo:** comentarios no agresivos que expresan aspectos favorables de la empresa o describen un buen clima laboral.
- **Neutral:** comentarios que no son claramente positivos ni agresivos, incluidos comentarios regulares que señalan algunos problemas.
- **Negativo:** comentarios que expresan insultos, problemas, quejas o abusos.

La revisión documenta la procedencia y el criterio aplicado; no equivale a una validación independiente por una segunda persona.

El MVP fija `accuracy ≥85%` para polaridad y `recall ≥95%` para banderas rojas con un conjunto de al menos 200 comentarios etiquetados. Las etiquetas esperadas deben asignarlas y revisarlas personas; no uses predicciones de IA como etiquetas de referencia. El CSV de evaluación debe incluir:

~~~csv
case_id,text_content,expected_sentiment,expected_red_flag
E001,"El equipo se apoya y comparte sus conocimientos",Positivo,false
E002,"La carga de trabajo me provoca agotamiento constante",Negativo,true
~~~

Valores permitidos para `expected_sentiment`: `Positivo`, `Neutral` o `Negativo`. Para `expected_red_flag`: `true/false`, `sí/no` o `1/0`. No incluyas nombres ni datos personales. El evaluador sanitiza el texto antes de llamar a Azure; guarda por caso solo el identificador, las etiquetas y la latencia.

Instala las dependencias del backend en un entorno local con Python 3.12 (la misma versión de la imagen Docker), configura `.env` con llaves reales de ambos servicios Azure y ejecuta desde la raíz:

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/evaluar_modelo.py --csv documentos/evaluacion_ia_200.csv
~~~

El script exige 200 casos por defecto, pausa un segundo entre comentarios y escribe un JSON con accuracy, recall, cobertura, matriz de confusión y latencias media/p50/p95 por caso en `documentos/`. Los análisis no disponibles cuentan como incorrectos para accuracy y como falsos negativos si el caso esperado era una bandera roja. La latencia reportada incluye sanitización local y las dos etapas de IA; excluye UI, HTTP de la aplicación y escritura en PostgreSQL. Cada caso invoca Azure AI Language y Azure OpenAI, así que la ejecución consume cuota y puede generar cargos. Un p95 inferior a 3 segundos es una referencia operativa para el criterio del MVP; confirma con el maestro qué percentil evaluará.

#### Corrida oficial

La corrida oficial es `documentos/evaluacion_modelo_20261022_025516Z.json`, generada el 22 de octubre de 2026 a las 02:55 UTC. Sobre 200 comentarios obtuvo accuracy de 86.5% (173/200), recall de banderas rojas de 100% (24/24), latencia p95 de 1.9938 segundos y cobertura de 99.5% (199/200). Cumplió los tres umbrales configurados: accuracy ≥85%, recall ≥95% y p95 <3 segundos. Un análisis no estuvo disponible y se contó como error; la latencia máxima fue 12.2637 segundos, aunque el p95 quedó bajo el objetivo. Las llamadas a IA pueden producir resultados distintos entre corridas.

### Evidencia de Azure en QA

En la prueba de QA con `documentos/comentarios_sinteticos_2026-10-17.csv`, la importación terminó con 25/25 comentarios procesados, 0 omitidos y 0 fallidos. Los 25 tuvieron análisis disponible: 9 positivos, 8 neutrales y 8 negativos; la polaridad media fue `+0.0452` (el panel la muestra como `+0.05`). Esto verifica el flujo integrado con la configuración Azure usada en QA. La muestra de 25 no demuestra los umbrales de accuracy/recall del MVP, y esa ejecución no midió latencia.

### Recorrido manual para la evaluación

1. Comprueba que `docker compose ps` muestre PostgreSQL, API y frontend activos.
2. Abre `/docs` y confirma que la API responde.
3. Crea el usuario inicial con el comando CLI y entra desde `/login`.
4. Envía comentarios sintéticos desde el buzón. No uses información real de empleados durante una demostración.
5. Con al menos cinco comentarios que sí hayan sido analizados por Azure OpenAI, comprueba las métricas del dashboard. Si falta la llave o Azure falla, el sistema guarda el comentario como no analizado y no lo incluye en esos agregados.
6. Envía un comentario de prueba que active una alerta y verifica el registro en la bandeja. Para comprobar la entrega del correo, revisa el buzón de prueba y los logs; que exista una alerta no confirma que el correo haya sido enviado.
7. Registra el resultado y el entorno de cada prueba. El MVP establece objetivos de latencia, accuracy y recall, pero estos deben medirse aparte con carga y un conjunto etiquetado.

### Diagnóstico rápido

- **La API no inicia:** revisa `JWT_SECRET_KEY`, los valores PostgreSQL y que las tres variables `*_URLENCODED` correspondan a las credenciales codificadas para URL.
- **El análisis queda como no disponible:** revisa endpoint, llave y nombre del despliegue Azure en `.env`, y consulta `docker compose logs web`.
- **No llega el correo:** confirma host, puerto, usuario, contraseña SMTP y destinatario; revisa los logs. El sistema no reintenta automáticamente ni guarda el estado de entrega del correo.
- **No aparece una métrica:** confirma que haya al menos cinco análisis válidos en el rango filtrado; la IA debe haber producido polaridad, no basta con que el comentario esté guardado.

## Estructura

- app/api/v1/endpoints/: autenticación, comentarios, métricas y alertas.
- app/core/: validación de JWT.
- app/db/: conexión y modelos SQLAlchemy.
- app/schemas/: validación y contratos de API.
- app/services/: IA, sanitización y correo.
- frontend/src/pages/: buzón, login y panel.
- documentos/PRD.md y documentos/MVP.md: requisitos y alcance.

## Uso de herramientas de IA

El desarrollo contó con asistencia de IA generativa (Codex). El autor revisó y ejecutó las pruebas y verificaciones descritas; los resultados reportados corresponden a las ejecuciones indicadas, no a una certificación externa.

## Alcance y limitaciones

Entra ID y Power BI quedan fuera del MVP. Docker Compose sirve el frontend con el servidor de desarrollo Vite. Antes de publicar, configura un servidor de producción, HTTPS, control de acceso y gestión segura de secretos. Ejecutar el flujo no demuestra por sí solo los umbrales de precisión del PRD; estos requieren un conjunto de comentarios etiquetados.
