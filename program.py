import requests
from datetime import datetime, timedelta, UTC
import threading
import time
import logging
import json
import os
import sys

from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusDeviceContext
)

# ============================================================
# CONFIG
# ============================================================

def load_env_file(env_path=".env"):
    """Charge un fichier .env simple (KEY=VALUE) si présent."""
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


load_env_file()

BASE_URL = os.getenv("MEWS_BASE_URL", "https://api.mews.com/api/connector/v1")

# Credentials API MEWS (doivent venir des variables d'environnement)
CLIENT_TOKEN = os.getenv("MEWS_CLIENT_TOKEN", "")
ACCESS_TOKEN = os.getenv("MEWS_ACCESS_TOKEN", "")

HEADERS = {"Content-Type": "application/json"}

# Configuration Modbus
MODBUS_HOST = "0.0.0.0"    # 0.0.0.0 = écoute sur toutes les interfaces
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "300"))

MAPPING_FILE = "rooms_mapping.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("MEWS-ROOMS")


class MewsApiError(Exception):
    """Erreur API MEWS avec statut HTTP."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


def validate_config():
    """Valide la configuration avant démarrage."""
    missing = []
    if not CLIENT_TOKEN:
        missing.append("MEWS_CLIENT_TOKEN")
    if not ACCESS_TOKEN:
        missing.append("MEWS_ACCESS_TOKEN")

    if missing:
        raise RuntimeError(
            "Variables d'environnement manquantes: " + ", ".join(missing)
        )


# ============================================================
# MAPPING PERSISTANT (CHAMBRE → UNIT ID)
# ============================================================

def load_persistent_mapping():
    """
    Charge le mapping persistant depuis le fichier JSON.
    Format: {"room_id": unit_id, ...}
    """
    try:
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mapping", {})
    except FileNotFoundError:
        return {}

def save_persistent_mapping(mapping):
    """Sauvegarde le mapping persistant."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "mapping": mapping,
        "description": "Mapping persistant Unit ID <-> Chambre (ne change jamais)"
    }
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def update_mapping(rooms):
    """
    Met à jour le mapping en ajoutant uniquement les nouvelles chambres.
    Ne supprime JAMAIS les anciennes.
    Retourne: (mapping complet {room_id: unit_id}, set des room_id actifs)
    """
    mapping = load_persistent_mapping()
    rooms_actives = {room["Id"] for room in rooms}
    
    # Trouver le prochain Unit ID disponible
    if mapping:
        next_unit_id = max(mapping.values()) + 1
    else:
        next_unit_id = 1
    
    # Ajouter les nouvelles chambres uniquement
    for room in rooms:
        room_id = room["Id"]
        if room_id not in mapping:
            mapping[room_id] = next_unit_id
            log.info(f"Nouvelle chambre : {room.get('Name', 'N/A')} → Unit ID {next_unit_id}")
            next_unit_id += 1
    
    save_persistent_mapping(mapping)
    return mapping, rooms_actives


# ============================================================
# API MEWS
# ============================================================

def call(endpoint, payload):
    """Appel API Mews"""
    payload.update({
        "ClientToken": CLIENT_TOKEN,
        "AccessToken": ACCESS_TOKEN,
        "Client": "EneriaIntegration"
    })

    response = requests.post(
        f"{BASE_URL}/{endpoint}",
        json=payload,
        headers=HEADERS,
        timeout=30
    )

    if response.status_code != 200:
        message = f"Erreur API: {response.status_code} {response.text}"
        log.error(message)
        raise MewsApiError(response.status_code, message)

    return response.json()


def fetch_rooms():
    """Récupère toutes les chambres"""
    rooms_data = call("resources/getAll", {"Limitation": {"Count": 200}})
    return rooms_data.get("Resources", [])


