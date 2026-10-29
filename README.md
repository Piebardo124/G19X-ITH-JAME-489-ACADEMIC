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

Al exceder un límite, la API responde HTTP `429 Too Many Requests`; espera a que se renueve el periodo antes de reintentar. Los valores se pueden cambiar en `.env` con `RATE_LIMIT_LOGIN`, `RATE_LIMIT_FEEDBACK` y `RATE_LIMIT_CSV_UPLOAD`, usando la sintaxis de SlowAPI, por ejemplo `10/minute` o `2/minute`. Reinicia el servicio `web` después de editar `.env`:

~~~sh
docker compose restart web
~~~

El almacenamiento predeterminado `memory://` mantiene contadores en memoria del proceso y los reinicia al reiniciar la API. Para varias réplicas, configura `RATE_LIMIT_STORAGE_URI` con una URL de Redis accesible desde el contenedor (por ejemplo `redis://redis:6379`) y agrega/conecta Redis a la misma red de Docker. Si la API está detrás de un proxy, configura el proxy para conservar correctamente la IP del cliente; el limitador usa la dirección que ve FastAPI. Los límites protegen por IP y no representan una cuota global de llamadas a Azure.

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

#### Corrida oficial

La corrida oficial es `documentos/evaluacion_modelo_20261022_025516Z.json`, generada el 22 de octubre de 2026 a las 02:55 UTC. Sobre 200 comentarios obtuvo accuracy de 86.5% (173/200), recall de banderas rojas de 100% (24/24), latencia p95 de 1.9938 segundos y cobertura de 99.5% (199/200). Cumplió los tres umbrales configurados: accuracy ≥85%, recall ≥95% y p95 <3 segundos. Un análisis no estuvo disponible y se contó como error; la latencia máxima fue 12.2637 segundos, aunque el p95 quedó bajo el objetivo. Las llamadas a IA pueden producir resultados distintos entre corridas.

### Evidencia de Azure en QA

En la prueba de QA con `documentos/comentarios_sinteticos_2026-10-17.csv`, la importación terminó con 25/25 comentarios procesados, 0 omitidos y 0 fallidos. Los 25 tuvieron análisis disponible: 9 positivos, 8 neutrales y 8 negativos; la polaridad media fue `+0.0452` (el panel la muestra como `+0.05`). Esto verifica el flujo integrado con la configuración Azure usada en QA. La muestra de 25 no demuestra los umbrales de accuracy/recall del MVP, y esa ejecución no midió latencia.

### Recorrido manual para la evaluación

#### Ensayo desde cero

El [ensayo manual del 29 de octubre de 2026](documentos/ensayo_demo_2026-10-29.md) documenta la creación de cuentas para los cuatro roles, permisos en pantalla, carga de 200 comentarios, métricas, alertas, buzón y aviso 429 de login, según las confirmaciones del usuario durante el recorrido.

Para conservar una instalación existente, el ensayo usó un proyecto separado con volúmenes nuevos: `docker compose down` y después `docker compose -p plurione-demo up --build -d`. En ese caso, todos los comandos posteriores deben incluir `-p plurione-demo`, por ejemplo `docker compose -p plurione-demo exec web python -m app.create_user_cli`. Al finalizar puedes detenerlo con `docker compose -p plurione-demo down` y volver a la instalación habitual con `docker compose up -d`; los volúmenes se conservan.

Haz este ensayo solo con una base de datos desechable. `docker compose down -v` elimina el volumen `postgres_data`, incluidas cuentas, comentarios, alertas e importaciones existentes del proyecto.

1. Detén el proyecto y borra su volumen de datos de demo:

   ~~~sh
   docker compose down -v
   ~~~

2. Verifica que `.env` esté configurado y levanta los servicios:

   ~~~sh
   docker compose up --build -d
   docker compose ps
   ~~~

   Confirma que `db`, `web` y `frontend` estén activos. Si `web` no inicia, revisa `docker compose logs web` y `docker compose logs db` antes de continuar.

