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

La generación actual de alertas crea únicamente alertas de nivel `ALTO`; por ello, el filtro de la bandeja ofrece ese nivel y no muestra opciones `MEDIO` o `BAJO` que el backend todavía no genera.

## Flujo

~~~text
Buzón → validación y sanitización → análisis IA → PostgreSQL → métricas y alertas
~~~

Los comentarios no se asocian a una cuenta de empleado. La sanitización combina patrones, contexto y reconocimiento lingüístico; incluye regresiones para nombres en minúsculas sin acentos, nombres separados por etiquetas y saltos de línea. Sigue siendo heurística y no garantiza reconocer cualquier identificador en texto libre. El análisis apoya la revisión humana; no constituye una conclusión sobre una persona.

Un RFC con una posible homoclave separada por espacios puede confundirse con palabras del comentario. En esos casos el buzón responde `422` y solicita retirar el identificador antes de enviarlo: no lo almacena ni llama a IA. En CSV se marca la fila como fallida y se continúa con las demás. Los folios de diez dígitos se ocultan preventivamente como `[NUMERO OCULTO]`, porque el texto libre no permite verificar que no sean un teléfono. No se conservan por el simple hecho de que el remitente los llame «pedido» o «folio». Las correcciones no reescriben automáticamente registros históricos.

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
   | SMTP_ALERT_RECIPIENT | Destinatario requerido si se habilita el envío de alertas por correo. No hay destinatario predeterminado. |
   | RATE_LIMIT_STORAGE_URI | Almacenamiento del límite de solicitudes; `memory://` para una instancia local. Configure Redis para varias réplicas. |
   | RATE_LIMIT_LOGIN | Límite del inicio de sesión. Predeterminado: `5/minute`. |
   | RATE_LIMIT_FEEDBACK | Límite de envío de comentarios al buzón. Predeterminado: `5/minute`. |
   | RATE_LIMIT_CSV_UPLOAD | Límite de carga de archivos CSV. Predeterminado: `3/minute`. |

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

La API permite solicitudes del navegador desde estos orígenes exactos: `http://localhost:5173`, `http://127.0.0.1:5173` y `http://localhost:3000`. El esquema, el nombre del host y el puerto forman parte del origen. Si Vite elige otro puerto porque el 5173 está ocupado, libera el puerto y reinicia el frontend, o configura explícitamente el origen correspondiente en `app/main.py`. `VITE_API_BASE_URL` cambia la dirección de la API utilizada por el frontend, pero no modifica CORS.

La configuración actual de Compose publica los puertos 8000 y 5173 en todas las interfaces del equipo. Para restringir una demo al equipo local, cambia sus mapeos en `docker-compose.yml` a `127.0.0.1:8000:8000` y `127.0.0.1:5173:5173`, respectivamente, y recrea los servicios. CORS no limita el acceso a los puertos desde la red.

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

## Crear usuarios para la demo

Con los servicios activos, crea por separado los usuarios que usarás para probar los permisos:

~~~sh
docker compose exec web python -m app.create_user_cli
~~~

El asistente solicita correo, rol y contraseña dos veces (la contraseña no se muestra al escribirla). Los roles admitidos son `hr`, `analyst` y `executive`; escribe el rol que quieras crear. El script normaliza el correo a minúsculas, rechaza correos duplicados, requiere una contraseña de al menos 12 caracteres y limita su tamaño a 72 bytes UTF-8 por el algoritmo bcrypt. Las contraseñas se guardan con hash bcrypt.

Ejecuta el comando una vez por cada cuenta que necesites. Para la demo, ejecútalo tres veces y crea una cuenta de cada rol (`hr`, `analyst` y `executive`); el CLI pide el correo y rol en texto y la contraseña dos veces sin mostrarla. Usa correos distintos y guarda las credenciales de prueba de forma segura. El script no crea administradores: para crear el primer `admin`, usa `python -m app.create_admin_cli`. No existe registro público de usuarios. Conserva el acceso al contenedor y las contraseñas de prueba solo con las personas que participen en la demo.

## Límites de solicitudes

Los límites predeterminados se aplican por dirección IP:

| Acción | Límite predeterminado | Endpoint |
| --- | --- | --- |
| Inicio de sesión | 5 solicitudes por minuto | `POST /api/v1/auth/login` |
| Envío de comentario | 5 solicitudes por minuto | `POST /api/v1/nlp/analyze-feedback` |
| Carga CSV | 3 solicitudes por minuto | `POST /api/v1/nlp/upload-csv` |

