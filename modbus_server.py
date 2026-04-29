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
    MOCK_ROOM_COUNT,
    MOCK_MODE,
    MODBUS_HOST,
    MODBUS_PORT,
    POLLING_INTERVAL,
    SHOW_UI,
    CLIENT_TOKEN,
    log,
)
from domain import RoomStatus
from occupancy import analyse_occupation, generate_mock_rooms, generate_mock_occupation
from services import MewsApiClient, RoomMappingRepository


class MewsRoomsModbus:
    def __init__(self):
        self.running = False
        self.status_lock = threading.Lock()
        self.api_client = MewsApiClient(BASE_URL, CLIENT_TOKEN, ACCESS_TOKEN, HEADERS)
        self.mapping_repo = RoomMappingRepository(MAPPING_FILE)
        self.latest_status = {}
        self.room_names = {}
        self.sim_devices = []
        self.server = None
        self.server_ready = threading.Event()
        self.mock_mode = MOCK_MODE
        rooms = self._load_initial_rooms()

        if not rooms:
            raise RuntimeError(
                "Aucune chambre recuperee depuis MEWS. Verifiez les tokens et l'environnement API."
            )

        self.room_to_unit, self.rooms_actives = self.mapping_repo.update(rooms)
        self._cache_room_names(rooms)
        self._initialize_status_cache()

        log.info(f"Chambres trouvees dans l'API : {len(rooms)}")
        log.info(f"Unit IDs totaux (historique) : {len(self.room_to_unit)}")

        self.sim_devices = self._build_modbus_devices()

    def _load_initial_rooms(self):
        if self.mock_mode:
            rooms = generate_mock_rooms(MOCK_ROOM_COUNT)
            log.warning("Mode MOCK actif: aucune connexion API MEWS, donnees simulees.")
            return rooms
        return self.api_client.fetch_rooms()

    def _cache_room_names(self, rooms):
        for room in rooms:
            self.room_names[room["Id"]] = room.get("Name", "N/A")

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
            devices.append(
                SimDevice(
                    unit_id,
                    simdata=[
                        SimData(0, values=0, datatype=DataType.REGISTERS),
                    ],
                )
            )

            status = "ACTIVE" if room_id in self.rooms_actives else "INACTIVE"
            room_name = self.room_names.get(room_id, "Inconnue")
            log.info(f"  Unit ID {unit_id:3d} -> {room_name:20s} [{status}]")

        return devices

    def _get_runtime_device(self, unit_id):
        if self.server is None:
            return None

        context = getattr(self.server, "context", None)
        if context is None or not hasattr(context, "devices"):
            return None

        return context.devices.get(unit_id)

    def _fetch_rooms_and_occupation(self):
        if self.mock_mode:
            rooms = generate_mock_rooms(MOCK_ROOM_COUNT)
            occupation = generate_mock_occupation(rooms)
            api_error = 0
            log.info(f"Mise a jour MOCK: {len(rooms)} chambres simulees")
            return rooms, occupation, api_error

        try:
            rooms = self.api_client.fetch_rooms()
            reservations = self.api_client.fetch_reservations()
            occupation = analyse_occupation(rooms, reservations)
            api_error = 0
        except Exception as exc:
            log.error(f"Erreur API: {exc}")
            rooms = []
            occupation = {}
            api_error = 1

        return rooms, occupation, api_error

    def update_registers(self):
        rooms, occupation, api_error = self._fetch_rooms_and_occupation()

        total_occupied = 0
        active_room_ids = {room.get("Id") for room in rooms}

        for room_id, unit_id in self.room_to_unit.items():
            occupied = 0
            if room_id in occupation:
                occupied = 1 if occupation[room_id].get("occupied", False) else 0

            if occupied:
                total_occupied += 1

            with self.status_lock:
                self.latest_status[room_id] = RoomStatus(
                    room_id=room_id,
                    unit_id=unit_id,
                    room_name=self.room_names.get(room_id, "Inconnue"),
                    active=room_id in active_room_ids,
                    occupied=occupied,
                )

            log.info(f"Unit {unit_id} -> value {occupied}")
            runtime_device = self._get_runtime_device(unit_id)
            if runtime_device is not None:
                block = runtime_device.block.get("x") or runtime_device.block.get("h") or runtime_device.block.get("i")
                if block is not None:
                    block[2][0] = occupied

        log.info(f"Update OK | Occupied: {total_occupied} | API Error: {api_error}")

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
            text=f"Modbus TCP: {MODBUS_HOST}:{MODBUS_PORT} | Registre 0 = occupation",
        )
        info.pack(anchor="w", padx=12, pady=(0, 8))

        columns = ("unit", "room", "active", "status")
        tree = ttk.Treeview(root, columns=columns, show="headings", height=18)
        tree.heading("unit", text="Unit ID")
        tree.heading("room", text="Chambre")
        tree.heading("active", text="Active")
        tree.heading("status", text="Statut")
        tree.column("unit", width=90, anchor="center")
        tree.column("room", width=360, anchor="w")
        tree.column("active", width=90, anchor="center")
        tree.column("status", width=160, anchor="center")

        scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        scrollbar.pack(side="right", fill="y", padx=(0, 12), pady=(0, 12))

        for room_id, unit_id in sorted(self.room_to_unit.items(), key=lambda item: item[1]):
            room_name = self.room_names.get(room_id, "Inconnue")
            tree.insert("", "end", iid=room_id, values=(unit_id, room_name, "Oui", "Disponible"))

        def refresh_ui():
            with self.status_lock:
                snapshot = dict(self.latest_status)

            for room_id, status in snapshot.items():
                if not tree.exists(room_id):
                    continue

                active = "Oui" if status.active else "Non"
                if not status.active:
                    label = "Inactive"
                else:
                    label = "Occupee" if status.occupied else "Disponible"

                tree.item(
                    room_id,
                    values=(status.unit_id, status.room_name, active, label),
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
