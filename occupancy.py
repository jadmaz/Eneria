from datetime import datetime, UTC

from app_config import log


def analyse_occupation(rooms, reservations):
    """Build room occupancy from current reservations."""
    now = datetime.now(UTC)
    occupied_room_ids = set()

    for reservation in reservations:
        try:
            state = reservation.get("State")
            start_str = reservation.get("StartUtc", "")
            end_str = reservation.get("EndUtc", "")

            if not start_str or not end_str:
                continue

            start = datetime.fromisoformat(start_str.replace("Z", "")).replace(tzinfo=UTC)
            end = datetime.fromisoformat(end_str.replace("Z", "")).replace(tzinfo=UTC)

            if state in ["Confirmed", "Started"] and start <= now < end:
                resource_id = reservation.get("AssignedResourceId")
                if resource_id:
                    occupied_room_ids.add(resource_id)
        except Exception as exc:
            log.warning(f"Erreur parsing reservation: {exc}")
            continue

    result = {}
    for room in rooms:
        room_id = room.get("Id")
        room_name = room.get("Name", "N/A")
        room_number = "".join(filter(str.isdigit, room_name)) or "0"

        result[room_id] = {
            "occupied": room_id in occupied_room_ids,
            "room_name": room_name,
            "room_number": room_number,
        }

    return result


def generate_mock_rooms(count):
    """Generate fake rooms for mock mode."""
    rooms = []
    for index in range(1, max(1, count) + 1):
        rooms.append({"Id": f"mock-room-{index:03d}", "Name": f"Mock Room {100 + index}"})
    return rooms


def generate_mock_occupation(rooms):
    """Generate deterministic occupancy for tests."""
    result = {}
    for idx, room in enumerate(rooms):
        room_id = room.get("Id")
        room_name = room.get("Name", "N/A")
        room_number = "".join(filter(str.isdigit, room_name)) or "0"
        occupied = (idx % 3) == 0

        result[room_id] = {
            "occupied": occupied,
            "room_name": room_name,
            "room_number": room_number,
        }

    return result
