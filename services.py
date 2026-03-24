import json
from datetime import datetime, timedelta, UTC

import requests

from app_config import log
from domain import MewsApiError


class RoomMappingRepository:
    """Persistent storage for room_id -> unit_id mapping."""

    def __init__(self, mapping_file):
        self.mapping_file = mapping_file

    def load(self):
        try:
            with open(self.mapping_file, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
                return data.get("mapping", {})
        except FileNotFoundError:
            return {}

    def save(self, mapping):
        data = {
            "timestamp": datetime.now().isoformat(),
            "mapping": mapping,
            "description": "Mapping persistant Unit ID <-> Chambre (ne change jamais)",
        }
        with open(self.mapping_file, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=2, ensure_ascii=False)

    def update(self, rooms):
        mapping = self.load()
        active_rooms = {room["Id"] for room in rooms}

        next_unit_id = max(mapping.values()) + 1 if mapping else 1
        for room in rooms:
            room_id = room["Id"]
            if room_id not in mapping:
                mapping[room_id] = next_unit_id
                log.info(
                    f"Nouvelle chambre : {room.get('Name', 'N/A')} -> Unit ID {next_unit_id}"
                )
                next_unit_id += 1

        self.save(mapping)
        return mapping, active_rooms


class MewsApiClient:
    """Client wrapper around MEWS endpoints."""

    def __init__(self, base_url, client_token, access_token, headers):
        self.base_url = base_url
        self.client_token = client_token
        self.access_token = access_token
        self.headers = headers

    def call(self, endpoint, payload):
        request_payload = dict(payload)
        request_payload.update(
            {
                "ClientToken": self.client_token,
                "AccessToken": self.access_token,
                "Client": "EneriaIntegration",
            }
        )

        response = requests.post(
            f"{self.base_url}/{endpoint}",
            json=request_payload,
            headers=self.headers,
            timeout=30,
        )

        if response.status_code != 200:
            message = f"Erreur API: {response.status_code} {response.text}"
            log.error(message)
            raise MewsApiError(response.status_code, message)

        return response.json()

    def fetch_rooms(self):
        rooms_data = self.call("resources/getAll", {"Limitation": {"Count": 200}})
        return rooms_data.get("Resources", [])

    def fetch_reservations(self):
        now = datetime.now(UTC)
        start_utc = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc = (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "StartUtc": start_utc,
            "EndUtc": end_utc,
            "Limitation": {"Count": 200},
        }

        reservations_data = self.call("reservations/getAll", payload)
        return reservations_data.get("Reservations", [])
