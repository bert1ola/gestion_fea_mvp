from database import get_connection

ESTADOS = ("Recibido", "Pendiente", "Validado", "Enviado",
           "Entregado", "Error", "Revisión manual")
TIPOS_TRAMITE = ("Nuevo", "Renovación")

def listar_solicitudes(busqueda="", estado=""):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        sql = """
            SELECT s.id, s.n_solicitud, s.cliente_id, c.rut,
                   c.nombre_completo, c.correo_electronico,
                   s.tipo_tramite, s.anios_vigencia, s.estado,
                   s.fecha_aviso, s.fecha_entrega, s.fecha_caducidad
            FROM fea_solicitudes s
            JOIN clientes c ON c.id = s.cliente_id
            WHERE 1=1
        """
        params = []
        if busqueda.strip():
            term = f"%{busqueda.strip()}%"
            sql += " AND (s.n_solicitud LIKE %s OR c.rut LIKE %s OR c.nombre_completo LIKE %s)"
            params.extend([term, term, term])
        if estado.strip():
            sql += " AND s.estado = %s"
            params.append(estado)
        sql += " ORDER BY s.fecha_aviso DESC LIMIT 300"
        cur.execute(sql, tuple(params))
        return cur.fetchall()
    finally:
        conn.close()

def crear_solicitud(cliente_id, n_solicitud, tipo_tramite, anios_vigencia,
                    monto_fda=None, fecha_aviso=None):
    if tipo_tramite not in TIPOS_TRAMITE:
        raise ValueError("El tipo de trámite debe ser Nuevo o Renovación.")
    if anios_vigencia not in (1, 2, 3):
        raise ValueError("La vigencia debe ser 1, 2 o 3 años.")
    if not n_solicitud.strip():
        raise ValueError("El número de solicitud es obligatorio.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        # fecha_aviso tiene que estar definida según el esquema original.
        if fecha_aviso:
            cur.execute("""
                INSERT INTO fea_solicitudes
                    (cliente_id, n_solicitud, tipo_tramite, anios_vigencia,
                     monto_fda, estado, fecha_aviso)
                VALUES (%s, %s, %s, %s, %s, 'Recibido', %s)
            """, (cliente_id, n_solicitud.strip(), tipo_tramite,
                  anios_vigencia, monto_fda or None, fecha_aviso))
        else:
            cur.execute("""
                INSERT INTO fea_solicitudes
                    (cliente_id, n_solicitud, tipo_tramite, anios_vigencia,
                     monto_fda, estado, fecha_aviso)
                VALUES (%s, %s, %s, %s, %s, 'Recibido', CURRENT_TIMESTAMP)
            """, (cliente_id, n_solicitud.strip(), tipo_tramite,
                  anios_vigencia, monto_fda or None))
        solicitud_id = cur.lastrowid
        # El historial se registra en la misma transacción.
        cur.execute("""
            INSERT INTO historial_solicitudes
                (solicitud_id, estado_anterior, estado_nuevo, detalle, usuario_responsable)
            VALUES (%s, NULL, 'Recibido', %s, %s)
        """, (solicitud_id, "Solicitud creada", "sistema"))
        conn.commit()
        return solicitud_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def cambiar_estado(solicitud_id, nuevo_estado, detalle="", usuario="operador"):
    if nuevo_estado not in ESTADOS:
        raise ValueError("Estado no permitido.")
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT estado FROM fea_solicitudes WHERE id=%s FOR UPDATE", (solicitud_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("No existe esa solicitud.")
        anterior = row["estado"]
        if anterior == nuevo_estado:
            conn.rollback()
            return False
        cur.execute("UPDATE fea_solicitudes SET estado=%s WHERE id=%s",
                    (nuevo_estado, solicitud_id))
        cur.execute("""
            INSERT INTO historial_solicitudes
                (solicitud_id, estado_anterior, estado_nuevo, detalle, usuario_responsable)
            VALUES (%s, %s, %s, %s, %s)
        """, (solicitud_id, anterior, nuevo_estado, detalle or None, usuario))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def registrar_entrega(solicitud_id, numero_serie, fecha_entrega=None, usuario="operador"):
    if not numero_serie.strip():
        raise ValueError("El número de serie del token es obligatorio.")
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT estado, anios_vigencia
            FROM fea_solicitudes WHERE id=%s FOR UPDATE
        """, (solicitud_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("No existe esa solicitud.")
        if row["anios_vigencia"] is None:
            raise ValueError("La solicitud no tiene definida la vigencia.")
        cur2 = conn.cursor()
        if fecha_entrega:
            cur2.execute("""
                UPDATE fea_solicitudes
                SET n_serie_token=%s, fecha_entrega=%s,
                    fecha_caducidad=DATE_ADD(%s, INTERVAL anios_vigencia YEAR),
                    estado='Entregado'
                WHERE id=%s
            """, (numero_serie.strip(), fecha_entrega, fecha_entrega, solicitud_id))
        else:
            cur2.execute("""
                UPDATE fea_solicitudes
                SET n_serie_token=%s, fecha_entrega=CURRENT_TIMESTAMP,
                    fecha_caducidad=DATE_ADD(CURRENT_TIMESTAMP, INTERVAL anios_vigencia YEAR),
                    estado='Entregado'
                WHERE id=%s
            """, (numero_serie.strip(), solicitud_id))
        cur2.execute("""
            INSERT INTO historial_solicitudes
                (solicitud_id, estado_anterior, estado_nuevo, detalle, usuario_responsable)
            VALUES (%s, %s, 'Entregado', %s, %s)
        """, (solicitud_id, row["estado"],
              f"Entrega de token. Serie: {numero_serie.strip()}", usuario))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def obtener_solicitud(solicitud_id):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, cliente_id, n_solicitud, tipo_tramite, anios_vigencia,
                   monto_fda, n_serie_token, estado, fecha_aviso,
                   fecha_entrega, fecha_caducidad
            FROM fea_solicitudes WHERE id=%s
        """, (solicitud_id,))
        return cur.fetchone()
    finally:
        conn.close()

