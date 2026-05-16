"""
DiagRover — diagrover/core/serial_manager.py
Thread de lecture port série USB CDC (Nano 33 BLE)
"""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Callable, Optional

import serial
import serial.tools.list_ports


class SerialManager:
    """
    Thread de lecture port série non-bloquant.

    - Lit les JSON lines envoyées par le Nano en arrière-plan
    - Dispatch les messages vers les callbacks enregistrés
    - Gère la reconnexion automatique en cas de déconnexion USB

    Usage :
        mgr = SerialManager()
        mgr.on_message("live",   lambda msg: print(msg))
        mgr.on_message("status", lambda msg: print(msg))
        mgr.connect("/dev/ttyACM0")
        mgr.send({"cmd": "init"})
    """

    BAUD = 115200
    RECONNECT_DELAY = 2.0  # secondes entre tentatives

    def __init__(self):
        self._port:     Optional[serial.Serial] = None
        self._thread:   Optional[threading.Thread] = None
        self._running   = False
        self._connected = False
        self._tx_queue: queue.Queue = queue.Queue()
        self._callbacks: dict[str, list[Callable]] = {}

        # Callbacks de connexion/déconnexion
        self._on_connected:    Optional[Callable] = None
        self._on_disconnected: Optional[Callable] = None

    # ── API publique ──────────────────────────────────────────

    def connect(self, port: str) -> bool:
        """Ouvre le port et démarre le thread de lecture."""
        try:
            self._port = serial.Serial(
                port=port,
                baudrate=self.BAUD,
                timeout=0.1,
            )
            self._running   = True
            self._connected = True
            self._thread    = threading.Thread(
                target=self._read_loop,
                daemon=True,
                name="SerialManager"
            )
            self._thread.start()
            if self._on_connected:
                self._on_connected(port)
            return True
        except serial.SerialException as e:
            self._connected = False
            return False

    def disconnect(self):
        """Ferme la connexion proprement."""
        self._running = False
        if self._port and self._port.is_open:
            try:
                self._port.close()
            except Exception:
                pass
        self._connected = False

    def send(self, msg: dict) -> bool:
        """
        Envoie une commande JSON au Nano.
        Non-bloquant — met dans la queue TX.
        """
        if not self._connected:
            return False
        self._tx_queue.put(json.dumps(msg) + "\n")
        return True

    def is_connected(self) -> bool:
        return self._connected

    # ── Enregistrement callbacks ──────────────────────────────

    def on_message(self, msg_type: str, callback: Callable):
        """
        Enregistre un callback pour un type de message.

        Types : "live", "status", "error", "ack", "switches", "vom"
        Le callback reçoit le dict JSON parsé.

        IMPORTANT : Le callback est appelé depuis le thread série,
        jamais depuis le thread Qt. Ne jamais modifier l'UI directement.
        """
        if msg_type not in self._callbacks:
            self._callbacks[msg_type] = []
        self._callbacks[msg_type].append(callback)

    def on_connected(self, cb: Callable):
        self._on_connected = cb

    def on_disconnected(self, cb: Callable):
        self._on_disconnected = cb

    # ── Thread de lecture ─────────────────────────────────────

    def _read_loop(self):
        """
        Boucle de lecture série — tourne dans un thread dédié.

        ⚠️ Ne jamais toucher l'UI depuis ce thread.
           Utiliser des signaux Qt ou une queue.
        """
        while self._running:
            # ── Envoi des commandes TX ────────────────────────
            while not self._tx_queue.empty():
                try:
                    line = self._tx_queue.get_nowait()
                    self._port.write(line.encode("utf-8"))
                except (queue.Empty, serial.SerialException):
                    break

            # ── Lecture ──────────────────────────────────────
            try:
                raw = self._port.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                self._dispatch(line)

            except serial.SerialException:
                # Nano débranché
                self._connected = False
                if self._on_disconnected:
                    self._on_disconnected()
                break

            except Exception:
                continue

    def _dispatch(self, line: str):
        """Parse une ligne JSON et appelle le callback correspondant."""
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # Ligne partielle ou corrompue — ignorer silencieusement
            return

        msg_type = msg.get("type", "unknown")
        callbacks = self._callbacks.get(msg_type, [])
        for cb in callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    # ── Détection port ────────────────────────────────────────

    @staticmethod
    def find_nano_port() -> Optional[str]:
        """
        Détecte automatiquement le port du Nano 33 BLE.
        Cherche par VID:PID (Arduino nRF52840 = 0x2341:0x805A)
        ou par nom générique.
        """
        NANO_VID = 0x2341
        NANO_PID = 0x805A

        for port in serial.tools.list_ports.comports():
            if port.vid == NANO_VID and port.pid == NANO_PID:
                return port.device
            if port.vid == NANO_VID:
                return port.device
            # Fallback : nom de port générique Linux/macOS/Windows
            name = port.device.lower()
            if any(p in name for p in ("acm", "usbmodem", "cu.usb")):
                return port.device

        return None

    @staticmethod
    def list_ports() -> list[dict]:
        """Liste tous les ports série disponibles."""
        return [
            {
                "device": p.device,
                "description": p.description,
                "vid": p.vid,
                "pid": p.pid,
            }
            for p in serial.tools.list_ports.comports()
        ]
