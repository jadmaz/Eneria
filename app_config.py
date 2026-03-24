import logging
import os


def load_env_file(env_path=".env"):
    """Load a simple .env file (KEY=VALUE) if present."""
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as file_obj:
        for line in file_obj:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


load_env_file()


def env_bool(name, default=False):
    """Read a boolean from environment (true/false, 1/0, yes/no)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


BASE_URL = os.getenv("MEWS_BASE_URL", "https://api.mews.com/api/connector/v1")
CLIENT_TOKEN = os.getenv("MEWS_CLIENT_TOKEN", "")
ACCESS_TOKEN = os.getenv("MEWS_ACCESS_TOKEN", "")

HEADERS = {"Content-Type": "application/json"}

MODBUS_HOST = "0.0.0.0"
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "300"))
MOCK_MODE = env_bool("MOCK_MODE", False)
MOCK_ROOM_COUNT = int(os.getenv("MOCK_ROOM_COUNT", "10"))
SHOW_UI = env_bool("SHOW_UI", True)

MAPPING_FILE = "rooms_mapping.json"

log = logging.getLogger("MEWS-ROOMS")
log.addHandler(logging.NullHandler())
log.propagate = False


def validate_config():
    """Validate required config before startup."""
    if MOCK_MODE:
        return

    missing = []
    if not CLIENT_TOKEN:
        missing.append("MEWS_CLIENT_TOKEN")
    if not ACCESS_TOKEN:
        missing.append("MEWS_ACCESS_TOKEN")

    if missing:
        raise RuntimeError("Variables d'environnement manquantes: " + ", ".join(missing))
