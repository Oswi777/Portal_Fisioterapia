import os
from pathlib import Path
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from sqlalchemy import inspect
from dotenv import load_dotenv

# Carga .env (dev)
load_dotenv()

# ----- Crea la app -----
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-segura-fisiolife")

# ----- Extensiones (sin app) -----
db = SQLAlchemy()
bcrypt = Bcrypt()
mail = Mail()

def _normalize_db_url(url: str) -> str:
    """Convierte 'postgres://' -> 'postgresql+psycopg2://' (Render/Supabase)."""
    if not url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url

def _compute_sqlalchemy_uri() -> str:
    """
    Si hay DATABASE_URL -> úsala (PostgreSQL recomendado en prod).
    Si no, usa SQLite en ./instance/fisiolife.db (dev/pruebas).
    """
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        return _normalize_db_url(env_url)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    sqlite_path = Path(app.instance_path) / "fisiolife.db"
    return f"sqlite:///{sqlite_path.as_posix()}"

# ----- Configuración antes de init_app -----
# Base de datos
app.config["SQLALCHEMY_DATABASE_URI"] = _compute_sqlalchemy_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Mail (ideal mover a .env)
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "lucero.obregon24@gmail.com")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "tcza vvps uryz oedj")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", app.config["MAIL_USERNAME"])

# ----- Inicializa extensiones con la app -----
db.init_app(app)
bcrypt.init_app(app)
mail.init_app(app)

# Importa modelos y rutas ANTES de crear tablas / seed
from app import models  # noqa: E402,F401
from app import routes  # noqa: E402,F401

def _create_tables_if_sqlite():
    """Crea tablas automáticamente SOLO cuando usamos SQLite (dev)."""
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        db.create_all()

def _seed_initial_data():
    """
    Inserta datos iniciales SOLO si:
    - Existen las tablas 'servicios' y 'usuarios'
    - 'servicios' está vacío (o no están los IDs especificados)
    - No existe el usuario admin indicado
    Funciona tanto con SQLite como con PostgreSQL.
    """
    from app.models import Servicio, Usuario

    insp = inspect(db.engine)

    # Si las tablas aún no existen (por ejemplo, en Postgres antes de migrar), no hacemos nada.
    if not (insp.has_table("servicios") and insp.has_table("usuarios")):
        return

    # --- Servicios: insertamos si faltan (idempotente por ID) ---
    servicios_seed = [
        (1, 'Terapia Física General', 'Sesión enfocada en el tratamiento de dolor muscular, articular o lesiones físicas comunes.', 450.00, True),
        (2, 'Rehabilitación Postoperatoria', 'Tratamiento especializado posterior a cirugía ortopédica, neurológica o traumatológica.', 600.00, True),
        (3, 'Terapia Deportiva', 'Optimización de rendimiento, prevención y tratamiento de lesiones deportivas.', 500.00, True),
        (4, 'Terapia Neurológica', 'Atención a pacientes con lesiones neurológicas como parálisis, EVC, Parkinson, etc.', 550.00, True),
        (5, 'Terapia Respiratoria', 'Ejercicios y técnicas para mejorar la función pulmonar y oxigenación.', 400.00, True),
        (6, 'Electroterapia prueba', 'Aplicación de corriente eléctrica para alivio del dolor y mejora del tono muscular. prueba', 349.00, True),
        (7, 'Terapia de Suelo Pélvico', 'Evaluación y tratamiento de disfunciones urinarias, sexuales o de embarazo.', 600.00, True),
    ]

    # ¿Hay registros? Si no hay ninguno, sembramos todo.
    need_commit = False

    try:
        existing_count = db.session.query(models.Servicio).count()
    except Exception:
        # Si por alguna razón la tabla aún no está accesible, abortamos seed.
        return

    if existing_count == 0:
        for sid, nombre, desc, precio, activo in servicios_seed:
            db.session.add(models.Servicio(
                id=sid, nombre=nombre, descripcion=desc, precio=precio, activo=activo
            ))
        need_commit = True
    else:
        # Si ya hay datos, solo aseguramos que existan los IDs clave (idempotente)
        for sid, nombre, desc, precio, activo in servicios_seed:
            if not models.Servicio.query.get(sid):
                db.session.add(models.Servicio(
                    id=sid, nombre=nombre, descripcion=desc, precio=precio, activo=activo
                ))
                need_commit = True

    # --- Usuario admin: si no existe, lo creamos ---
    admin_email = os.getenv("ADMIN_EMAIL", "admin@fisiolife.com")
    admin_nombre = os.getenv("ADMIN_NOMBRE", "Administrador")
    admin_password_env = os.getenv("ADMIN_PASSWORD")  # si lo pones, generamos hash nuevo
    admin_hash_fijo = "$2b$12$QJ.7mgzvs.U6S2Cv0ueh.eV.ICDxSERscj4mpJp0rULeI8cFZax0u"  # tu hash provisto

    if not models.Usuario.query.filter_by(email=admin_email).first():
        if admin_password_env:
            pwd_hash = bcrypt.generate_password_hash(admin_password_env).decode()
        else:
            # Usamos el hash que nos diste (bcrypt) si no definiste ADMIN_PASSWORD
            pwd_hash = admin_hash_fijo

        db.session.add(models.Usuario(
            id=1,  # opcional; puedes omitir para autoincrement
            nombre=admin_nombre,
            email=admin_email,
            password=pwd_hash,
            rol="admin",
            creado_en=datetime(2025, 7, 19, 21, 35, 19)  # fecha de tu insert; o datetime.utcnow()
        ))
        need_commit = True

    if need_commit:
        db.session.commit()

with app.app_context():
    # 1) Crea tablas automáticamente si estamos en SQLite (dev)
    _create_tables_if_sqlite()
    # 2) Intenta sembrar datos iniciales si las tablas existen (SQLite o Postgres)
    _seed_initial_data()
