"""Lee config.py aplicando valores por defecto para lo que no esté definido."""
from pathlib import Path

try:
    import config as _cfg
except ImportError as e:  # pragma: no cover
    raise SystemExit("Falta config.py. Copia my_config.py como config.py y pon tu TOKEN.") from e

ROOT = Path(__file__).resolve().parent.parent

TOKEN = _cfg.TOKEN
DB_PATH = str(ROOT / getattr(_cfg, "DB_PATH", "padi.db"))

# Cada cuántos minutos se comprueba PADI, y en qué franja horaria
CHECK_EVERY_MINUTES = getattr(_cfg, "CHECK_EVERY_MINUTES", 30)
CHECK_HOURS = getattr(_cfg, "CHECK_HOURS", (8, 21))
CHECK_WEEKENDS = getattr(_cfg, "CHECK_WEEKENDS", False)

# Usuarios del formato antiguo (se importan una vez a la base de datos)
LEGACY_USERS = getattr(_cfg, "users", {})
