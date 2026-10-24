from database import get_connection

def listar_clientes(busqueda=""):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        termino = f"%{busqueda.strip()}%"
        if busqueda.strip():
            cur.execute("""
                SELECT id, rut, nombre_completo, correo_electronico,
                       telefono, rut_empresa
                FROM clientes
                WHERE rut LIKE %s OR nombre_completo LIKE %s
                ORDER BY nombre_completo
                LIMIT 200
            """, (termino, termino))
        else:
            cur.execute("""
                SELECT id, rut, nombre_completo, correo_electronico,
                       telefono, rut_empresa
                FROM clientes
                ORDER BY id DESC
                LIMIT 200
            """)
        return cur.fetchall()
    finally:
        conn.close()

def obtener_cliente(cliente_id):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
        return cur.fetchone()
    finally:
        conn.close()

def crear_cliente(rut, nombre_completo, correo_electronico, telefono=None, rut_empresa=None):
    rut = rut.strip().upper()
    nombre_completo = nombre_completo.strip()
    correo_electronico = correo_electronico.strip()
    if not rut or not nombre_completo or not correo_electronico:
        raise ValueError("RUT, nombre y correo son obligatorios.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clientes
                (rut, nombre_completo, correo_electronico, telefono, rut_empresa)
            VALUES (%s, %s, %s, %s, %s)
        """, (rut, nombre_completo, correo_electronico,
              telefono.strip() or None if telefono else None,
              rut_empresa.strip().upper() or None if rut_empresa else None))
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def actualizar_cliente(cliente_id, rut, nombre_completo, correo_electronico, telefono=None, rut_empresa=None):
    if not rut.strip() or not nombre_completo.strip() or not correo_electronico.strip():
        raise ValueError("RUT, nombre y correo son obligatorios.")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE clientes
            SET rut=%s, nombre_completo=%s, correo_electronico=%s,
                telefono=%s, rut_empresa=%s
            WHERE id=%s
        """, (rut.strip().upper(), nombre_completo.strip(),
              correo_electronico.strip(),
              telefono.strip() or None if telefono else None,
              rut_empresa.strip().upper() or None if rut_empresa else None,
              cliente_id))
        if cur.rowcount == 0:
            conn.rollback()
            return False
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def eliminar_cliente(cliente_id):
    """Elimina un cliente solo si no tiene solicitudes asociadas."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM fea_solicitudes WHERE cliente_id=%s", (cliente_id,))
        cantidad = cur.fetchone()[0]
        if cantidad:
            raise ValueError(
                "No se puede eliminar este cliente porque tiene solicitudes asociadas. "
                "Elimina primero las solicitudes que correspondan."
            )
        cur.execute("DELETE FROM clientes WHERE id=%s", (cliente_id,))
        if cur.rowcount == 0:
            conn.rollback()
            return False
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
