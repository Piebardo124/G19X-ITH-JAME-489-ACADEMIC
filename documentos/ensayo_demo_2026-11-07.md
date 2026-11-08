# Ensayo manual de la demo — 7 de noviembre de 2026

## Estado del ensayo

**Ensayo con incidencia de sanitización; pendiente de corrección y repetición.** Julio indicó que siguió el recorrido del README y compartió la consulta de los comentarios guardados desde el buzón. Esa evidencia confirma que el correo se ocultó, pero el nombre ficticio «Ana López» permaneció en los cinco registros consultados.

Esta bitácora reemplaza la del ensayo manual anterior, retirada del repositorio. La bitácora histórica de pruebas automatizadas del 29 de octubre se conserva por separado; sus resultados no se atribuyen a este ensayo.

## Código de referencia

- Commit: `74a7cc49fbc7e3581e6868fc51e255c5135cf793`.
- Mensaje: `Arreglos en documentos`.
- Fecha del commit: 7 de noviembre de 2026, 21:13:21, UTC−08:00.
- Al preparar esta bitácora, el árbol de trabajo estaba limpio. El documento y su enlace en el README se agregan después de ese commit.
- No se adjuntó el identificador de la imagen o del contenedor ejecutado durante el ensayo.

## Entorno y procedimiento seguido

Entorno indicado durante el recorrido: Windows/PowerShell y Docker Compose, con el proyecto separado `plurione-demo`. El usuario manifestó haber seguido los pasos del README. La secuencia indicada fue:

1. Detener la instalación habitual y preparar los volúmenes vacíos de `plurione-demo`.
2. Registrar el estado de Git y las versiones de Docker e iniciar los servicios con `docker compose -p plurione-demo up --build -d`.
3. Ejecutar las pruebas directas de `sanitize_text` para nombres, RFC, correo y teléfono.
4. Crear el administrador y las cuentas `hr`, `analyst` y `executive`, y comprobar sus controles en pantalla.
5. Enviar el comentario sintético por el buzón y consultar el texto persistido en PostgreSQL.
6. Comprobar CSV, métricas, actualización del panel, alertas y el límite de inicio de sesión, según el recorrido del README.

La salida detallada compartida para esta ejecución corresponde al paso del buzón y a su consulta en la base de datos. No se adjuntaron salidas individuales de arranque, versiones, permisos, RFC, CSV, métricas, alertas ni 429; por ello, no se certifican sus resultados específicos en esta bitácora. Se registrarán expresamente en la siguiente demo.

## Prueba del buzón y de persistencia

Texto sintético utilizado:

> PRUEBA DEMO: Mi jefa Ana López me humilla en las juntas. Mi correo es prueba@example.test.

Después de enviarlo desde el buzón, se ejecutó la consulta indicada de los últimos cinco comentarios de la base de demo. El usuario compartió:

```text
1f2e0b25-142e-4ac7-bffc-5938e071f8fd 'PRUEBA DEMO: Mi jefa Ana L\xf3pez me humilla en las juntas. Mi correo es [CORREO OCULTO].'
90752e6b-48f3-485c-8def-d7e26a0c124c 'PRUEBA DEMO: Mi jefa Ana L\xf3pez me humilla en las juntas. Mi correo es [CORREO OCULTO].'
482f4c32-7c0d-4a95-b545-c0609aa74ef5 'PRUEBA DEMO: Mi jefa Ana L\xf3pez me humilla en las juntas. Mi correo es [CORREO OCULTO].'
4fb35094-46df-440c-ab72-91e010cfebb7 'PRUEBA DEMO: Mi jefa Ana L\xf3pez me humilla en las juntas. Mi correo es [CORREO OCULTO].'
5773c4a9-c62f-43dc-b5ca-246dece7243d 'PRUEBA DEMO: Mi jefa Ana L\xf3pez me humilla en las juntas. Mi correo es [CORREO OCULTO].'
```

`\xf3` representa la letra «ó» en la salida de `ascii()`; no es un mecanismo de ocultación ni cifrado.

| Comprobación | Resultado observado |
| --- | --- |
| Recepción y persistencia de comentarios del buzón | Confirmadas por los cinco registros compartidos |
| Ocultación del correo | Correcta en los cinco registros: `[CORREO OCULTO]` |
| Ocultación del nombre ficticio | **Fallida**: «Ana López» permanece legible en los cinco registros |

Resultado esperado para este caso:

```text
PRUEBA DEMO: Mi jefa [NOMBRE OCULTO] me humilla en las juntas. Mi correo es [CORREO OCULTO].
```

La consulta confirma el fallo en el texto almacenado. No constituye una captura del tráfico enviado a Azure ni demuestra, por sí sola, qué análisis devolvieron los servicios externos en esta ejecución.

## Corrección y próximo ensayo

Se volverá a realizar una demo después de resolver el problema de ocultación del nombre. Antes de repetirla:

1. Corregir la detección de nombres en contexto, incluyendo «Mi jefa Ana López…», y agregar pruebas de regresión con variantes; no limitar la solución a sustituir ese nombre concreto.
2. Comprobar también los casos RFC señalados en la revisión del maestro, conservando los espacios y las palabras posteriores. Sus resultados no fueron compartidos en este ensayo.
3. Ejecutar las pruebas de privacidad y registrar su salida.
4. Identificar el nuevo commit probado y documentar si existen modificaciones locales.

En el siguiente ensayo se repetirán los casos del buzón y su consulta en PostgreSQL, además del recorrido de instalación, usuarios, roles, CSV, métricas, actualización del panel, alertas y 429. Se guardarán salidas y capturas reales, con fecha y resultados por paso, incluyendo los fallos que persistan. No se incluirán credenciales, tokens, llaves ni datos reales de empleados.