def fetch_reservations():
    """Récupère les réservations actives"""
    now = datetime.now(UTC)
    start_utc = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_utc = (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    payload = {
        "StartUtc": start_utc,
        "EndUtc": end_utc,
        "Limitation": {"Count": 200}
    }
    
    reservations_data = call("reservations/getAll", payload)
    return reservations_data.get("Reservations", [])


def analyse_occupation(rooms, reservations):
    """
    Analyse l'occupation des chambres (OCCUPÉ ou DISPONIBLE).
    Retourne un dict: {room_id: {"occupied": bool, "room_name": str, "room_number": str}}
    """
    now = datetime.now(UTC)
    occupied_room_ids = set()
    
    # Trouver les chambres occupées (avec réservation active)
    for reservation in reservations:
        try:
            state = reservation.get("State")
            start_str = reservation.get("StartUtc", "")
            end_str = reservation.get("EndUtc", "")
            
            if not start_str or not end_str:
                continue
                
            start = datetime.fromisoformat(start_str.replace("Z", "")).replace(tzinfo=UTC)
            end = datetime.fromisoformat(end_str.replace("Z", "")).replace(tzinfo=UTC)
            
            # Réservation active = état Confirmed ou Started ET période actuelle
            if state in ["Confirmed", "Started"] and start <= now < end:
                resource_id = reservation.get("AssignedResourceId")
                if resource_id:
                    occupied_room_ids.add(resource_id)
        except Exception as e:
            log.warning(f"Erreur parsing réservation: {e}")
            continue
    
    # Créer le résultat pour chaque chambre
    resultats = {}
    for room in rooms:
        room_id = room.get("Id")
        room_name = room.get("Name", "N/A")
        
        # Extraire le numéro de chambre
        room_number = ''.join(filter(str.isdigit, room_name)) or "0"
        
        resultats[room_id] = {
            "occupied": room_id in occupied_room_ids,
            "room_name": room_name,
            "room_number": room_number
        }
    
    return resultats


# ============================================================
# SERVEUR MODBUS
# ============================================================

class MewsRoomsModbus:

    def __init__(self):
        self.running = False
        self.room_names = {}  # Pour stocker les noms {room_id: name}
        
        # Chargement initial
        rooms = fetch_rooms()

        if not rooms:
            raise RuntimeError(
                "Aucune chambre récupérée depuis MEWS. Vérifiez les tokens et l'environnement API."
            )
        
        # Charger/mettre à jour le mapping persistant
        self.room_to_unit, self.rooms_actives = update_mapping(rooms)
        
        # Sauvegarder les noms de chambres pour l'affichage
        for room in rooms:
            self.room_names[room["Id"]] = room.get("Name", "N/A")
        
        log.info(f"Chambres trouvées dans l'API : {len(rooms)}")
        log.info(f"Unit IDs totaux (historique) : {len(self.room_to_unit)}")

        # Créer les devices Modbus pour TOUTES les chambres
        devices = {}
        for room_id, unit_id in self.room_to_unit.items():
            devices[unit_id] = ModbusDeviceContext(
                hr=ModbusSequentialDataBlock(0, [0] * 1),
                ir=ModbusSequentialDataBlock(0, [0] * 1)
            )
            
            status = "ACTIVE" if room_id in self.rooms_actives else "INACTIVE"
            room_name = self.room_names.get(room_id, "Inconnue")
            log.info(f"  Unit ID {unit_id:3d} → {room_name:20s} [{status}]")

        self.context = ModbusServerContext(
            devices=devices,
            single=False
        )

    def update_registers(self):
        """Met à jour les registres Modbus avec les données actuelles"""
        try:
            rooms = fetch_rooms()
            reservations = fetch_reservations()
            occupation = analyse_occupation(rooms, reservations)
            api_error = 0
            
            log.info(f"Mise à jour: {len(rooms)} chambres, {len(reservations)} réservations")
        except MewsApiError as e:
            log.error(f"Echec API MEWS pendant update: {e}")
            occupation = {}
            api_error = 1
        except Exception as e:
            log.error(f"Erreur lors de la récupération des données: {e}")
            occupation = {}
            api_error = 1
        
        # Compteurs globaux
        total_occupied = sum(1 for info in occupation.values() if info["occupied"])
        total_available = len(occupation) - total_occupied

        # Mise à jour de chaque Unit ID
        for room_id, unit_id in self.room_to_unit.items():
            # Récupérer les données d'occupation
            if room_id in occupation:
                info = occupation[room_id]
                occupied = 1 if info["occupied"] else 0
            else:
                occupied = 0
            
            # Structure des registres:
            # 0: Occupé (1=occupé, 0=disponible)
            
            values = [occupied]

            # Mise à jour HR (3) et IR (4)
            device = self.context[unit_id]
            device.setValues(3, 0, values)
            device.setValues(4, 0, values)

        log.info(f"✅ Mise à jour terminée | Occupées: {total_occupied}, Disponibles: {total_available}, Erreur API: {api_error}")

    def loop(self):
        """Boucle de mise à jour périodique"""
        while self.running:
            time.sleep(POLLING_INTERVAL)
            self.update_registers()

    def start(self):
        """Démarre le serveur Modbus"""
        self.running = True
        self.update_registers()  # Mise à jour initiale

        # Démarrer la boucle de mise à jour en arrière plan
        threading.Thread(target=self.loop, daemon=True).start()

        log.info(f"🚀 Serveur Modbus TCP démarré sur {MODBUS_HOST}:{MODBUS_PORT}")
        log.info(f"📊 Mise à jour toutes les {POLLING_INTERVAL} secondes")
        log.info("")
        log.info("STRUCTURE DES REGISTRES (par Unit ID):")
        log.info("  Registre 0: Occupé (1=occupé, 0=disponible)")
        
        # Démarrer le serveur (bloquant)
        StartTcpServer(
            context=self.context,
            address=(MODBUS_HOST, MODBUS_PORT)
        )


# ============================================================# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print(" MEWS API → MODBUS TCP SERVER")
    print(" Exposition des chambres disponibles via Modbus")
    print("="*60)
    print(" Ctrl+C pour arrêter\n")

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
