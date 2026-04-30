from typing import Dict, List, Any, Iterable, Optional


def chunkArray(items: List[str], size: int) -> Iterable[List[str]]:
    if size <= 0:
        raise ValueError("chunk size must be > 0")
    for i in range(0, len(items), size):
        yield items[i : i + size]


def getResources(api_client, limit: int = 1000) -> List[Dict[str, Any]]:
    resources_by_id: Dict[str, Dict[str, Any]] = {}
    cursor: Optional[str] = None
    seen_cursors = set()

    while True:
        payload: Dict[str, Any] = {
            "Extent": {
                "Resources": True,
                "Inactive": False,
            },
            "Limitation": {"Count": limit},
        }
        if cursor:
            payload["Limitation"]["Cursor"] = cursor

        data = api_client.call("resources/getAll", payload)
        page_resources = data.get("Resources") or []
        for resource in page_resources:
            resource_id = resource.get("Id")
            if resource_id:
                resources_by_id[resource_id] = resource

        cursor = data.get("Cursor")
        if not cursor:
            break
        if cursor in seen_cursors:
            break
        seen_cursors.add(cursor)

    resources = list(resources_by_id.values())
    return resources


def getResourceCategories(api_client, service_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
    categories_by_id: Dict[str, Dict[str, Any]] = {}
    cursor: Optional[str] = None
    seen_cursors = set()

    while True:
        payload: Dict[str, Any] = {
            "ServiceIds": [service_id],
            "ActivityStates": ["Active"],
            "Limitation": {"Count": limit},
        }
        if cursor:
            payload["Limitation"]["Cursor"] = cursor

        data = api_client.call("resourceCategories/getAll", payload)
        page_categories = data.get("ResourceCategories") or []
        for category in page_categories:
            category_id = category.get("Id")
            if category_id:
                categories_by_id[category_id] = category

        cursor = data.get("Cursor")
        if not cursor:
            break
        if cursor in seen_cursors:
            break
        seen_cursors.add(cursor)

    categories = list(categories_by_id.values())
    return categories


def getOccupancyStatesByCategoryIds(api_client, resource_category_ids: List[str]) -> Dict[str, str]:
    occupancy_map: Dict[str, str] = {}

    for chunk in chunkArray(resource_category_ids, 5):
        payload = {
            "ResourceCategoryIds": chunk,
            "OccupancyStates": [
                "Vacant",
                "Reserved",
                "ReservedLocked",
                "InternalUse",
                "OutOfOrder",
            ],
        }
        data = api_client.call("resources/getOccupancyState", payload)
        resource_states = data.get("ResourceOccupancyStates")
        if resource_states is None:
            rc_states = data.get("ResourceCategoryOccupancyStates") or []
            resource_states = []
            for rc_state in rc_states:
                resource_states.extend(rc_state.get("ResourceOccupancyStates") or [])

        for entry in resource_states or []:
            resource_id = entry.get("ResourceId")
            occupancy_state = entry.get("OccupancyState")
            if resource_id and occupancy_state:
                occupancy_map[resource_id] = occupancy_state

    return occupancy_map


def buildRoomsWithOccupancy(rooms: List[Dict[str, Any]], occupancy_map: Dict[str, str]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for room in rooms:
        room_id = room.get("Id")
        room_name = room.get("Name")
        data = room.get("Data") or {}
        value = data.get("Value") or {}
        floor = value.get("FloorNumber")

        occupancy_state = occupancy_map.get(room_id)
        if occupancy_state in ("Vacant", "OutOfOrder"):
            is_occupied = False
        elif occupancy_state in ("Reserved", "ReservedLocked", "InternalUse"):
            is_occupied = True
        else:
            occupancy_state = "Unknown"
            is_occupied = None

        result.append(
            {
                "id": room_id,
                "name": room_name,
                "floor": floor,
                "occupancyState": occupancy_state,
                "isOccupied": is_occupied,
            }
        )

    return result
