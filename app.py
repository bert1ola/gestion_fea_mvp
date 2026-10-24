import os
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from mysql.connector import IntegrityError, Error as MySQLError

from services.clients import (
    listar_clientes, crear_cliente, obtener_cliente,
    actualizar_cliente, eliminar_cliente,
)
from services.requests import (
    listar_solicitudes, crear_solicitud, cambiar_estado,
    obtener_solicitud, actualizar_solicitud, eliminar_solicitud,
    ESTADOS, TIPOS_TRAMITE,
)
from services.appointments import (
    listar_citas, listar_solicitudes_agendables, crear_cita,
    reprogramar_cita, cambiar_estado_cita, obtener_historial_citas,
    ESTADOS_CITA, obtener_cita,
)

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "solo-desarrollo-cambiar-esta-clave")


def _valor_formulario_fecha(nombre):
    valor = request.form.get(nombre, "").strip()
    return valor or None


@app.get("/")
def index():
    solicitudes = listar_solicitudes()
    clientes = listar_clientes()
    try:
        citas_hoy = listar_citas(date.today().isoformat(), date.today().isoformat())
    except MySQLError:
        # El panel sigue abriendo si aún no se ejecuta la migración de agenda.
        citas_hoy = []
    return render_template(
        "index.html",
        total_clientes=len(clientes),
        total_solicitudes=len(solicitudes),
        pendientes=sum(1 for s in solicitudes if s["estado"] in ("Recibido", "Pendiente")),
        errores=sum(1 for s in solicitudes if s["estado"] in ("Error", "Revisión manual")),
        solicitudes=solicitudes[:8],
        citas_hoy=citas_hoy[:6],
    )


@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    if request.method == "POST":
        try:
            crear_cliente(
                request.form.get("rut", ""),
                request.form.get("nombre_completo", ""),
                request.form.get("correo_electronico", ""),
                request.form.get("telefono", ""),
                request.form.get("rut_empresa", ""),
            )
            flash("Cliente creado correctamente.", "success")
            return redirect(url_for("clientes"))
        except IntegrityError:
            flash("No se pudo crear: el RUT ya existe o hay un conflicto de datos.", "error")
        except (ValueError, MySQLError) as exc:
            flash(f"No se pudo crear el cliente: {exc}", "error")
    busqueda = request.args.get("q", "")
    return render_template("clientes.html", clientes=listar_clientes(busqueda), busqueda=busqueda)


@app.route("/clientes/<int:cliente_id>/editar", methods=["GET", "POST"])
def editar_cliente(cliente_id):
    cliente = obtener_cliente(cliente_id)
    if not cliente:
        flash("No se encontró el cliente.", "error")
        return redirect(url_for("clientes"))
    if request.method == "POST":
        try:
            actualizar_cliente(
                cliente_id,
                request.form.get("rut", ""),
                request.form.get("nombre_completo", ""),
                request.form.get("correo_electronico", ""),
                request.form.get("telefono", ""),
                request.form.get("rut_empresa", ""),
            )
            flash("Cliente actualizado correctamente.", "success")
            return redirect(url_for("clientes"))
        except IntegrityError:
            flash("No se pudo actualizar: el RUT ya pertenece a otro cliente.", "error")
        except (ValueError, MySQLError) as exc:
            flash(f"No se pudo actualizar el cliente: {exc}", "error")
    return render_template("editar_cliente.html", cliente=cliente)


@app.post("/clientes/<int:cliente_id>/eliminar")
def borrar_cliente(cliente_id):
    try:
        if eliminar_cliente(cliente_id):
            flash("Cliente eliminado.", "success")
        else:
            flash("El cliente ya no existe.", "error")
    except (ValueError, MySQLError) as exc:
        flash(f"No se pudo eliminar el cliente: {exc}", "error")
    return redirect(url_for("clientes"))


@app.route("/solicitudes", methods=["GET", "POST"])
def solicitudes():
    if request.method == "POST":
        try:
            crear_solicitud(
                int(request.form["cliente_id"]),
                request.form["n_solicitud"],
                request.form["tipo_tramite"],
                int(request.form["anios_vigencia"]),
                request.form.get("monto") or None,
            )
            flash("Solicitud creada correctamente.", "success")
            return redirect(url_for("solicitudes"))
        except IntegrityError:
            flash("No se pudo crear: revisa que el número de solicitud no esté duplicado y que el cliente exista.", "error")
        except (ValueError, KeyError, MySQLError) as exc:
            flash(f"No se pudo crear la solicitud: {exc}", "error")
    busqueda = request.args.get("q", "")
    estado = request.args.get("estado", "")
    return render_template(
        "solicitudes.html",
        solicitudes=listar_solicitudes(busqueda, estado),
        clientes=listar_clientes(),
        estados=ESTADOS,
        tipos=TIPOS_TRAMITE,
        busqueda=busqueda,
        estado_seleccionado=estado,
    )


