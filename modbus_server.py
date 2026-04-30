import asyncio
import threading
import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from app_config import (
    ACCESS_TOKEN,
    BASE_URL,
    HEADERS,
    MAPPING_FILE,
    MODBUS_HOST,
    MODBUS_PORT,
    POLLING_INTERVAL,
    SHOW_UI,
    CLIENT_TOKEN,
    STAY_SERVICE_ID,
)
from domain import RoomStatus
from mews_occupancy import (
    getResources,
    getResourceCategories,
    getOccupancyStatesByCategoryIds,
    buildRoomsWithOccupancy,
)
from services import MewsApiClient, RoomMappingRepository


class MewsRoomsModbus:
    def __init__(self):
        self.running = False
        self.status_lock = threading.Lock()
        self.api_client = MewsApiClient(BASE_URL, CLIENT_TOKEN, ACCESS_TOKEN, HEADERS)
        self.mapping_repo = RoomMappingRepository(MAPPING_FILE)
        self.latest_status = {}
        self.room_names = {}
        self.room_floors = {}
        self.sim_devices = []
        self.server = None
        self.server_ready = threading.Event()
        rooms = self._load_initial_rooms()
        self._cached_rooms = rooms

        self.room_to_unit, self.rooms_actives = self.mapping_repo.update(rooms)
        self._cache_room_names(rooms)
        self._initialize_status_cache()

        self.sim_devices = self._build_modbus_devices()

    def _load_initial_rooms(self):
        return getResources(self.api_client, limit=1000)

    def _cache_room_names(self, rooms):
        for room in rooms:
            self.room_names[room["Id"]] = room.get("Name", "N/A")
            floor = None
            data = room.get("Data") or {}
            value = data.get("Value") or {}
            floor = value.get("FloorNumber")
            self.room_floors[room["Id"]] = floor

    def _initialize_status_cache(self):
        for room_id, unit_id in self.room_to_unit.items():
            self.latest_status[room_id] = RoomStatus(
                room_id=room_id,
                unit_id=unit_id,
                room_name=self.room_names.get(room_id, "Inconnue"),
                active=room_id in self.rooms_actives,
                occupied=0,
            )

    def _build_modbus_devices(self):
        devices = []
        for room_id, unit_id in self.room_to_unit.items():
            if unit_id >= 255:
                continue
            devices.append(
                SimDevice(
                    unit_id,
                    simdata=[
                        SimData(0, values=0, datatype=DataType.REGISTERS),
                    ],
                )
            )
        return devices

    def _get_runtime_device(self, unit_id):
        if self.server is None:
            return None

        context = getattr(self.server, "context", None)
        if context is None or not hasattr(context, "devices"):
            return None

        return context.devices.get(unit_id)

    def _fetch_rooms_and_occupation(self, cached_rooms=None):
        try:
            rooms = cached_rooms or getResources(self.api_client, limit=1000)
            if not STAY_SERVICE_ID:
                raise RuntimeError("Missing MEWS_STAY_SERVICE_ID in environment")
            service_id = STAY_SERVICE_ID
            categories = getResourceCategories(self.api_client, service_id, limit=1000)
            category_ids = [cat.get("Id") for cat in categories if cat.get("Id")]
            occupancy_map = getOccupancyStatesByCategoryIds(self.api_client, category_ids)
            rooms_with_occ = buildRoomsWithOccupancy(rooms, occupancy_map)

            rooms = [{"Id": r["id"], "Name": r["name"]} for r in rooms_with_occ]
            occupation = {}
            for r in rooms_with_occ:
                room_id = r["id"]
                room_name = r.get("name", "N/A")
                room_number = "".join(filter(str.isdigit, room_name)) or "0"
                occ_state = r.get("occupancyState")
                is_occ = r.get("isOccupied")
                occupation[room_id] = {
                    "occupied": True if is_occ is True else False if is_occ is False else None,
                    "room_name": room_name,
                    "room_number": room_number,
                    "occupancy_state": occ_state,
                }
            api_error = 0
        except Exception:
            rooms = []
            occupation = {}
            api_error = 1

        return rooms, occupation, api_error

    def update_registers(self):
        cached_rooms = self._cached_rooms
        self._cached_rooms = None
        rooms, occupation, api_error = self._fetch_rooms_and_occupation(cached_rooms)

        active_room_ids = {room.get("Id") for room in rooms}

        for room_id, unit_id in self.room_to_unit.items():
            occupied = 0
            occ_state = None
            if room_id in occupation:
                occ_flag = occupation[room_id].get("occupied", False)
                occ_state = occupation[room_id].get("occupancy_state")
                if occ_flag is True:
                    occupied = 1
                else:
                    occupied = 0

            with self.status_lock:
                self.latest_status[room_id] = RoomStatus(
                    room_id=room_id,
                    unit_id=unit_id,
                    room_name=self.room_names.get(room_id, "Inconnue"),
                    active=room_id in active_room_ids,
                    occupied=occupied,
                    occupancy_state=occ_state,
                )

            runtime_device = self._get_runtime_device(unit_id)
            if runtime_device is not None:
                block = runtime_device.block.get("x") or runtime_device.block.get("h") or runtime_device.block.get("i")
                if block is not None:
                    block[2][0] = occupied

    async def _serve_modbus_server(self):
        self.server = ModbusTcpServer(self.sim_devices, address=(MODBUS_HOST, MODBUS_PORT))
        self.server_ready.set()
        await self.server.serve_forever()

    def run_modbus_server(self):
        asyncio.run(self._serve_modbus_server())

    def run_ui(self):
        root = tk.Tk()
        root.title("Eneria - Statut des chambres")
        root.geometry("760x520")

        title = ttk.Label(root, text="Statut des chambres (temps reel)")
        title.pack(anchor="w", padx=12, pady=(12, 4))

        info = ttk.Label(
            root,
            text=f"Modbus TCP: {MODBUS_HOST}:{MODBUS_PORT}",
        )
        info.pack(anchor="w", padx=12, pady=(0, 8))

        columns = ("unit", "room", "status")
        tree = ttk.Treeview(root, columns=columns, show="headings", height=18)
        tree.heading("unit", text="Unit ID")
        tree.heading("room", text="Chambre")
        tree.heading("status", text="Statut")
        tree.column("unit", width=90, anchor="center")
        tree.column("room", width=360, anchor="w")
        tree.column("status", width=160, anchor="center")

        scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        scrollbar.pack(side="right", fill="y", padx=(0, 12), pady=(0, 12))

        floors = sorted({f for f in self.room_floors.values() if f not in (None, "")})
        floors_display = ["Tous"] + [str(f) for f in floors]
        selected_floor = tk.StringVar(value="Tous")
        floor_label = ttk.Label(root, text="Etage:")
        floor_label.pack(anchor="w", padx=12, pady=(0, 4))
        floor_combo = ttk.Combobox(root, textvariable=selected_floor, values=floors_display, state="readonly")
        floor_combo.pack(anchor="w", padx=12, pady=(0, 8))

        def populate_tree():
            tree.delete(*tree.get_children())
            chosen = selected_floor.get()

            with self.status_lock:
                snapshot = dict(self.latest_status)

            for room_id, unit_id in sorted(self.room_to_unit.items(), key=lambda item: item[1]):
                room_name = self.room_names.get(room_id, "Inconnue")
                floor = self.room_floors.get(room_id)
                if chosen != "Tous" and str(floor) != chosen:
                    continue

                status = snapshot.get(room_id)
                state_label = {
                    "Vacant": "Libre",
                    "Reserved": "Réservé",
                    "ReservedLocked": "Réservé (verrouillé)",
                    "InternalUse": "Usage interne",
                    "OutOfOrder": "Hors service",
                    "Unknown": "Inconnu",
                }
                label = state_label.get(getattr(status, "occupancy_state", None), "Inconnu")

                tree.insert("", "end", iid=room_id, values=(unit_id, room_name, label))

        floor_combo.bind("<<ComboboxSelected>>", lambda _event: populate_tree())
        populate_tree()

        def refresh_ui():
            with self.status_lock:
                snapshot = dict(self.latest_status)

            for room_id, status in snapshot.items():
                if not tree.exists(room_id):
                    continue

                state_label = {
                    "Vacant": "Libre",
                    "Reserved": "Réservé",
                    "ReservedLocked": "Réservé (verrouillé)",
                    "InternalUse": "Usage interne",
                    "OutOfOrder": "Hors service",
                    "Unknown": "Inconnu",
                }
                label = state_label.get(status.occupancy_state, "Inconnu")

                tree.item(
                    room_id,
                    values=(status.unit_id, status.room_name, label),
                )

            if self.running:
                root.after(1000, refresh_ui)

        def on_close():
            confirmed = messagebox.askokcancel(
                "Confirmer la fermeture",
                "Fermer le programme va arreter le serveur Modbus et les appels API. Continuer ?",
                parent=root,
            )
            if not confirmed:
                return

            self.running = False
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)
        refresh_ui()
        root.mainloop()

    def loop(self):
        while self.running:
            time.sleep(POLLING_INTERVAL)
            self.update_registers()

    def start(self):
        self.running = True
        threading.Thread(target=self.run_modbus_server, daemon=True).start()

        if not self.server_ready.wait(timeout=5):
            raise RuntimeError("Le serveur Modbus ne s'est pas initialisé a temps.")

        self.update_registers()
        threading.Thread(target=self.loop, daemon=True).start()

        if SHOW_UI:
            self.run_ui()
            return

        while self.running:
            time.sleep(1)
