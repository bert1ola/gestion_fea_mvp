-- Ejecutar una sola vez en la base gestion_fea.
-- Crea las tablas necesarias para agenda presencial e historial de reprogramaciones.
USE gestion_fea;

CREATE TABLE IF NOT EXISTS citas_retiro (
    id BIGINT NOT NULL AUTO_INCREMENT,
    solicitud_id BIGINT NOT NULL,
    fecha_cita DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    estado_cita VARCHAR(20) NOT NULL DEFAULT 'Agendada',
    motivo_reprogramacion TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_citas_fecha_hora (fecha_cita, hora_inicio, hora_fin),
    KEY idx_citas_solicitud_estado (solicitud_id, estado_cita),
    CONSTRAINT fk_cita_solicitud FOREIGN KEY (solicitud_id) REFERENCES fea_solicitudes(id),
    CONSTRAINT chk_estado_cita CHECK (estado_cita IN ('Agendada', 'Atendida', 'Cancelada', 'Reprogramada')),
    CONSTRAINT chk_horas_cita CHECK (hora_fin > hora_inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS historial_citas (
    id BIGINT NOT NULL AUTO_INCREMENT,
    cita_id BIGINT NOT NULL,
    accion VARCHAR(30) NOT NULL,
    fecha_anterior DATE NULL,
    hora_inicio_anterior TIME NULL,
    hora_fin_anterior TIME NULL,
    fecha_nueva DATE NULL,
    hora_inicio_nueva TIME NULL,
    hora_fin_nueva TIME NULL,
    motivo TEXT NULL,
    fecha_cambio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_responsable VARCHAR(100) NULL,
    PRIMARY KEY (id),
    KEY idx_historial_citas_fecha (cita_id, fecha_cambio),
    CONSTRAINT fk_historial_cita FOREIGN KEY (cita_id) REFERENCES citas_retiro(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


show tables;