Al exceder un límite, la API responde HTTP `429 Too Many Requests`; espera a que se renueve el periodo antes de reintentar. Los valores se pueden cambiar en `.env` con `RATE_LIMIT_LOGIN`, `RATE_LIMIT_FEEDBACK` y `RATE_LIMIT_CSV_UPLOAD`, usando la sintaxis de SlowAPI, por ejemplo `10/minute` o `2/minute`. Recrea el servicio `web` después de editar `.env` para que cargue las nuevas variables:

~~~sh
docker compose up -d --force-recreate web
~~~

El almacenamiento predeterminado `memory://` mantiene contadores en memoria del proceso y los reinicia al reiniciar la API. Para varias réplicas, configura `RATE_LIMIT_STORAGE_URI` con una URL de Redis accesible desde el contenedor (por ejemplo `redis://redis:6379`) y agrega/conecta Redis a la misma red de Docker. Si la API está detrás de un proxy, configura el proxy para conservar correctamente la IP del cliente; el limitador usa la dirección que ve FastAPI. Los límites protegen por IP y no representan una cuota global de llamadas a Azure.

## Buzón y carga CSV

El buzón es público. Acepta comentarios de 5 a 3000 caracteres y requiere al menos una palabra de dos letras. El departamento es opcional. El texto se sanitiza antes de almacenarlo y analizarlo.

La respuesta del buzón incluye `analysis_available`: `true` si el comentario fue analizado y `false` si se guardó sin análisis disponible. La interfaz muestra el primer resultado en verde y el segundo como advertencia en ámbar. Los avisos permanecen visibles hasta el siguiente envío válido. El login y el buzón muestran el `detail` del servidor ante un límite 429, con un mensaje de respaldo si falta.

El CSV debe estar en UTF-8 e incluir la columna text_content. El límite es 5 MB. También se admiten is_anonymous y department_id; el MVP solo importa comentarios anónimos.

~~~csv
text_content,is_anonymous,department_id
"La carga de trabajo ha sido muy alta esta semana",true,2
"El equipo tiene buena comunicación",true,1
~~~

La importación corre en segundo plano dentro del proceso web, procesa filas secuencialmente y no tiene una cola durable. Si el backend se reinicia durante la tarea, no existe garantía de reanudación. El tamaño del archivo está limitado a 5 MB y se examinan como máximo 1000 filas de datos, sin contar la cabecera. Las filas omitidas o fallidas también cuentan para ese máximo. Si hay más de 1000 filas, se detiene el procesamiento al alcanzar el límite, las restantes no se importan y el resumen muestra una advertencia; no se rechaza todo el archivo por ese motivo.

Cuando la importación termina correctamente o con observaciones, el panel vuelve a consultar las métricas del filtro seleccionado y las alertas, regresando a la primera página de la bandeja. No es necesario recargar la página. Una carga fallida muestra un error y no se presenta como completada.

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
| GET /api/v1/alerts/ | Consulta alertas paginadas (`page`, `page_size`, máximo 100); requiere JWT y rol autorizado. La respuesta indica si hay otra página en `X-Has-More`. |
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
docker compose exec web python -X pycache_prefix=/tmp/plurione-pycache -m compileall -q app
~~~

Estas comprobaciones verifican dependencias y sintaxis; no sustituyen una validación funcional integral.

La imagen del backend contiene `app/`, pero no incluye los archivos `test_*.py` ni `scripts/`. Para ejecutar las suites con sus dependencias dentro de Docker, monta el repositorio como solo lectura en un contenedor temporal. Desde la raíz del proyecto, en PowerShell:

~~~powershell
docker compose run --rm --no-deps -v "${PWD}:/workspace:ro" -w /workspace web python -m unittest -v test_api_hardening test_ai_engine_validation test_sanitization_regression test_feedback_response test_privacy test_mvp_acceptance test_csv_import test_alerts test_email_service test_model_evaluation
~~~

En macOS/Linux:

~~~sh
docker compose run --rm --no-deps -v "$PWD:/workspace:ro" -w /workspace web python -m unittest -v test_api_hardening test_ai_engine_validation test_sanitization_regression test_feedback_response test_privacy test_mvp_acceptance test_csv_import test_alerts test_email_service test_model_evaluation
~~~

