from typing import List, Dict, Any, Optional
import requests
import os
from app_config import MAPPING_FILE
from services import RoomMappingRepository


def fetch_all_resources(api_url: str, client_token: str, access_token: str, page_limit: int = 1000, timeout: int = 30) -> List[Dict[str, Any]]:
    if not api_url:
        raise RuntimeError("Empty api_url passed to fetch_all_resources")

    if "/api/connector" not in api_url:
        api_url = api_url.rstrip("/") + "/api/connector/v1/resources/getAll"

    url = api_url
    headers = {
        "Content-Type": "application/json",
        "Client-Token": client_token,
        "Access-Token": access_token,
    }
    payload: Dict[str, Any] = {
        "ClientToken": client_token,
        "AccessToken": access_token,
        "Client": "EneriaIntegration",
        "Extent": {
            "Resources": True,
            "ResourceCategories": False,
            "ResourceCategoryAssignments": False,
            "ResourceCategoryImageAssignments": False,
            "ResourceFeatures": False,
            "ResourceFeatureAssignments": False,
            "Inactive": False,
        },
        "Limitation": {"Count": page_limit},
    }

    all_resources: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    seen_cursors = set()

    while True:
        if cursor:
            payload["Cursor"] = cursor
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        resources = data.get("Resources") or []
        all_resources.extend(resources)
        cursor = data.get("Cursor")
        if not cursor:
            break
        if cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
        if not resources:
            break

    return all_resources


def update_rooms_mapping(base_url: Optional[str] = None, client_token: Optional[str] = None,
                         access_token: Optional[str] = None, page_limit: Optional[int] = None,
                         out_path: str = "rooms_mapping.json") -> int:
    api_url = base_url or os.getenv("MEWS_BASE_URL")
    client_token = client_token or os.getenv("MEWS_CLIENT_TOKEN")
    access_token = access_token or os.getenv("MEWS_ACCESS_TOKEN")

    if not client_token or not access_token:
        raise RuntimeError("Missing MEWS tokens in environment")

    try:
        if not api_url:
            raise RuntimeError("Missing MEWS_BASE_URL in environment")

        if page_limit and page_limit > 0:
            limit = page_limit
        else:
            limit = 1000

        resources = fetch_all_resources(api_url, client_token, access_token, page_limit=limit)
        mapping_repo = RoomMappingRepository(out_path or MAPPING_FILE)
        mapping_repo.update(resources)
        return len(resources)
    except Exception:
        raise

