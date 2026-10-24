from datetime import date, timedelta
from database import get_connection

ESTADOS_CITA = ("Agendada", "Atendida", "Cancelada", "Reprogramada")


def _validar_horas(hora_inicio, hora_fin):
    if not hora_inicio or not hora_fin or hora_inicio >= hora_fin:
        raise ValueError("La hora de término debe ser posterior a la hora de inicio.")


def _validar_sin_choque(cur, fecha_cita, hora_inicio, hora_fin, excluir_id=None):
    sql = """
        SELECT id FROM citas_retiro
        WHERE fecha_cita=%s
          AND estado_cita IN ('Agendada', 'Reprogramada')
          AND hora_inicio < %s AND hora_fin > %s
    """
    params = [fecha_cita, hora_fin, hora_inicio]
    if excluir_id is not None:
        sql += " AND id <> %s"
        params.append(excluir_id)
    sql += " LIMIT 1"
    cur.execute(sql, tuple(params))
    if cur.fetchone():
        raise ValueError("Ese horario se cruza con otra cita. Elige otro bloque horario.")


def listar_citas(fecha_desde=None, fecha_hasta=None, estado=""):
    fecha_desde = fecha_desde or date.today().isoformat()
    fecha_hasta = fecha_hasta or (date.today() + timedelta(days=7)).isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        sql = """
            SELECT c.id, c.solicitud_id, c.fecha_cita, c.hora_inicio, c.hora_fin,
                   DATE_FORMAT(c.fecha_cita, '%Y-%m-%d') AS fecha_cita_texto,
                   TIME_FORMAT(c.hora_inicio, '%H:%i') AS hora_inicio_texto,
                   TIME_FORMAT(c.hora_fin, '%H:%i') AS hora_fin_texto,
                   c.estado_cita, c.motivo_reprogramacion,
                   s.n_solicitud, s.estado AS estado_solicitud,
                   cl.rut, cl.nombre_completo, cl.telefono, cl.correo_electronico
            FROM citas_retiro c
            JOIN fea_solicitudes s ON s.id=c.solicitud_id
            JOIN clientes cl ON cl.id=s.cliente_id
            WHERE c.fecha_cita BETWEEN %s AND %s
        """
        params = [fecha_desde, fecha_hasta]
        if estado:
            sql += " AND c.estado_cita=%s"
            params.append(estado)
        sql += " ORDER BY c.fecha_cita, c.hora_inicio LIMIT 500"
        cur.execute(sql, tuple(params))
        return cur.fetchall()
    finally:
        conn.close()


def listar_solicitudes_agendables():
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT s.id, s.n_solicitud, s.estado, c.rut, c.nombre_completo
            FROM fea_solicitudes s
            JOIN clientes c ON c.id=s.cliente_id
            WHERE s.estado <> 'Entregado'
              AND NOT EXISTS (
                SELECT 1 FROM citas_retiro cr
                WHERE cr.solicitud_id=s.id
                  AND cr.estado_cita IN ('Agendada', 'Reprogramada')
              )
            ORDER BY s.fecha_aviso DESC LIMIT 500
        """)
        return cur.fetchall()
    finally:
        conn.close()


def _registrar_historial(cur, cita_id, accion, fecha_anterior=None,
                         inicio_anterior=None, fin_anterior=None,
                         fecha_nueva=None, inicio_nuevo=None, fin_nuevo=None,
                         motivo=None, usuario="operador"):
    cur.execute("""
        INSERT INTO historial_citas
            (cita_id, accion, fecha_anterior, hora_inicio_anterior, hora_fin_anterior,
             fecha_nueva, hora_inicio_nueva, hora_fin_nueva, motivo, usuario_responsable)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (cita_id, accion, fecha_anterior, inicio_anterior, fin_anterior,
          fecha_nueva, inicio_nuevo, fin_nuevo, motivo, usuario))