@app.route("/solicitudes/<int:solicitud_id>/editar", methods=["GET", "POST"])
def editar_solicitud(solicitud_id):
    solicitud = obtener_solicitud(solicitud_id)
    if not solicitud:
        flash("No se encontró la solicitud.", "error")
        return redirect(url_for("solicitudes"))
    if request.method == "POST":
        try:
            actualizar_solicitud(
                solicitud_id=solicitud_id,
                cliente_id=int(request.form["cliente_id"]),
                n_solicitud=request.form.get("n_solicitud", ""),
                tipo_tramite=request.form.get("tipo_tramite", ""),
                anios_vigencia=int(request.form["anios_vigencia"]),
                monto_fda=request.form.get("monto_fda") or None,
                n_serie_token=request.form.get("n_serie_token", ""),
                fecha_aviso=_valor_formulario_fecha("fecha_aviso"),
                fecha_entrega=_valor_formulario_fecha("fecha_entrega"),
                fecha_caducidad=_valor_formulario_fecha("fecha_caducidad"),
                estado=request.form.get("estado", ""),
                detalle=request.form.get("detalle", ""),
            )
            flash("Solicitud actualizada correctamente.", "success")
            return redirect(url_for("solicitudes"))
        except IntegrityError:
            flash("No se pudo actualizar: revisa que el número de solicitud no esté duplicado y que el cliente exista.", "error")
        except (ValueError, KeyError, MySQLError) as exc:
            flash(f"No se pudo actualizar la solicitud: {exc}", "error")
    return render_template(
        "editar_solicitud.html", solicitud=solicitud,
        clientes=listar_clientes(), estados=ESTADOS, tipos=TIPOS_TRAMITE,
    )


@app.post("/solicitudes/<int:solicitud_id>/eliminar")
def borrar_solicitud(solicitud_id):
    try:
        if eliminar_solicitud(solicitud_id):
            flash("Solicitud y sus registros asociados eliminados.", "success")
        else:
            flash("La solicitud ya no existe.", "error")
    except MySQLError as exc:
        flash(f"No se pudo eliminar la solicitud: {exc}", "error")
    return redirect(url_for("solicitudes"))


@app.post("/solicitudes/<int:solicitud_id>/estado")
def actualizar_estado(solicitud_id):
    try:
        cambiar_estado(
            solicitud_id,
            request.form.get("estado", ""),
            request.form.get("detalle", ""),
            usuario="operador",
        )
        flash("Estado actualizado y guardado en el historial.", "success")
    except (ValueError, MySQLError) as exc:
        flash(f"No se pudo actualizar el estado: {exc}", "error")
    return redirect(url_for("solicitudes"))


@app.route("/citas", methods=["GET", "POST"])
def citas():
    hoy = date.today()
    fecha_desde = request.values.get("desde", hoy.isoformat())
    fecha_hasta = request.values.get("hasta", (hoy + timedelta(days=7)).isoformat())
    estado = request.values.get("estado", "")
    if request.method == "POST":
        try:
            crear_cita(
                int(request.form["solicitud_id"]),
                request.form.get("fecha_cita", ""),
                request.form.get("hora_inicio", ""),
                request.form.get("hora_fin", ""),
            )
            flash("Cita presencial agendada correctamente.", "success")
            return redirect(url_for("citas", desde=fecha_desde, hasta=fecha_hasta, estado=estado))
        except IntegrityError:
            flash("No se pudo crear la cita por un conflicto con los datos.", "error")
        except (ValueError, KeyError, MySQLError) as exc:
            flash(f"No se pudo agendar la cita: {exc}", "error")
    try:
        listado_citas = listar_citas(fecha_desde, fecha_hasta, estado)
        solicitudes_agendables = listar_solicitudes_agendables()
    except MySQLError as exc:
        flash(f"No se pudo cargar la agenda. Comprueba que ejecutaste la migración 002_agenda_citas.sql: {exc}", "error")
        listado_citas, solicitudes_agendables = [], []
    return render_template(
        "citas.html", citas=listado_citas, solicitudes=solicitudes_agendables,
        estados_cita=ESTADOS_CITA, desde=fecha_desde, hasta=fecha_hasta,
        estado_seleccionado=estado, hoy=hoy.isoformat(),
    )


@app.route("/citas/<int:cita_id>/reprogramar", methods=["GET", "POST"])
def reprogramar(cita_id):
    cita = obtener_cita(cita_id)
    if not cita:
        flash("No se encontró la cita.", "error")
        return redirect(url_for("citas"))
    if request.method == "POST":
        try:
            reprogramar_cita(
                cita_id, request.form.get("fecha_cita", ""),
                request.form.get("hora_inicio", ""), request.form.get("hora_fin", ""),
                request.form.get("motivo", ""),
            )
            flash("Cita reprogramada y cambio registrado en el historial.", "success")
            return redirect(url_for("citas"))
        except (ValueError, MySQLError) as exc:
            flash(f"No se pudo reprogramar la cita: {exc}", "error")
    return render_template("reprogramar_cita.html", cita=cita)


@app.post("/citas/<int:cita_id>/estado")
def estado_cita(cita_id):
    try:
        nuevo_estado = request.form.get("estado", "")
        cambiar_estado_cita(cita_id, nuevo_estado, request.form.get("motivo", ""))
        flash(f"Cita marcada como {nuevo_estado.lower()}.", "success")
    except (ValueError, MySQLError) as exc:
        flash(f"No se pudo actualizar la cita: {exc}", "error")
    return redirect(url_for("citas"))


@app.get("/citas/<int:cita_id>/historial")
def historial_cita(cita_id):
    try:
        historial = obtener_historial_citas(cita_id)
    except MySQLError as exc:
        flash(f"No se pudo consultar el historial: {exc}", "error")
        return redirect(url_for("citas"))
    return render_template("historial_cita.html", cita_id=cita_id, historial=historial)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