Para ejecutar solo privacidad, conserva el mismo comando y deja `test_sanitization_regression test_privacy` después de `-v`. Estas suites cubren nombres tras cargos, conservación del contexto, correos Unicode, teléfonos con separadores, RFC, CURP, etiquetas existentes, doble sanitización y aplicación antes de guardar o analizar, además de salidas generadas por IA y supresión de distribuciones pequeñas. La detección sigue siendo heurística: no garantiza reconocer cualquier nombre o identificador. Los registros históricos no se modifican automáticamente con una corrección del sanitizador. También puedes ejecutar `python -m unittest -v ...` directamente desde la raíz en un entorno local con Python 3.12 y las dependencias del backend instaladas y configuradas; no ejecutes ese comando dentro de la imagen sin montar los archivos.

Si utilizas el proyecto de demo, agrega `-p plurione-demo` después de `docker compose` en estos comandos. `npm run lint` y `npm run build` se ejecutan desde `frontend/`. Las pruebas unitarias usan datos de prueba y dobles; no sustituyen la evaluación del modelo con comentarios etiquetados. Registra los resultados de una nueva ejecución sobre la versión que vas a presentar; las bitácoras anteriores fueron retiradas.

El motor exige de 3 a 5 frases clave únicas en la respuesta original de IA. Después de sanitizar pueden quedar menos: se devuelven solo las frases seguras, sin relleno artificial, y se registra `metadata_ai.key_phrases_suppressed`. Las colisiones se comparan sin distinguir mayúsculas y normalizando espacios. Una frase ambigua se omite; una explicación de riesgo que no puede sanitizarse conserva el comportamiento de análisis no disponible.

Las suites `test_ai_engine_validation` y `test_api_hardening` cubren catálogos, explicación obligatoria de riesgos, supresión de frases, puntuaciones inválidas, JWT sin expiración, entradas extremas y archivos CSV mal formados. Los límites de paginación son una protección transitoria: alertas admite páginas entre 1 y 10000, con un máximo de 100 resultados por página.

### Evaluación cuantitativa del modelo

#### Procedencia y revisión de las etiquetas

Los 200 comentarios del conjunto `documentos/evaluacion_ia_200.csv` fueron generados con asistencia de Codex. Julio Alfonso Monteverde Esquer realizó una primera revisión de los 200 comentarios y sus etiquetas el 21 de octubre de 2026. En esa revisión no se modificó el archivo. Después se seleccionaron al azar 50 posiciones del CSV original: 4, 5, 10, 11, 12, 19, 23, 27, 29, 33, 38, 41, 45, 48, 54, 59, 63, 68, 71, 76, 82, 85, 87, 88, 91, 95, 99, 102, 108, 113, 119, 124, 128, 134, 137, 142, 144, 147, 150, 156, 161, 167, 170, 175, 178, 182, 189, 195, 198 y 200. Corresponden a los casos E004, E005, E010, E011, E012, E019, E023, E027, E029, E033, E038, E041, E045, E048, E054, E059, E063, E068, E071, E076, E082, E085, E087, E088, E091, E095, E099, E102, E108, E113, E119, E124, E128, E134, E137, E142, E144, E147, E150, E156, E161, E167, E170, E175, E178, E182, E189, E195, E198 y E200 del archivo de 200 casos.

El compañero de residencias Bryan Julian Tanori Duarte revisó esas 50 muestras y confirmó que las etiquetas de polaridad existentes (Positivo, Neutral o Negativo) eran correctas. La fecha de esta revisión no fue proporcionada. El archivo `documentos/evaluacion_ia_50_seleccionados.csv` conserva las etiquetas esperadas; por ello, esta revisión de una muestra aleatoria no demuestra por sí sola un etiquetado ciego e independiente ni valida las etiquetas `expected_red_flag`. No se reportó una matriz de desacuerdos porque el revisor indicó que las 50 etiquetas de polaridad eran correctas.

Se aplicaron estos criterios para la polaridad:

- **Positivo:** comentarios no agresivos que expresan aspectos favorables de la empresa o describen un buen clima laboral.
- **Neutral:** comentarios que no son claramente positivos ni agresivos, incluidos comentarios regulares que señalan algunos problemas.
- **Negativo:** comentarios que expresan insultos, problemas, quejas o abusos.

La revisión completa inicial y la comprobación independiente de una muestra aleatoria documentan la procedencia y revisión humana de las etiquetas; la comprobación de 50 casos no sustituye una segunda anotación ciega de los 200 casos.

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

#### Nueva corrida de evaluación

