from app import db
from datetime import datetime

# Tabla: usuarios
class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum('admin', 'staff'), default='admin')
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, index=True)

# Tabla: servicios
class Servicio(db.Model):
    __tablename__ = 'servicios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    activo = db.Column(db.Boolean, default=True)

    citas = db.relationship('Cita', backref='servicio', lazy=True)

# Tabla: citas
class Cita(db.Model):
    __tablename__ = 'citas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    servicio_id = db.Column(db.Integer, db.ForeignKey('servicios.id'), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False, index=True)
    mensaje = db.Column(db.Text)
    # importante: incluye 'completada' porque la usas en rutas/admin
    estado = db.Column(db.Enum('pendiente', 'confirmada', 'completada', 'cancelada'), default='pendiente')
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, index=True)
