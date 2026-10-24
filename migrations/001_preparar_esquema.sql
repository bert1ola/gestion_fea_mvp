-- Ejecutar una sola vez en la base gestion_fea.
USE gestion_fea;

-- Historial de cambios de estado.
CREATE TABLE IF NOT EXISTS historial_solicitudes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    solicitud_id BIGINT NOT NULL,
    estado_anterior VARCHAR(30) NULL,
    estado_nuevo VARCHAR(30) NULL,
    detalle TEXT NULL,
    fecha_cambio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_responsable VARCHAR(100) NULL,
    INDEX idx_historial_solicitud_fecha (solicitud_id, fecha_cambio),
    CONSTRAINT fk_historial_solicitud
        FOREIGN KEY (solicitud_id) REFERENCES fea_solicitudes(id),
    CONSTRAINT chk_historial_estado_anterior CHECK (
        estado_anterior IS NULL OR estado_anterior IN (
            'Recibido', 'Pendiente', 'Validado', 'Enviado',
            'Entregado', 'Error', 'Revisión manual'
        )
    ),
    CONSTRAINT chk_historial_estado_nuevo CHECK (
        estado_nuevo IS NULL OR estado_nuevo IN (
            'Recibido', 'Pendiente', 'Validado', 'Enviado',
            'Entregado', 'Error', 'Revisión manual'
        )
    )
);

-- NOTA: MySQL no permite agregar columnas con IF NOT EXISTS en todas las versiones.
-- Antes de ejecutar los ALTER, comprueba que estas columnas no existan.
ALTER TABLE notificaciones_correo
    ADD COLUMN asunto VARCHAR(255) NULL,
    ADD COLUMN cuerpo TEXT NULL;

-- La definición inicial solo contemplaba cinco estados. El mockup usa además
-- Validado y Revisión manual. En MySQL 8.0.16+, modifica el CHECK existente.
-- Si tu constraint tiene otro nombre, consulta SHOW CREATE TABLE fea_solicitudes.
ALTER TABLE fea_solicitudes
    DROP CHECK chk_estado_solicitud;

ALTER TABLE fea_solicitudes
    MODIFY estado VARCHAR(30) NOT NULL DEFAULT 'Recibido',
    ADD CONSTRAINT chk_estado_solicitud
    CHECK (estado IN (
        'Recibido', 'Pendiente', 'Validado', 'Enviado',
        'Entregado', 'Error', 'Revisión manual'
    ));

ALTER TABLE historial_solicitudes
    MODIFY estado_anterior VARCHAR(30) NULL,
    MODIFY estado_nuevo VARCHAR(30) NULL;