La [evaluación del 11 de noviembre de 2026](documentos/evaluacion_modelo_2026-11-11.md), con el commit `a9b1cd52a986ba4bd57a3601098fd15e29dac262` y Azure real, obtuvo **87% de accuracy (174/200), 100% de recall de banderas rojas (24/24), 100% de cobertura y p95 de 2.1595 s**. Se conservan el [JSON por caso](documentos/evaluacion_modelo_20261111_180516Z.json) y la [salida de ejecución](documentos/evaluacion_modelo_20261111_180516Z.log). Hubo 26 errores de polaridad y tres falsos positivos de riesgo respecto a las etiquetas actuales. Una solicitud tardó 3.6086 s; p95 <3 s no significa que todas cumplan ese tiempo. El informe documenta el idioma inglés implícito del SDK, falsos positivos de sanitización y los límites del conjunto etiquetado.

Los informes históricos anteriores fueron retirados. Para futuras versiones, repite el procedimiento y conserva una salida con nombre nuevo: estos resultados corresponden únicamente al código y al conjunto identificados en el informe.

### Archivo de prueba funcional

Para el recorrido funcional puedes utilizar `documentos/comentarios_sinteticos_2026-10-17.csv`. Comprueba en la nueva ejecución las filas procesadas, omitidas y fallidas y la disponibilidad real del análisis. Importar comentarios no sustituye la medición de accuracy, recall y latencia contra etiquetas humanas.

### Recorrido manual para la evaluación

#### Ensayo desde cero

Las bitácoras e informes anteriores fueron retirados. Realiza este recorrido con los archivos actuales y guarda una nueva bitácora únicamente después de ejecutar las pruebas, en `documentos/ensayo_demo_<fecha>.md`. Registra lo que realmente ocurra, incluidos fallos o pasos no comprobados.

La [bitácora del 11 de noviembre de 2026](documentos/ensayo_demo_2026-11-11.md) documenta el ensayo del commit `a9b1cd52a986ba4bd57a3601098fd15e29dac262`: cinco envíos del caso de nombre después del cargo con ocultación correcta, verificaciones técnicas, métricas y alerta atendida. Conserva las evidencias, una observación sobre la claridad del motivo de alerta y los pasos pendientes de confirmación.

Los pasos siguientes usan el proyecto separado `plurione-demo`. Todos sus comandos llevan `-p plurione-demo` para distinguirlo de la instalación habitual. Antes de repetir el ensayo, conserva cualquier dato del entorno de demo que necesites: `docker compose -p plurione-demo down -v` elimina sus volúmenes, incluidas cuentas, comentarios, alertas, importaciones y dependencias del frontend de ese proyecto.

1. Detén la instalación habitual para liberar los puertos y comprueba el entorno de demo:

   ~~~sh
   docker compose down
   docker compose -p plurione-demo ps -a
   ~~~

   **Reinicio opcional para un ensayo desde cero:** solo si todos los datos de `plurione-demo` son desechables, ejecuta `docker compose -p plurione-demo down -v`. Borra cuentas, comentarios, alertas e importaciones de ese proyecto. Si deseas conservarlos, omite ese comando y reutiliza las cuentas existentes; las métricas incluirán datos anteriores.

2. Verifica que `.env` esté configurado. Registra el commit, las modificaciones locales y las versiones de Docker antes de levantar los servicios:

   ~~~sh
   git rev-parse HEAD
   git status --short
   docker --version
   docker compose version
   docker compose -p plurione-demo up --build -d
   docker compose -p plurione-demo ps
   ~~~

   Guarda esas salidas en la bitácora. Si hay cambios locales, el commit por sí solo no identifica todo el código probado: registra qué archivos cambiaron y conserva el diff sin incluir secretos. Confirma que `db`, `web` y `frontend` estén activos. Si `web` no inicia, revisa `docker compose -p plurione-demo logs web` y `docker compose -p plurione-demo logs db` antes de continuar.

3. Abre `http://localhost:8000/docs` y confirma que la API responde. Crea las cuentas de demo dentro del contenedor:

   ~~~sh
   docker compose -p plurione-demo exec web python -m app.create_admin_cli
   docker compose -p plurione-demo exec web python -m app.create_user_cli
   docker compose -p plurione-demo exec web python -m app.create_user_cli
   docker compose -p plurione-demo exec web python -m app.create_user_cli
   ~~~

   Si conservaste el entorno y esas cuentas ya existen, reutilízalas. En un entorno vacío, el primer comando crea el administrador inicial. En cada una de las tres ejecuciones siguientes escribe un correo único, selecciona respectivamente `hr`, `analyst` y `executive`, y captura la contraseña dos veces. Cada contraseña debe tener al menos 12 caracteres y no superar 72 bytes UTF-8. No escribas contraseñas en la bitácora.