3. Abre `http://localhost:8000/docs` y confirma que la API responde. Crea las cuentas de demo dentro del contenedor:

   ~~~sh
   docker compose exec web python -m app.create_admin_cli
   docker compose exec web python -m app.create_user_cli
   docker compose exec web python -m app.create_user_cli
   docker compose exec web python -m app.create_user_cli
   ~~~

   En el primer comando crea el administrador inicial. En cada una de las tres ejecuciones siguientes escribe un correo único, selecciona respectivamente `hr`, `analyst` y `executive`, y captura la contraseña dos veces. Cada contraseña debe tener al menos 12 caracteres y no superar 72 bytes UTF-8. No escribas contraseñas en la bitácora.

4. Prueba cada cuenta en `http://localhost:5173/login`, cerrando sesión antes de cambiar de usuario:

   | Cuenta | Comprobaciones esperadas |
   | --- | --- |
   | `admin` | Entra al panel; ve la bandeja de alertas y puede cargar CSV. |
   | `hr` | Entra al panel; ve la bandeja de alertas y puede cargar CSV. |
   | `analyst` | Entra al panel; ve la bandeja de alertas y puede cargar CSV. |
   | `executive` | Entra al panel y consulta métricas; no ve ni puede consultar la bandeja de alertas ni cargar CSV. |

   Para la comprobación de permisos, la API debe responder `403` si `executive` intenta consultar `GET /api/v1/alerts/` o `POST /api/v1/nlp/upload-csv`. El buzón de comentarios es público y no requiere iniciar sesión.

5. Envía comentarios sintéticos desde `http://localhost:5173/`. No uses información real de empleados. Para que aparezcan métricas, necesitas al menos cinco comentarios con análisis de Azure disponible; un comentario guardado como no analizado no cuenta para esos agregados.

6. Envía un comentario sintético que active una alerta y confirma que aparece en la bandeja con el estado correspondiente. Si quieres verificar el correo, revisa el buzón de prueba y los logs; que exista una alerta no confirma que el correo haya sido entregado.

7. Espera un minuto después de tu último inicio de sesión y comprueba el límite intentando iniciar sesión seis veces dentro del mismo minuto; el sexto intento debe mostrar el aviso de espera en vez del mensaje de credenciales incorrectas. El límite predeterminado es por IP y es `5/minute`.

8. Registra fecha, sistema operativo, versiones de Docker, resultado de cada rol, métricas visibles, alerta y errores en `documentos/ensayo_demo_<fecha>.md`. No incluyas contraseñas, tokens ni datos personales.

El ensayo acredita el flujo de uso y permisos en ese entorno; no sustituye la evaluación cuantitativa del modelo. Los umbrales de accuracy, recall y latencia se miden con el conjunto etiquetado y el procedimiento descrito arriba.

### Diagnóstico rápido

- **La API no inicia:** revisa `JWT_SECRET_KEY`, los valores PostgreSQL y que las tres variables `*_URLENCODED` correspondan a las credenciales codificadas para URL.
- **El análisis queda como no disponible:** revisa endpoint, llave y nombre del despliegue Azure en `.env`, y consulta `docker compose logs web`.
- **No llega el correo:** confirma host, puerto, usuario, contraseña SMTP y destinatario; revisa los logs. El sistema no reintenta automáticamente ni guarda el estado de entrega del correo.
- **No aparece una métrica:** confirma que haya al menos cinco análisis válidos en el rango filtrado; la IA debe haber producido polaridad, no basta con que el comentario esté guardado.

## Estructura

- app/api/v1/endpoints/: autenticación, comentarios, métricas y alertas.
- app/core/: validación de JWT y límites de solicitudes.
- app/db/: conexión y modelos SQLAlchemy.
- app/schemas/: validación y contratos de API.
- app/services/: IA, sanitización y correo.
- frontend/src/pages/: buzón, login y panel.
- documentos/PRD.md y documentos/MVP.md: requisitos y alcance.

## Uso de herramientas de IA

El desarrollo contó con asistencia de IA generativa (Codex). El autor revisó y ejecutó las pruebas y verificaciones descritas; los resultados reportados corresponden a las ejecuciones indicadas, no a una certificación externa.

## Alcance y limitaciones

Entra ID y Power BI quedan fuera del MVP. Docker Compose sirve el frontend con el servidor de desarrollo Vite. Antes de publicar, configura un servidor de producción, HTTPS, control de acceso y gestión segura de secretos. Ejecutar el flujo no demuestra por sí solo los umbrales de precisión del PRD; estos requieren un conjunto de comentarios etiquetados.
