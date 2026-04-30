import sys
import os
from env_loader import load_env_file

load_env_file()

from app_config import validate_config
from domain import MewsApiError
from modbus_server import MewsRoomsModbus
from mews_client import update_rooms_mapping

if __name__ == "__main__":
    try:
        validate_config()
    except RuntimeError as e:
        sys.exit(str(e))

    try:
        skip_update = os.getenv("SKIP_MEWS_UPDATE", "false").lower() in ("1", "true", "yes")
        if not skip_update:
            update_rooms_mapping()
    except Exception:
        pass

    try:
        server = MewsRoomsModbus()
        server.start()
    except MewsApiError as e:
        sys.exit(str(e))
    except RuntimeError as e:
        sys.exit(str(e))
