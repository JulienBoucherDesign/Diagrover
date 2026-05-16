"""
DiagRover — diagrover/core/session.py
Gestionnaire de session KWP2000 côté PC
Coordonne l'auth, le live data, et les commandes
"""

from __future__ import annotations

import threading
import time
from enum import Enum, auto
from typing import Callable, Optional

from kwp2000 import (
    LIVE_CYCLE_PAGE2,
    decode_battery, decode_rpm, decode_speed,
    decode_temp, decode_temps_all, decode_pressure_mbar,
    decode_throttle_v, decode_power_balance, decode_switches,
    decode_ecuid_type, decode_vin,
    LOCAL_IDS,
)
from serial_manager import SerialManager


class SessionState(Enum):
    DISCONNECTED  = auto()
    CONNECTED     = auto()   # port série ouvert, Nano prêt
    INITIALIZING  = auto()   # séquence KWP2000 en cours
    AUTHENTICATED = auto()   # session fabricant LR ouverte
    ERROR         = auto()


class DiagRoverSession:
    """
    Gère la session DiagRover côté PC.

    - Connecte au Nano via SerialManager
    - Déclenche et surveille l'authentification KWP2000
    - Dispatche les données live vers les callbacks UI
    - Expose les commandes utilisateur (actuate, test injecteur, etc.)
    """

    def __init__(self):
        self._serial    = SerialManager()
        self._state     = SessionState.DISCONNECTED
        self._ecu_type  = None   # "NNN" ou "MSB"
        self._vin       = None

        # Callbacks UI (appelés depuis le thread série → utiliser signaux Qt)
        self._on_state_change: Optional[Callable] = None
        self._on_live_data:    Optional[Callable] = None
        self._on_error:        Optional[Callable] = None

        # Enregistrer les callbacks du SerialManager
        self._serial.on_message("status",  self._handle_status)
        self._serial.on_message("live",    self._handle_live)
        self._serial.on_message("error",   self._handle_error)
        self._serial.on_message("ack",     self._handle_ack)
        self._serial.on_message("switches",self._handle_switches)
        self._serial.on_disconnected(self._handle_disconnect)

    # ── Connexion ─────────────────────────────────────────────

    def connect(self, port: Optional[str] = None) -> bool:
        """
        Connecte au Nano. Si port=None, auto-détection.
        """
        if port is None:
            port = SerialManager.find_nano_port()
        if not port:
            return False

        ok = self._serial.connect(port)
        if ok:
            self._set_state(SessionState.CONNECTED)
        return ok

    def open_session(self):
        """
        Lance la séquence d'authentification KWP2000.
        Résultat via callback on_state_change.
        """
        self._set_state(SessionState.INITIALIZING)
        self._serial.send({"cmd": "init"})

    def disconnect(self):
        """Ferme la connexion proprement."""
        self._serial.send({"cmd": "live_stop"})
        time.sleep(0.1)
        self._serial.disconnect()
        self._set_state(SessionState.DISCONNECTED)

    # ── Live data ─────────────────────────────────────────────

    def start_live_data(self, rate_ms: int = 200):
        """Démarre l'acquisition live data sur le Nano."""
        self._serial.send({"cmd": "live_start", "rate_ms": rate_ms})

    def stop_live_data(self):
        self._serial.send({"cmd": "live_stop"})

    def read_pid(self, lid: int):
        """Lit un Local ID unique."""
        self._serial.send({"cmd": "read_pid", "lid": lid})

    # ── Commandes véhicule ────────────────────────────────────

    def actuate(self, lid: int, val: int = 0xFF):
        """
        IOControl — activer/désactiver une sortie.

        Exemple : actuate(0xA1)       → pompe carburant ON
                  actuate(0xA1, 0x00) → pompe carburant OFF
        """
        self._serial.send({"cmd": "actuate", "lid": lid, "val": val})

    def test_injector(self, n: int):
        """Test injecteur N (1–5)."""
        assert 1 <= n <= 5
        self._serial.send({"cmd": "routine", "lid": 0xC2, "param": n})

    def clear_faults(self):
        """Effacement codes défauts (routine 0xDD)."""
        self._serial.send({"cmd": "routine", "lid": 0xDD, "param": 0})

    def set_mode(self, mode: str):
        """Change le mode ATST : 'livedata', 'diag', 'flash'."""
        self._serial.send({"cmd": "set_mode", "mode": mode})

    # ── Callbacks enregistrement ──────────────────────────────

    def on_state_change(self, cb: Callable):
        self._on_state_change = cb

    def on_live_data(self, cb: Callable):
        """
        Callback appelé pour chaque donnée live reçue.
        cb(pid: str, value: float|int, unit: str)

        ⚠️ Appelé depuis le thread série — ne pas modifier l'UI directement.
        """
        self._on_live_data = cb

    def on_error(self, cb: Callable):
        self._on_error = cb

    # ── État ──────────────────────────────────────────────────

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def ecu_type(self) -> Optional[str]:
        return self._ecu_type

    @property
    def vin(self) -> Optional[str]:
        return self._vin

    @property
    def is_authenticated(self) -> bool:
        return self._state == SessionState.AUTHENTICATED

    # ── Handlers internes ─────────────────────────────────────

    def _handle_status(self, msg: dict):
        level = msg.get("level", "")
        text  = msg.get("msg", "")

        if level == "ok" and text == "session_open":
            self._set_state(SessionState.AUTHENTICATED)
        elif level == "error":
            self._set_state(SessionState.ERROR)
            if self._on_error:
                self._on_error(text)

    def _handle_live(self, msg: dict):
        if not self._on_live_data:
            return
        pid   = msg.get("pid", "")
        value = msg.get("val", 0)
        unit  = msg.get("unit", "")
        self._on_live_data(pid, value, unit)

    def _handle_switches(self, msg: dict):
        if self._on_live_data:
            # Envoyer chaque switch individuellement
            for key, val in msg.items():
                if key not in ("type", "ts"):
                    self._on_live_data(f"SW_{key.upper()}", int(val), "bool")

    def _handle_error(self, msg: dict):
        code   = msg.get("code", "ERROR")
        detail = msg.get("detail", "")
        if self._on_error:
            self._on_error(f"{code}: {detail}")

    def _handle_ack(self, msg: dict):
        cmd = msg.get("cmd", "")
        # Mettre à jour l'état selon la commande acquittée
        if cmd == "live_start":
            pass  # UI gère ça
        elif cmd == "live_stop":
            pass

    def _handle_disconnect(self):
        self._set_state(SessionState.DISCONNECTED)

    def _set_state(self, new_state: SessionState):
        if self._state != new_state:
            self._state = new_state
            if self._on_state_change:
                self._on_state_change(new_state)
