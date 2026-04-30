from dataclasses import dataclass
from typing import Optional


class MewsApiError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class RoomStatus:
    room_id: str
    unit_id: int
    room_name: str
    active: bool
    occupied: int
    occupancy_state: Optional[str] = None
