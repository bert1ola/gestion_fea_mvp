import os
import ssl
import smtplib
import time
from email.message import EmailMessage
from dotenv import load_dotenv
from database import get_connection

load_dotenv()

def programar_correo(solicitud_id, destinatario, asunto, cuerpo,
                     fecha_hora_programada=None, cc=None):
    """Guarda el correo en MySQL; no lo envía todavía."""
    if not destinatario.strip() or not asunto.strip() or not cuerpo.strip():
        raise ValueError("Destinatario, asunto y cuerpo son obligatorios.")
    conn = get_connection()
    try:
        cur = conn.cursor()
        if fecha_hora_programada:
            cur.execute("""
                INSERT INTO notificaciones_correo
                    (solicitud_id, destinatario_email, cc_institucional,
                     fecha_hora_programada, estado_envio, intentos, asunto, cuerpo)
                VALUES (%s, %s, %s, %s, 'Pendiente', 0, %s, %s)
            """, (solicitud_id, destinatario.strip(),
                  (cc.strip() if cc and cc.strip() else 'sclientes@cpcbiobio.cl'),
                  fecha_hora_programada, asunto.strip(), cuerpo))
        else:
            cur.execute("""
                INSERT INTO notificaciones_correo
                    (solicitud_id, destinatario_email, cc_institucional,
                     fecha_hora_programada, estado_envio, intentos, asunto, cuerpo)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 'Pendiente', 0, %s, %s)
            """, (solicitud_id, destinatario.strip(),
                  (cc.strip() if cc and cc.strip() else 'sclientes@cpcbiobio.cl'),
                  asunto.strip(), cuerpo))
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _smtp_send(destinatario, cc, asunto, cuerpo):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM") or user
    use_ssl = os.getenv("SMTP_USE_SSL", "0") == "1"
    use_tls = os.getenv("SMTP_USE_TLS", "1") == "1"

    if not all([host, sender, user, password]):
        raise RuntimeError("Faltan variables de configuración SMTP.")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = destinatario
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    context = ssl.create_default_context()
    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=25, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=25)
    with server:
        server.ehlo()
        if use_tls:
            server.starttls(context=context)
            server.ehlo()
        server.login(user, password)
        recipients = [destinatario] + ([cc] if cc else [])
        server.send_message(msg, to_addrs=recipients)

def procesar_correo(notificacion_id):
    """
    Envía una notificación existente y guarda intentos/errores.
    Para un worker simple se puede ejecutar desde CLI con:
    python -c "from services.email_service import procesar_correo; print(procesar_correo(1))"
    """
    max_attempts = max(1, int(os.getenv("EMAIL_MAX_ATTEMPTS", "3")))
    delay = max(0, int(os.getenv("EMAIL_RETRY_DELAY_SECONDS", "5")))
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, destinatario_email, cc_institucional, estado_envio,
                   intentos, asunto, cuerpo
            FROM notificaciones_correo WHERE id=%s
        """, (notificacion_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("No existe la notificación.")
        if row["estado_envio"] == "Enviado":
            return {"estado": "Enviado", "intentos": row["intentos"]}
        if not row["asunto"] or not row["cuerpo"]:
            raise ValueError("La notificación no tiene asunto/cuerpo. Revisa la migración SQL.")
    finally:
        conn.close()

    ultimo_error = None
    for intento in range(max_attempts):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE notificaciones_correo
                SET intentos = intentos + 1, estado_envio='Pendiente',
                    detalle_error=NULL
                WHERE id=%s AND estado_envio <> 'Enviado'
            """, (notificacion_id,))
            conn.commit()
        finally:
            conn.close()

        try:
            _smtp_send(row["destinatario_email"], row["cc_institucional"],
                       row["asunto"], row["cuerpo"])
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE notificaciones_correo
                    SET estado_envio='Enviado', fecha_hora_envio=CURRENT_TIMESTAMP,
                        detalle_error=NULL
                    WHERE id=%s
                """, (notificacion_id,))
                conn.commit()
            finally:
                conn.close()
            return {"estado": "Enviado", "intentos_nuevos": intento + 1}
        except Exception as exc:
            ultimo_error = str(exc)[:60000]
            conn = get_connection()
            try:
                cur = conn.cursor()
                estado = "Error" if intento == max_attempts - 1 else "Pendiente"
                cur.execute("""
                    UPDATE notificaciones_correo
                    SET estado_envio=%s, detalle_error=%s
                    WHERE id=%s
                """, (estado, ultimo_error, notificacion_id))
                conn.commit()
            finally:
                conn.close()
            if intento < max_attempts - 1:
                time.sleep(delay * (2 ** intento))

    return {"estado": "Error", "intentos_nuevos": max_attempts, "error": ultimo_error}

def procesar_cola_pendiente(limite=20):
    """Procesa hasta 'limite' correos pendientes; ejecutar desde tarea programada."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM notificaciones_correo
            WHERE estado_envio='Pendiente'
              AND fecha_hora_programada <= CURRENT_TIMESTAMP
            ORDER BY fecha_hora_programada ASC
            LIMIT %s
        """, (int(limite),))
        ids = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
    return [{"id": notification_id, **procesar_correo(notification_id)} for notification_id in ids]
