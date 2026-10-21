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
   | OPENAI_API_VERSION | Está en la plantilla, pero el código actual no consume esta variable. |
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

## Alcance y limitaciones

Entra ID y Power BI quedan fuera del MVP. Docker Compose sirve el frontend con el servidor de desarrollo Vite. Antes de publicar, configura un servidor de producción, HTTPS, control de acceso y gestión segura de secretos. Ejecutar el flujo no demuestra por sí solo los umbrales de precisión del PRD; estos requieren un conjunto de comentarios etiquetados.
