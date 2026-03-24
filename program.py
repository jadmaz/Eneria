import sys
from app_config import MOCK_MODE, MOCK_ROOM_COUNT, log, validate_config
from domain import MewsApiError
from modbus_server import MewsRoomsModbus

if __name__ == "__main__":
    if MOCK_MODE:
        log.warning("Mode test MOCK active via .env (MOCK_MODE=true)")
        log.warning(f"Nombre de chambres mock: {max(1, MOCK_ROOM_COUNT)}")

    try:
        validate_config()
    except RuntimeError as e:
        log.error(str(e))
        log.error("Configurez les variables d'environnement avant de lancer le serveur.")
        sys.exit(1)

    try:
        server = MewsRoomsModbus()
        server.start()
    except MewsApiError as e:
        log.error(f"Connexion MEWS refusée: {e}")
        log.error("Vérifiez MEWS_CLIENT_TOKEN, MEWS_ACCESS_TOKEN et MEWS_BASE_URL dans .env")
        sys.exit(1)
    except RuntimeError as e:
        log.error(str(e))
        sys.exit(1)
