# Ensayo manual de la demo — 29 de octubre de 2026

## Procedencia de la evidencia

Julio realizó el recorrido manual en Windows/PowerShell, guiado en el chat, y confirmó los resultados indicados abajo. La salida de construcción y creación de contenedores se pegó en el chat; los resultados de interfaz se registran según sus confirmaciones, sin atribuirles una inspección automática adicional. Las pruebas automáticas anteriores están documentadas por separado en [pruebas_sistema_2026-10-29.md](pruebas_sistema_2026-10-29.md).

## Instalación con base vacía

La instalación habitual estaba activa y PostgreSQL aparecía saludable. `docker compose -p plurione-demo ps -a` no mostró contenedores previos. Se utilizó un proyecto Compose separado para partir de una base vacía y conservar el volumen de la instalación habitual.

Secuencia indicada durante el ensayo:

```powershell
docker compose down
docker compose -p plurione-demo up --build -d
docker compose -p plurione-demo ps
```

La salida compartida de `up` confirmó:

- Imagen `plurione-demo-web` construida utilizando la caché de Docker.
- Red `plurione-demo_default` creada.
- Volúmenes nuevos `plurione-demo_postgres_data` y `plurione-demo_frontend_node_modules` creados.
- Contenedor `plurione-demo-db-1` saludable y servicios `web` y `frontend` iniciados.
- El usuario confirmó que el buzón y `http://localhost:8000/docs` abrieron correctamente.

El procedimiento parte de una base nueva; no se afirma una instalación en una máquina sin imágenes ni dependencias en caché. Las versiones exactas de Docker y Compose no se adjuntaron al chat.

## Cuentas y permisos

El usuario confirmó la creación del administrador mediante:

```powershell
docker compose -p plurione-demo exec web python -m app.create_admin_cli
```

Después ejecutó el asistente siguiente para crear tres cuentas con los roles `hr`, `analyst` y `executive`, y confirmó la creación de las tres:

```powershell
docker compose -p plurione-demo exec web python -m app.create_user_cli
```

Al cerrar sesión y cambiar de cuenta, confirmó los controles esperados de cada rol:

| Rol | Métricas | Bandeja de alertas | Carga CSV | Resultado comunicado |
| --- | --- | --- | --- | --- |
| admin | Visible | Visible | Visible | Correcto |
| hr | Visible | Visible | Visible | Correcto |
| analyst | Visible | Visible | Visible | Correcto |
| executive | Visible | Ausente | Ausente | Correcto |

Este recorrido confirma los permisos visibles en pantalla. El rechazo HTTP 403 de operaciones no autorizadas se comprobó en las pruebas integradas anteriores, no se repitió manualmente desde Swagger en este ensayo. No se guardan contraseñas, correos de las cuentas ni tokens en esta bitácora.

## CSV, métricas y alertas

- El usuario reportó una carga final de **200 comentarios**, todos aceptados, sin avisos de «comentario guardado; análisis de IA pendiente».
- El panel mostró una polaridad promedio de **−0.05** en el filtro utilizado. No se registraron el departamento ni el filtro temporal exactos; este valor documenta lo observado y no es un valor esperado universal para cualquier filtro.
- Confirmó que la bandeja permitió cambiar el estado de una alerta. No se adjuntó una captura ni una confirmación separada de persistencia después de recargar.
- No se verificó la entrega de correos reales en una bandeja de entrada.

La aceptación de filas y la ausencia de avisos se registran según el resultado visible comunicado por el usuario; no se inspeccionó cada análisis directamente en PostgreSQL durante este recorrido.

## Buzón público

Se solicitó enviar, seleccionando un departamento, el comentario sintético:

> PRUEBA DEMO: El equipo colabora con respeto y las herramientas nos ayudan a realizar el trabajo.

El usuario confirmó el comportamiento solicitado: botón en estado de procesamiento, mensaje de comentario recibido y analizado correctamente y limpieza del formulario al terminar. No reportó errores en este paso.

## Límite de inicio de sesión

Se indicó cerrar sesión, esperar un minuto y realizar seis intentos con contraseña incorrecta dentro de un minuto, con el límite predeterminado `5/minute` por IP. El usuario confirmó que apareció:

> Demasiados Intentos. Por favor, espera unos minutos.

El aviso 429 del buzón no se ejercitó manualmente en este ensayo; su respuesta API ya se comprobó en las pruebas integradas anteriores.

## Resultado y alcance

El ensayo aporta evidencia manual de instalación con volúmenes nuevos, creación de los cuatro roles mediante los asistentes, permisos visibles, carga CSV de 200 comentarios, métricas, gestión de una alerta, envío por el buzón y aviso de límite en el login. Los resultados fueron confirmados por el usuario durante el recorrido.

Quedan fuera de esta evidencia la entrega SMTP real, una nueva evaluación estadística de accuracy/recall, mediciones de latencia y carga sostenida, y el etiquetado ciego independiente de los 50 casos solicitado por el maestro. La bitácora no implica que los riesgos de arquitectura señalados en la auditoría hayan sido corregidos.