def actualizar_solicitud(solicitud_id, cliente_id, n_solicitud, tipo_tramite,
                         anios_vigencia, monto_fda=None, n_serie_token=None,
                         fecha_aviso=None, fecha_entrega=None, fecha_caducidad=None,
                         estado=None, detalle="", usuario="operador"):
    if tipo_tramite not in TIPOS_TRAMITE:
        raise ValueError("El tipo de trámite debe ser Nuevo o Renovación.")
    if anios_vigencia not in (1, 2, 3):
        raise ValueError("La vigencia debe ser 1, 2 o 3 años.")
    if not n_solicitud.strip():
        raise ValueError("El número de solicitud es obligatorio.")
    if estado not in ESTADOS:
        raise ValueError("Estado no permitido.")
    if not fecha_aviso:
        raise ValueError("La fecha de aviso es obligatoria.")

    def normalizar_fecha(valor):
        if not valor:
            return None
        return valor.replace("T", " ")

    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT estado FROM fea_solicitudes WHERE id=%s FOR UPDATE", (solicitud_id,))
        anterior = cur.fetchone()
        if not anterior:
            raise ValueError("No existe esa solicitud.")
        estado_anterior = anterior["estado"]
        cur.execute("""
            UPDATE fea_solicitudes
            SET cliente_id=%s, n_solicitud=%s, tipo_tramite=%s,
                anios_vigencia=%s, monto_fda=%s, n_serie_token=%s,
                fecha_aviso=%s, fecha_entrega=%s, fecha_caducidad=%s,
                estado=%s
            WHERE id=%s
        """, (
            cliente_id, n_solicitud.strip(), tipo_tramite, anios_vigencia,
            monto_fda or None, n_serie_token.strip() or None if n_serie_token else None,
            normalizar_fecha(fecha_aviso), normalizar_fecha(fecha_entrega),
            normalizar_fecha(fecha_caducidad), estado, solicitud_id
        ))
        if estado_anterior != estado:
            cur.execute("""
                INSERT INTO historial_solicitudes
                    (solicitud_id, estado_anterior, estado_nuevo, detalle, usuario_responsable)
                VALUES (%s, %s, %s, %s, %s)
            """, (solicitud_id, estado_anterior, estado, detalle or "Estado actualizado desde edición", usuario))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def eliminar_solicitud(solicitud_id):
    """Elimina la solicitud y sus registros dependientes en una sola transacción."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM fea_solicitudes WHERE id=%s FOR UPDATE", (solicitud_id,))
        if not cur.fetchone():
            return False
        # Se borran primero los registros dependientes para respetar las FK.
        cur.execute("""
            DELETE h FROM historial_citas h
            INNER JOIN citas_retiro c ON c.id = h.cita_id
            WHERE c.solicitud_id=%s
        """, (solicitud_id,))
        cur.execute("DELETE FROM citas_retiro WHERE solicitud_id=%s", (solicitud_id,))
        cur.execute("DELETE FROM notificaciones_correo WHERE solicitud_id=%s", (solicitud_id,))
        cur.execute("DELETE FROM historial_solicitudes WHERE solicitud_id=%s", (solicitud_id,))
        cur.execute("DELETE FROM fea_solicitudes WHERE id=%s", (solicitud_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
