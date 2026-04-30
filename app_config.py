import os


def env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


BASE_URL = os.getenv("MEWS_BASE_URL", "https://api.mews.com/api/connector/v1")
CLIENT_TOKEN = os.getenv("MEWS_CLIENT_TOKEN", "")
ACCESS_TOKEN = os.getenv("MEWS_ACCESS_TOKEN", "")
STAY_SERVICE_ID = os.getenv("MEWS_STAY_SERVICE_ID", "")

HEADERS = {"Content-Type": "application/json"}

MODBUS_HOST = "0.0.0.0"
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "300"))
SHOW_UI = True

MAPPING_FILE = "rooms_mapping.json"

def validate_config():
    missing = []
    if not CLIENT_TOKEN:
        missing.append("MEWS_CLIENT_TOKEN")
    if not ACCESS_TOKEN:
        missing.append("MEWS_ACCESS_TOKEN")
    if not STAY_SERVICE_ID:
        missing.append("MEWS_STAY_SERVICE_ID")

    if missing:
        raise RuntimeError("Variables d'environnement manquantes: " + ", ".join(missing))
