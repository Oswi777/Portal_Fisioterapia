from flask import render_template, request, redirect, url_for, session
from app import app, db, bcrypt
from app.models import Usuario

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and bcrypt.check_password_hash(usuario.password, password):
            session["usuario_id"] = usuario.id
            session["usuario_nombre"] = usuario.nombre
            return redirect(url_for("dashboard"))
        else:
            error = "Correo o contraseña incorrectos"
    
    return render_template("login.html", error=error)

@app.route("/dashboard")
def dashboard():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