4. Prueba cada cuenta en `http://localhost:5173/login`, cerrando sesión antes de cambiar de usuario:

   | Cuenta | Comprobaciones esperadas |
   | --- | --- |
   | `admin` | Entra al panel; ve la bandeja de alertas y puede cargar CSV. |
   | `hr` | Entra al panel; ve la bandeja de alertas y puede cargar CSV. |
   | `analyst` | Entra al panel; ve la bandeja de alertas y puede cargar CSV. |
   | `executive` | Entra al panel y consulta métricas; no ve ni puede consultar la bandeja de alertas ni cargar CSV. |

   Para comprobar también la autorización del servidor, abre Swagger en `http://localhost:8000/docs`, usa **Authorize** con la cuenta `executive` y ejecuta las rutas restringidas. La API debe responder `403` si intenta consultar `GET /api/v1/alerts/` o `POST /api/v1/nlp/upload-csv`. El buzón de comentarios es público y no requiere iniciar sesión.

5. Envía comentarios sintéticos desde `http://localhost:5173/`. No uses información real de empleados. Para que aparezcan métricas, necesitas al menos cinco comentarios con análisis de Azure disponible; un comentario guardado como no analizado no cuenta para esos agregados.

   Realiza la comprobación de sanitización descrita debajo. Después carga `documentos/comentarios_sinteticos_2026-10-17.csv` con un rol autorizado e identifica el archivo y la cantidad de filas en la bitácora. Espera el resumen final y registra cuántas se procesaron, omitieron o fallaron y si hubo avisos de análisis pendiente. Selecciona el departamento importado y el mes actual. Comprueba si las métricas y alertas se actualizan al terminar la carga sin recargar la página; si requieren recarga manual, anótalo como incidencia.

6. Envía `PRUEBA DEMO: La carga laboral excesiva me provoca agotamiento y deseo renunciar.` y confirma si Azure genera una alerta de nivel ALTO. Cambia su estado de Pendiente a En revisión y después a Atendida; recarga y comprueba que persiste. Si no se genera, registra el resultado real y revisa si el análisis estuvo disponible. Si quieres verificar el correo, revisa el buzón de prueba y los logs; que exista una alerta no confirma que el correo haya sido entregado.

7. Espera un minuto después de tu último inicio de sesión y comprueba el límite intentando iniciar sesión seis veces dentro del mismo minuto; el sexto intento debe mostrar el aviso de espera en vez del mensaje de credenciales incorrectas. El límite predeterminado es por IP y es `5/minute`.

8. Registra fecha, responsable, sistema operativo, versiones de Docker, commit y modificaciones locales, resultado de cada rol, filtros y métricas visibles, cambios de alerta y su persistencia tras recargar, resumen CSV y errores en `documentos/ensayo_demo_<fecha>.md`. Adjunta capturas o salidas reales con su fecha e indica si Azure y SMTP fueron reales, simulados o no comprobados. Conserva las evidencias referenciadas en el repositorio, sin contraseñas, tokens, llaves ni datos personales.

El ensayo acredita el flujo de uso y permisos en ese entorno; no sustituye la evaluación cuantitativa del modelo. Los umbrales de accuracy, recall y latencia se miden con el conjunto etiquetado y el procedimiento descrito arriba.

#### Comprobación manual de sanitización

En el paso 5, envía este comentario ficticio desde el buzón, seleccionando un departamento:

~~~text
PRUEBA DEMO ACTUAL: Mi jefa Ana López me humilla en las juntas. Mi correo es demo@example.test y mi telefono 6621234567.
~~~

Si Azure está disponible, el aviso debe indicar que fue analizado; si se guardó sin análisis, registra la advertencia. Comprueba lo almacenado con esta consulta de solo lectura desde PowerShell:

~~~powershell
@'
from app.db.database import SessionLocal
from app.db.models import FeedbackEntry
with SessionLocal() as db:
    entries = db.query(FeedbackEntry).filter(
        FeedbackEntry.content_text.contains("PRUEBA DEMO ACTUAL")
    ).order_by(FeedbackEntry.created_at.desc()).limit(10).all()
    for entry in entries:
        print(entry.id, entry.content_text)
'@ | docker compose -p plurione-demo exec -T web python -
~~~