def crear_cita(solicitud_id, fecha_cita, hora_inicio, hora_fin, usuario="operador"):
    if not fecha_cita:
        raise ValueError("La fecha de la cita es obligatoria.")
    _validar_horas(hora_inicio, hora_fin)
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT estado FROM fea_solicitudes WHERE id=%s", (solicitud_id,))
        solicitud = cur.fetchone()
        if not solicitud:
            raise ValueError("La solicitud seleccionada no existe.")
        if solicitud["estado"] == "Entregado":
            raise ValueError("No se puede agendar una solicitud cuyo token ya fue entregado.")
        cur2 = conn.cursor()
        cur2.execute("""
            SELECT id FROM citas_retiro
            WHERE solicitud_id=%s AND estado_cita IN ('Agendada', 'Reprogramada')
            LIMIT 1
        """, (solicitud_id,))
        if cur2.fetchone():
            raise ValueError("Esta solicitud ya tiene una cita activa.")
        _validar_sin_choque(cur2, fecha_cita, hora_inicio, hora_fin)
        cur2.execute("""
            INSERT INTO citas_retiro
                (solicitud_id, fecha_cita, hora_inicio, hora_fin, estado_cita)
            VALUES (%s, %s, %s, %s, 'Agendada')
        """, (solicitud_id, fecha_cita, hora_inicio, hora_fin))
        cita_id = cur2.lastrowid
        _registrar_historial(cur2, cita_id, "Creada", fecha_nueva=fecha_cita,
                             inicio_nuevo=hora_inicio, fin_nuevo=hora_fin, usuario=usuario)
        conn.commit()
        return cita_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reprogramar_cita(cita_id, fecha_cita, hora_inicio, hora_fin, motivo, usuario="operador"):
    if not fecha_cita:
        raise ValueError("La nueva fecha es obligatoria.")
    if not motivo or not motivo.strip():
        raise ValueError("Indica el motivo de la reprogramación.")
    _validar_horas(hora_inicio, hora_fin)
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM citas_retiro WHERE id=%s FOR UPDATE", (cita_id,))
        cita = cur.fetchone()
        if not cita:
            raise ValueError("La cita no existe.")
        if cita["estado_cita"] not in ("Agendada", "Reprogramada"):
            raise ValueError("Solo se pueden reprogramar citas activas.")
        cur2 = conn.cursor()
        _validar_sin_choque(cur2, fecha_cita, hora_inicio, hora_fin, excluir_id=cita_id)
        cur2.execute("""
            UPDATE citas_retiro
            SET fecha_cita=%s, hora_inicio=%s, hora_fin=%s,
                estado_cita='Reprogramada', motivo_reprogramacion=%s
            WHERE id=%s
        """, (fecha_cita, hora_inicio, hora_fin, motivo.strip(), cita_id))
        _registrar_historial(
            cur2, cita_id, "Reprogramada", cita["fecha_cita"], cita["hora_inicio"], cita["hora_fin"],
            fecha_cita, hora_inicio, hora_fin, motivo.strip(), usuario
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cambiar_estado_cita(cita_id, nuevo_estado, motivo="", usuario="operador"):
    if nuevo_estado not in ESTADOS_CITA:
        raise ValueError("Estado de cita no permitido.")
    if nuevo_estado == "Reprogramada":
        raise ValueError("Para reprogramar, usa el formulario de reprogramación.")
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM citas_retiro WHERE id=%s FOR UPDATE", (cita_id,))
        cita = cur.fetchone()
        if not cita:
            raise ValueError("La cita no existe.")
        if cita["estado_cita"] in ("Atendida", "Cancelada"):
            raise ValueError("La cita ya está cerrada y no puede cambiar de estado.")
        cur2 = conn.cursor()
        cur2.execute("UPDATE citas_retiro SET estado_cita=%s WHERE id=%s", (nuevo_estado, cita_id))
        _registrar_historial(cur2, cita_id, nuevo_estado,
                             cita["fecha_cita"], cita["hora_inicio"], cita["hora_fin"],
                             motivo=motivo.strip() or None, usuario=usuario)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_historial_citas(cita_id):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT accion,
                   DATE_FORMAT(fecha_anterior, '%Y-%m-%d') AS fecha_anterior,
                   TIME_FORMAT(hora_inicio_anterior, '%H:%i') AS hora_inicio_anterior,
                   TIME_FORMAT(hora_fin_anterior, '%H:%i') AS hora_fin_anterior,
                   DATE_FORMAT(fecha_nueva, '%Y-%m-%d') AS fecha_nueva,
                   TIME_FORMAT(hora_inicio_nueva, '%H:%i') AS hora_inicio_nueva,
                   TIME_FORMAT(hora_fin_nueva, '%H:%i') AS hora_fin_nueva,
                   motivo, fecha_cambio, usuario_responsable
            FROM historial_citas WHERE cita_id=%s ORDER BY fecha_cambio DESC, id DESC
        """, (cita_id,))
        return cur.fetchall()
    finally:
        conn.close()

def obtener_cita(cita_id):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT c.id, c.solicitud_id, c.fecha_cita, c.hora_inicio, c.hora_fin,
                   DATE_FORMAT(c.fecha_cita, '%Y-%m-%d') AS fecha_cita_texto,
                   TIME_FORMAT(c.hora_inicio, '%H:%i') AS hora_inicio_texto,
                   TIME_FORMAT(c.hora_fin, '%H:%i') AS hora_fin_texto,
                   c.estado_cita, c.motivo_reprogramacion,
                   s.n_solicitud, cl.nombre_completo, cl.rut
            FROM citas_retiro c
            JOIN fea_solicitudes s ON s.id=c.solicitud_id
            JOIN clientes cl ON cl.id=s.cliente_id
            WHERE c.id=%s
        """, (cita_id,))
        return cur.fetchone()
    finally:
        conn.close()
