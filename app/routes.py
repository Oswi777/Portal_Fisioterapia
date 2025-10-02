from app import app, db, bcrypt, mail
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Message
from app.models import Usuario, Servicio, Cita
from datetime import datetime, timedelta

# ========== PÁGINAS PÚBLICAS ==========

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        usuario = Usuario.query.filter_by(email=email).first()

        from flask_bcrypt import check_password_hash as fb_check
        if usuario and fb_check(usuario.password, password):
            session["usuario_id"] = usuario.id
            session["usuario_nombre"] = usuario.nombre
            return redirect(url_for("admin_dashboard"))
        else:
            error = "Correo o contraseña incorrectos"

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/cita", methods=["GET", "POST"])
def agendar_cita():
    servicios = Servicio.query.filter_by(activo=True).order_by(Servicio.nombre).all()
    mensaje = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        telefono = request.form.get("telefono", "").strip()
        fecha_hora = request.form.get("fecha_hora", "").strip()
        servicio_id = request.form.get("servicio_id")

        if not all([nombre, email, telefono, fecha_hora, servicio_id]):
            mensaje = "Completa todos los campos."
            return render_template("cita.html", servicios=servicios, mensaje=mensaje)

        try:
            fecha_hora_dt = datetime.strptime(fecha_hora, "%Y-%m-%dT%H:%M")
        except ValueError:
            mensaje = "Formato de fecha incorrecto."
            return render_template("cita.html", servicios=servicios, mensaje=mensaje)

        # Bloque horario 1h (ajustable)
        hora_inicio = fecha_hora_dt.replace(minute=0, second=0, microsecond=0)
        hora_fin = hora_inicio + timedelta(hours=1)

        # Choque de horario (puedes limitar por servicio si quieres)
        cita_existente = Cita.query.filter(
            Cita.fecha_hora >= hora_inicio,
            Cita.fecha_hora < hora_fin
        ).first()

        if cita_existente:
            mensaje = "Ya hay una cita agendada en esa hora. Por favor, elige otro horario."
            return render_template("cita.html", servicios=servicios, mensaje=mensaje)

        nueva_cita = Cita(
            nombre=nombre,
            email=email,
            telefono=telefono,
            fecha_hora=fecha_hora_dt,
            servicio_id=int(servicio_id),
            estado="pendiente"
        )
        db.session.add(nueva_cita)
        db.session.commit()

        # Enviar correo al admin (si SMTP configurado)
        try:
            msg = Message("Nueva cita registrada", recipients=[app.config.get("MAIL_DEFAULT_SENDER")])
            msg.body = (
                "Nueva cita registrada en FISIOLIFE:\n\n"
                f"Nombre: {nombre}\nEmail: {email}\nTeléfono: {telefono}\n"
                f"Fecha y hora: {fecha_hora_dt}\nServicio ID: {servicio_id}\n"
            )
            mail.send(msg)
        except Exception:
            # no interrumpir flujo si falla el correo
            pass

        mensaje = "¡Tu cita ha sido registrada exitosamente! Te contactaremos pronto."

    return render_template("cita.html", servicios=servicios, mensaje=mensaje)

# ========== DASHBOARD ADMIN ==========

@app.route("/admin")
@app.route("/dashboard")
def admin_dashboard():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return render_template("admin/dashboard.html")

# ========== GESTIÓN DE CITAS ==========

@app.route("/admin/citas")
def admin_citas():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    citas = Cita.query.order_by(Cita.fecha_hora.desc()).all()
    return render_template("admin/citas.html", citas=citas)

@app.route("/admin/citas/estado/<int:cita_id>/<nuevo_estado>")
def cambiar_estado_cita(cita_id, nuevo_estado):
    if "usuario_id" not in session:
        flash("Debes iniciar sesión como administrador", "danger")
        return redirect(url_for("login"))

    if nuevo_estado not in ['pendiente', 'confirmada', 'completada', 'cancelada']:
        flash("Estado inválido", "danger")
        return redirect(url_for("admin_citas"))

    cita = Cita.query.get_or_404(cita_id)
    cita.estado = nuevo_estado
    db.session.commit()
    flash(f"Estado actualizado a: {nuevo_estado}", "success")
    return redirect(url_for("admin_citas"))

# ========== GESTIÓN DE SERVICIOS ==========

@app.route("/admin/servicios")
def admin_servicios():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    servicios = Servicio.query.order_by(Servicio.nombre).all()
    return render_template("admin/servicios.html", servicios=servicios)

@app.route("/admin/servicios/agregar", methods=["GET", "POST"])
def agregar_servicio():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        nombre = request.form["nombre"]
        descripcion = request.form["descripcion"]
        precio = request.form["precio"]
        activo = True if request.form.get("activo") == "on" else False

        nuevo_servicio = Servicio(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            activo=activo
        )
        db.session.add(nuevo_servicio)
        db.session.commit()
        return redirect(url_for("admin_servicios"))
    return render_template("admin/form_servicio.html", modo="agregar")

@app.route("/admin/servicios/editar/<int:id>", methods=["GET", "POST"])
def editar_servicio(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    servicio = Servicio.query.get_or_404(id)
    if request.method == "POST":
        servicio.nombre = request.form["nombre"]
        servicio.descripcion = request.form["descripcion"]
        servicio.precio = request.form["precio"]
        servicio.activo = True if request.form.get("activo") == "on" else False
        db.session.commit()
        return redirect(url_for("admin_servicios"))
    return render_template("admin/form_servicio.html", servicio=servicio, modo="editar")

@app.route("/admin/servicios/eliminar/<int:id>")
def eliminar_servicio(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    servicio = Servicio.query.get_or_404(id)
    db.session.delete(servicio)
    db.session.commit()
    return redirect(url_for("admin_servicios"))

# ========== ERRORES ==========

@app.errorhandler(404)
def not_found(err):
    # JSON si el cliente lo pide
    if request.accept_mimetypes.best == "application/json" or request.path.startswith("/api/"):
        return jsonify({"error": "Not Found", "type": "NotFound"}), 404
    return render_template("404.html"), 404
