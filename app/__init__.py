import os
from pathlib import Path
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from sqlalchemy import inspect
from dotenv import load_dotenv

# Carga .env (solo dev/local)
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

    # Fallback SQLite
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    sqlite_path = Path(app.instance_path) / "fisiolife.db"
    return f"sqlite:///{sqlite_path.as_posix()}"

# ----- Configuración antes de init_app -----
# Base de datos
app.config["SQLALCHEMY_DATABASE_URI"] = _compute_sqlalchemy_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Mail (solo por .env; sin valores duros)
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")  # <-- no default
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")  # <-- no default
# Si MAIL_DEFAULT_SENDER no se define, intenta usar el username; si tampoco hay, queda None
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME")

# ----- Inicializa extensiones con la app -----
db.init_app(app)
bcrypt.init_app(app)
mail.init_app(app)

# Importa modelos y rutas ANTES de crear tablas / seed
from app.models import Servicio, Usuario  # noqa: E402
from app import routes  # noqa: E402

def _create_tables_if_sqlite():
    """Crea tablas automáticamente SOLO cuando usamos SQLite (dev)."""
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        db.create_all()

def _seed_initial_data():
    """
    Inserta datos iniciales si:
    - Existen las tablas 'servicios' y 'usuarios'
    - Y faltan registros base (idempotente)
    Funciona con SQLite / PostgreSQL.
    """
    insp = inspect(db.engine)

    # Si las tablas aún no existen (p. ej. en Postgres sin migrar), no hacemos nada.
    if not (insp.has_table("servicios") and insp.has_table("usuarios")):
        return

    need_commit = False

    # --- Servicios (idempotente) ---
    servicios_seed = [
        (1, 'Terapia Física General', 'Sesión enfocada en el tratamiento de dolor muscular, articular o lesiones físicas comunes.', 450.00, True),
        (2, 'Rehabilitación Postoperatoria', 'Tratamiento especializado posterior a cirugía ortopédica, neurológica o traumatológica.', 600.00, True),
        (3, 'Terapia Deportiva', 'Optimización de rendimiento, prevención y tratamiento de lesiones deportivas.', 500.00, True),
        (4, 'Terapia Neurológica', 'Atención a pacientes con lesiones neurológicas como parálisis, EVC, Parkinson, etc.', 550.00, True),
        (5, 'Terapia Respiratoria', 'Ejercicios y técnicas para mejorar la función pulmonar y oxigenación.', 400.00, True),
        (6, 'Electroterapia prueba', 'Aplicación de corriente eléctrica para alivio del dolor y mejora del tono muscular. prueba', 349.00, True),
        (7, 'Terapia de Suelo Pélvico', 'Evaluación y tratamiento de disfunciones urinarias, sexuales o de embarazo.', 600.00, True),
    ]

    try:
        existing_count = db.session.query(Servicio).count()
    except Exception:
        # Si la tabla no está accesible aún, salimos silenciosamente
        return

    if existing_count == 0:
        for sid, nombre, desc, precio, activo in servicios_seed:
            db.session.add(Servicio(id=sid, nombre=nombre, descripcion=desc, precio=precio, activo=activo))
        need_commit = True
    else:
        for sid, nombre, desc, precio, activo in servicios_seed:
            if not Servicio.query.get(sid):
                db.session.add(Servicio(id=sid, nombre=nombre, descripcion=desc, precio=precio, activo=activo))
                need_commit = True

    # --- Usuario admin (idempotente) ---
    admin_email = os.getenv("ADMIN_EMAIL", "admin@fisiolife.com")
    admin_nombre = os.getenv("ADMIN_NOMBRE", "Administrador")
    admin_password_env = os.getenv("ADMIN_PASSWORD")  # si se define, generamos un hash nuevo
    # Hash provisto (bcrypt), se usa solo si no defines ADMIN_PASSWORD
    admin_hash_fijo = "$2b$12$QJ.7mgzvs.U6S2Cv0ueh.eV.ICDxSERscj4mpJp0rULeI8cFZax0u"

    if not Usuario.query.filter_by(email=admin_email).first():
        if admin_password_env:
            pwd_hash = bcrypt.generate_password_hash(admin_password_env).decode()
        else:
            pwd_hash = admin_hash_fijo

        db.session.add(Usuario(
            id=1,  # opcional; puedes omitir para autoincrement
            nombre=admin_nombre,
            email=admin_email,
            password=pwd_hash,
            rol="admin",
            creado_en=datetime(2025, 7, 19, 21, 35, 19)  # o datetime.utcnow()
        ))
        need_commit = True

    if need_commit:
        db.session.commit()

with app.app_context():
    # 1) Crea tablas automáticamente si estamos en SQLite (dev)
    _create_tables_if_sqlite()
    # 2) Intenta sembrar datos iniciales si las tablas existen (SQLite o Postgres)
    _seed_initial_data()