El nombre, correo y teléfono deben quedar ocultos, preservando el sentido de la frase. Si el resultado difiere o no aparece el registro, anótalo como incidencia; el aviso de guardado no demuestra por sí solo que la sanitización sea correcta.

Prueba después `Mi RFC es ABCD 123456 XYZ.`: el buzón debe mostrar el aviso de identificador ambiguo (HTTP 422), sin guardar ese comentario ni enviarlo a IA. Un texto corto como `hola` y otro exclusivamente numérico como `1234567` deben rechazarse. Las pruebas automatizadas cubren más variantes; la detección continúa siendo heurística.

Al terminar, puedes conservar los datos de la nueva demo deteniéndola sin `-v` y volver a la instalación habitual:

~~~sh
docker compose -p plurione-demo down
docker compose up -d
~~~

### Diagnóstico rápido

- **La API no inicia:** revisa `JWT_SECRET_KEY`, los valores PostgreSQL y que las tres variables `*_URLENCODED` correspondan a las credenciales codificadas para URL.
- **El análisis queda como no disponible:** revisa endpoint, llave y nombre del despliegue Azure en `.env`, y consulta `docker compose logs web`.
- **No llega el correo:** confirma host, puerto, usuario, contraseña SMTP y destinatario; revisa los logs. El sistema no reintenta automáticamente ni guarda el estado de entrega del correo.
- **No aparece una métrica:** confirma que haya al menos cinco análisis válidos en el rango filtrado; la IA debe haber producido polaridad, no basta con que el comentario esté guardado.

## Informes de revisión actuales

Los seis tipos de registros históricos se conservan en estas versiones del **11 de noviembre de 2026**, asociadas al commit `a9b1cd52a986ba4bd57a3601098fd15e29dac262`:

| Registro | Archivo actual |
| --- | --- |
| Log de QA integrado | [qa_sistema_20261111.log](documentos/qa_sistema_20261111.log) |
| Pruebas funcionales del sistema | [pruebas_sistema_2026-11-11.md](documentos/pruebas_sistema_2026-11-11.md) |
| Evaluación del modelo por caso | [evaluacion_modelo_20261111_180516Z.json](documentos/evaluacion_modelo_20261111_180516Z.json) |
| Auditoría funcional, de seguridad y arquitectura | [evaluacion_completa_2026-11-11.md](documentos/evaluacion_completa_2026-11-11.md) |
| Bitácora de demo con evidencia manual y ampliación automatizada | [ensayo_demo_2026-11-11.md](documentos/ensayo_demo_2026-11-11.md) |
| Análisis de errores del modelo | [analisis_errores_modelo_20261111.md](documentos/analisis_errores_modelo_20261111.md) |

La repetición obtuvo **55 pruebas unitarias y 76 comprobaciones integradas correctas**, además de un recorrido de navegador con los cuatro roles, persistencia de alerta, resumen CSV, actualización automática del panel y aviso 429. Las comprobaciones adversas también encontraron fallos; consulta la auditoría para conocerlos. Se reutiliza la evaluación real de 200 casos del mismo día y código, documentada en el [informe del modelo](documentos/evaluacion_modelo_2026-11-11.md); no representa una segunda corrida. Las capturas y registros nuevos se conservan en `documentos/evidencias_revision_2026-11-11/`.

## Estructura

- app/api/v1/endpoints/: autenticación, comentarios, métricas y alertas.
- app/core/: validación de JWT y límites de solicitudes.
- app/db/: conexión y modelos SQLAlchemy.
- app/schemas/: validación y contratos de API.
- app/services/: IA, sanitización y correo.
- frontend/src/pages/: buzón, login y panel.
- documentos/PRD.md y documentos/MVP.md: requisitos y alcance.

## Uso de herramientas de IA

El desarrollo contó con asistencia de IA generativa (Codex) para solucionar errores menores, apoyar la auditoría del código y de seguridad, y generar scripts de pruebas. El autor revisó los cambios y participó en las pruebas. En las nuevas bitácoras se debe distinguir qué comprobaciones fueron automatizadas y cuáles fueron realizadas o confirmadas manualmente por el autor; los resultados corresponden a esas ejecuciones y no constituyen una certificación externa.

## Alcance y limitaciones

Entra ID y Power BI quedan fuera del MVP. Docker Compose sirve el frontend con el servidor de desarrollo Vite. Antes de publicar, configura un servidor de producción, HTTPS, control de acceso y gestión segura de secretos. Ejecutar el flujo no demuestra por sí solo los umbrales de precisión del PRD; estos requieren un conjunto de comentarios etiquetados.
