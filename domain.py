from dataclasses import dataclass


class MewsApiError(Exception):
    """MEWS API error carrying HTTP status code."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class RoomStatus:
    """Current room status used by UI."""

    room_id: str
    unit_id: int
    room_name: str
    active: bool
    occupied: int
