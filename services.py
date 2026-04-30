import json
from datetime import datetime, timedelta, UTC

import requests

from domain import MewsApiError


class RoomMappingRepository:
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
        }
        with open(self.mapping_file, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=2, ensure_ascii=False)

    def update(self, rooms):
        mapping = self.load()
        active_rooms = {room["Id"] for room in rooms}
        room_to_unit = {}
        next_unit_id = max(mapping.values()) + 1 if mapping else 1
        groups = {}
        for room in rooms:
            room_id = room.get("Id")
            room_name = room.get("Name", "N/A")
            data = room.get("Data") or {}
            value = data.get("Value") or {}
            floor = value.get("FloorNumber") or "Unknown"
            base_key = f"{room_name}-{floor}"
            groups.setdefault(base_key, []).append(room_id)

        for base_key in sorted(groups.keys()):
            room_id = sorted(groups[base_key])[0]
            key = base_key
            if key not in mapping:
                if next_unit_id >= 255:
                    break
                mapping[key] = next_unit_id
                next_unit_id += 1
            room_to_unit[room_id] = mapping[key]
            if next_unit_id >= 255:
                break

        self.save(mapping)
        return room_to_unit, active_rooms


class MewsApiClient:
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
            raise MewsApiError(response.status_code, message)

        return response.json()

    def fetch_rooms(self):
        rooms_data = self.call("resources/getAll", {"Limitation": {"Count": 1000}})
        return rooms_data.get("Resources", [])

