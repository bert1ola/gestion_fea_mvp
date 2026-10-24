# Gestión FEA – MVP actualizado

Aplicación web de desarrollo para gestionar clientes, solicitudes FEA y citas presenciales. Tecnologías: Flask, HTML/CSS y MySQL.

## Incluye
- Panel con resumen de clientes, solicitudes y citas del día.
- Alta, búsqueda, edición y eliminación de clientes. Un cliente no se elimina si tiene solicitudes asociadas.
- Alta, búsqueda, filtro por estado, edición, actualización de estado y eliminación de solicitudes.
- Historial de cambios de estado de solicitudes.
- Agenda de citas presenciales: creación, filtro por fechas/estado, reprogramación, cancelación, marcar como atendida e historial de movimientos.
- Validación de horario de término posterior al inicio y detección de solapamientos entre citas activas.
- Servicio SMTP con cola, reintentos y registro de errores (configuración de correo por completar).

## 1. Preparar entorno (Windows PowerShell)
Desde la carpeta `gestion_fea_mvp`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completa `.env` con tus credenciales de MySQL. No compartas ni subas `.env` a Git.

## 2. Base de datos
Haz una copia de seguridad de `gestion_fea` antes de ejecutar cambios.

- Si ya ejecutaste `migrations/001_preparar_esquema.sql` y la aplicación actual funciona con clientes/solicitudes, **no vuelvas a ejecutarla**: contiene cambios de esquema que no son idempotentes en todas las versiones de MySQL.
- Ejecuta ahora `migrations/002_agenda_citas.sql` una sola vez. Crea `citas_retiro` (si aún no existe) y `historial_citas`.
- Si `citas_retiro` ya existe, revisa primero su estructura con `SHOW CREATE TABLE citas_retiro;`. `CREATE TABLE IF NOT EXISTS` no modifica una tabla existente ni agrega columnas faltantes.

La aplicación espera que existan las tablas `clientes`, `fea_solicitudes`, `notificaciones_correo` e `historial_solicitudes`, y que las columnas de clientes y solicitudes coincidan con el esquema que se compartió durante la implementación.

## 3. Iniciar la aplicación

```powershell
python app.py
```

Abre `http://127.0.0.1:5000`.

## 4. Uso de la agenda
1. Entra en **Citas presenciales**.
2. Selecciona una solicitud que aún no tenga cita activa y cuyo token no esté entregado.
3. Elige fecha, hora de inicio y hora de término.
4. Si el bloque se cruza con otra cita activa, el sistema lo rechazará.
5. Para cambiar una cita, usa **Reprogramar** e indica el motivo. El cambio queda guardado en `historial_citas`.
6. Las citas se pueden marcar como atendidas o canceladas; ambas acciones también quedan registradas.

Los horarios de atención de la oficina no están fijados en el código porque todavía no se definió el horario oficial. La aplicación valida duración y cruces, pero actualmente permite cualquier rango horario válido.

## 5. Eliminación de registros
- Un cliente solo se puede eliminar si no tiene solicitudes asociadas.
- Eliminar una solicitud borra también las citas, el historial de citas, el historial de estados y las notificaciones relacionadas. Es una eliminación definitiva; úsala únicamente para corregir registros creados por error.
- En una versión productiva conviene evaluar baja lógica y permisos por usuario para conservar la trazabilidad.

## 6. Correo electrónico
La cola SMTP no se ejecuta automáticamente solo por mantener Flask abierto. Para probarla, configura las variables SMTP del `.env` y usa una dirección de prueba autorizada. En producción debe ejecutarse mediante una tarea periódica o worker dedicado.

## Limitaciones antes de producción
Este MVP no incluye autenticación, roles, protección CSRF ni baja lógica. `usuario_responsable` usa el valor fijo `operador` porque todavía no hay inicio de sesión. `FLASK_DEBUG=1` es solo para desarrollo; no lo uses en producción. Añade validación de RUT, controles de acceso y protección de datos antes de publicar el sistema.
