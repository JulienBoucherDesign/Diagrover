"""
DiagRover — diagrover/core/session_logger.py
Journal commenté de chaque session de diagnostic

Génère un fichier texte horodaté par session :
  logs/session_20240115_143205_SALLTGM844A.log

Format lisible par un mécanicien, chaque événement commenté.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Répertoire des logs ───────────────────────────────────────
LOGS_DIR = Path(__file__).parent.parent.parent / "logs"


class SessionLogger:
    """
    Écrit un fichier .log horodaté pour chaque session DiagRover.

    Utilisation :
        logger = SessionLogger()
        logger.start_session(port="/dev/ttyACM0")
        logger.log_connection(ok=True)
        logger.log_kwp_init()
        logger.log_auth(seed=0x173F, key=0xC173)
        logger.log_live({"RPM": 820, "BATT_V1": 14.022})
        logger.log_faults(faults)
        logger.end_session()
    """

    # ── Symboles visuels ──────────────────────────────────────
    TX   = "→"
    RX   = "←"
    INFO = "·"
    WARN = "⚠"
    ERR  = "✗"
    OK   = "✓"
    SEP  = "─" * 72

    def __init__(self, logs_dir: Path = LOGS_DIR):
        self._dir      = logs_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file     = None
        self._lock     = threading.Lock()
        self._start_ts: Optional[datetime] = None
        self._vin      = "UNKNOWN"
        self._path:    Optional[Path] = None
        self._live_count = 0
        self._last_live_log = 0.0  # timestamp dernier log live data

    # ── Cycle de vie ─────────────────────────────────────────

    def start_session(self, port: str = "?", demo: bool = False):
        """Ouvre le fichier de log et écrit l'en-tête."""
        self._start_ts = datetime.now()
        fname = f"session_{self._start_ts.strftime('%Y%m%d_%H%M%S')}.log"
        self._path = self._dir / fname
        self._file = open(self._path, "w", encoding="utf-8", buffering=1)  # line-buffered

        mode = "[DEMO]" if demo else f"port={port}"
        self._header(mode)

    def end_session(self):
        """Écrit le pied de page et ferme le fichier."""
        if not self._file:
            return
        dur = ""
        if self._start_ts:
            delta = datetime.now() - self._start_ts
            s = int(delta.total_seconds())
            dur = f"{s//60}m{s%60:02d}s"
        self._write(f"\n{self.SEP}")
        self._write(f"SESSION TERMINÉE — durée: {dur}")
        if self._path:
            self._write(f"Fichier: {self._path.name}")
        self._write(self.SEP)
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None

    def rename_with_vin(self, vin: str):
        """Renomme le fichier log avec le VIN une fois connu."""
        if not self._path or not self._path.exists():
            return
        self._vin = vin[:17] if vin else "UNKNOWN"
        stem = self._path.stem
        new_path = self._path.parent / f"{stem}_{self._vin}.log"
        try:
            os.rename(self._path, new_path)
            self._path = new_path
        except OSError:
            pass

    # ── Événements de connexion ───────────────────────────────

    def log_connection(self, ok: bool, port: str = "", msg: str = ""):
        if ok:
            self._write(f"{self.OK} Nano 33 BLE connecté sur {port}")
        else:
            self._write(f"{self.ERR} Connexion échouée: {msg}", section=False)

    def log_stn_ready(self, version: str = ""):
        self._write(f"{self.OK} STN1110 initialisé{' — ' + version if version else ''}")
        self._write(f"{self.INFO} Double init baud rate: 9600 → 115200 ✓")
        self._write(f"{self.INFO} Configuration AT: ATE0 ATH1 ATS0 ATCAF1 ATAL ✓")

    def log_disconnection(self):
        self._write(f"\n{self.WARN} Nano déconnecté !", section=False)

    # ── Protocole KWP2000 ─────────────────────────────────────

    def log_kwp_init(self, proto: str = "ATSP4"):
        self._section("INITIALISATION SESSION KWP2000")
        self._write(f"{self.TX} StartComm (FMT=0x81 TGT=0x13 SRC=0xF7)")
        self._write(f"{self.INFO} Protocole: {proto} (KWP2000 fast init)")

    def log_kwp_start_comm(self, kw1: int, kw2: int):
        self._write(f"{self.RX} StartComm_RESP — KW1=0x{kw1:02X} KW2=0x{kw2:02X} ✓")
        self._write(f"{self.TX} StartDiagSession(0xA0) — mode fabricant LR")

    def log_kwp_session_open(self):
        self._write(f"{self.RX} Session fabricant LR ouverte ✓")

    def log_auth(self, seed: int, key: int):
        self._section("AUTHENTIFICATION SEED-KEY TD5")
        self._write(f"{self.TX} SecurityAccess — RequestSeed (SID 0x27 sub=0x01)")
        self._write(f"{self.RX} Seed reçu: 0x{seed:04X}")
        self._write(f"{self.INFO} Calcul: td5_keygen(0x{seed:04X}) = 0x{key:04X}")
        self._write(f"    Algorithme LFSR 16 bits — count={(lambda s: ((s>>0xC&0x8)+(s>>0x5&0x4)+(s>>0x3&0x2)+(s&0x1))+1)(seed)}")
        self._write(f"{self.TX} SendKey: 0x{key:04X} (high=0x{key>>8:02X} low=0x{key&0xFF:02X})")

    def log_auth_ok(self):
        self._write(f"{self.RX} AUTH OK — session fabricant active ✓")
        self._write(f"{self.INFO} Tous les Local IDs TD5 maintenant accessibles")
        self._write(f"{self.INFO} Keep-alive actif: TesterPresent (0x3E) toutes les 2.5s")

    def log_auth_fail(self, nrc: int = 0):
        self._write(f"{self.ERR} AUTH ÉCHOUÉE — NRC=0x{nrc:02X}")

    def log_atsp_fallback(self, from_proto: str, to_proto: str):
        self._write(f"{self.WARN} {from_proto} → UNABLE TO CONNECT → fallback {to_proto}")

    def log_keepalive(self):
        """Silencieux — on ne logge pas chaque keep-alive pour ne pas polluer."""
        pass

    # ── Identification véhicule ───────────────────────────────

    def log_vehicle_id(self, vin: str, ecu_type: str,
                        map_variant: str = "", fuel_variant: str = ""):
        self._section("IDENTIFICATION VÉHICULE")
        self._write(f"{self.RX} VIN: {vin}")
        self._write(f"{self.RX} Type ECU: {ecu_type}")
        if ecu_type == "NNN":
            self._write(f"{self.INFO} ECU NNN — codes injecteurs modulo 16 (0-15)")
        elif ecu_type == "MSB":
            self._write(f"{self.INFO} ECU MSB — codes injecteurs modulo 4 (0-3)")
        if map_variant:
            self._write(f"{self.RX} Variante cartographie: {map_variant}")
        if fuel_variant:
            self._write(f"{self.RX} Variante carburant: {fuel_variant}")
        self.rename_with_vin(vin)

    # ── Live data ─────────────────────────────────────────────

    def log_live_start(self, rate_ms: int = 200):
        self._section("DONNÉES EN TEMPS RÉEL (live data)")
        self._write(f"{self.INFO} Cycle démarré — {rate_ms}ms par PID")
        self._write(f"{self.INFO} PIDs: 0x40 0x23 0x37 0x38 0x10 0x09 0x0D 0x1A 0x1B 0x1C 0x21")
        self._live_count = 0

    def log_live_stop(self):
        self._write(f"{self.INFO} Live data arrêté — {self._live_count} cycles enregistrés")

    def log_live_snapshot(self, data: dict):
        """
        Logge un snapshot des données live.
        Pas plus d'1 log toutes les 10 secondes pour ne pas noyer le fichier.
        """
        import time
        now = time.time()
        self._live_count += 1
        if now - self._last_live_log < 10.0:
            return
        self._last_live_log = now

        lines = [f"{self.RX} Snapshot #{self._live_count}:"]
        mapping = {
            "RPM":          ("Régime moteur",       "rpm"),
            "SPEED":        ("Vitesse",              "km/h"),
            "BATT_V1":      ("Batterie",             "V"),
            "TEMP_COOLANT": ("Temp. refroidissement","°C"),
            "TEMP_FUEL":    ("Temp. carburant",      "°C"),
            "TEMP_AIR":     ("Temp. admission",      "°C"),
            "MAP_MBAR":     ("Pression MAP",         "mbar"),
            "EGR_MOD":      ("Modulation EGR",       ""),
        }
        for pid, (label, unit) in mapping.items():
            val = data.get(pid)
            if val is not None:
                lines.append(f"    {label:<28} {val} {unit}")

        # Power Balance
        pb = [data.get(f"PWR_BAL_{i}") for i in range(1, 6)]
        if any(v is not None for v in pb):
            pb_str = "  ".join(
                f"Cyl{i+1}:{pb[i]:+.0f}" if pb[i] is not None else f"Cyl{i+1}:—"
                for i in range(5)
            )
            lines.append(f"    Power Balance: {pb_str}")

        for line in lines:
            self._write(line, section=False)

    # ── Codes défauts ─────────────────────────────────────────

    def log_fault_read(self, faults: list[dict]):
        self._section("CODES DÉFAUTS — LECTURE")
        crit = [f for f in faults if f["severity"] == 3]
        warn = [f for f in faults if f["severity"] == 2]
        info = [f for f in faults if f["severity"] == 1]
        unkn = [f for f in faults if not f.get("known", True)]

        self._write(f"{self.RX} {len(faults)} code(s) actif(s) — "
                    f"{len(crit)} critical / {len(warn)} warning / {len(info)} info")

        if crit:
            self._write(f"\n  [CRITICAL] {len(crit)} code(s) :")
            for f in crit:
                self._write(f"    {f['code']:<12} — {f['desc_fr']}")

        if warn:
            self._write(f"\n  [WARNING]  {len(warn)} code(s) :")
            for f in warn:
                self._write(f"    {f['code']:<12} — {f['desc_fr']}")

        if info:
            self._write(f"\n  [INFO]     {len(info)} code(s) :")
            for f in info:
                self._write(f"    {f['code']:<12} — {f['desc_fr']}")

        if unkn:
            self._write(f"\n  [INCONNUS] {len(unkn)} bit(s) non documenté(s) :")
            for f in unkn:
                self._write(f"    Bit #{f['bit_pos']:03d}  — {f['desc_fr']}")

    def log_fault_clear(self, count_before: int):
        self._section("CODES DÉFAUTS — EFFACEMENT")
        self._write(f"{self.TX} StartRoutine 0xDD — effacement de {count_before} code(s)")
        self._write(f"    Frame: 14 31 DD 00×18 22")

    def log_fault_clear_ok(self):
        self._write(f"{self.RX} Effacement confirmé ✓")

    # ── Actuations ────────────────────────────────────────────

    def log_actuation(self, name: str, lid: int, val: int, action: str = "ON"):
        self._write(
            f"{self.TX} Actuation {name} (LID=0x{lid:02X} val=0x{val:02X}) — {action}",
            section=False
        )

    def log_injector_test(self, n: int):
        self._write(
            f"{self.TX} Test injecteur {n} — StartRoutine 0xC2 param={n}",
            section=False
        )

    def log_injector_result(self, n: int, delta_rpm: Optional[int]):
        if delta_rpm is not None:
            quality = "BON" if abs(delta_rpm) > 30 else "FAIBLE — injecteur suspect"
            self._write(
                f"{self.RX} Injecteur {n} — chute RPM: {delta_rpm:+d} rpm → {quality}",
                section=False
            )
        else:
            self._write(f"{self.RX} Injecteur {n} — pas de données Power Balance", section=False)

    # ── Réglages ──────────────────────────────────────────────

    def log_settings_read(self, settings_hex: str,
                           map_variant: str = "", accel_type: str = ""):
        self._section("RÉGLAGES ECU")
        self._write(f"{self.RX} Settings block (0x3D): {settings_hex}")
        if map_variant:
            self._write(f"{self.RX} Variante map: {map_variant}")
        if accel_type:
            self._write(f"{self.RX} Type accélérateur: {accel_type}")

    def log_settings_write(self, what: str, value: str):
        self._write(f"{self.TX} Écriture setting: {what} = {value}", section=False)

    # ── Erreurs et NRC ────────────────────────────────────────

    def log_nrc(self, rejected_sid: int, nrc_code: int):
        nrc_names = {
            0x10: "GeneralReject",
            0x11: "ServiceNotSupported",
            0x22: "ConditionsNotCorrect",
            0x35: "InvalidKey",
            0x36: "ExceededAttempts",
        }
        name = nrc_names.get(nrc_code, f"0x{nrc_code:02X}")
        self._write(
            f"{self.WARN} NegativeResponse — SID=0x{rejected_sid:02X} NRC={name}",
            section=False
        )

    def log_error(self, msg: str):
        self._write(f"{self.ERR} ERREUR: {msg}", section=False)

    def log_comment(self, comment: str):
        """Commentaire libre dans le log."""
        self._write(f"{self.INFO} {comment}", section=False)

    # ── Helpers internes ──────────────────────────────────────

    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:12]

    def _write(self, line: str, section: bool = False):
        with self._lock:
            if not self._file:
                return
            prefix = f"[{self._ts()}] "
            for l in line.split("\n"):
                self._file.write(f"{prefix}{l}\n")

    def _section(self, title: str):
        self._write(f"\n{self.SEP}")
        self._write(f"  {title}")
        self._write(self.SEP)

    def _header(self, mode: str):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sep = "=" * 72
        self._file.write(f"{sep}\n")
        self._file.write(f"  DiagRover — Journal de session\n")
        self._file.write(f"  Date    : {now_str}\n")
        self._file.write(f"  Mode    : {mode}\n")
        self._file.write(f"  Fichier : {self._path.name if self._path else '?'}\n")
        self._file.write(f"{sep}\n\n")

    @property
    def path(self) -> Optional[Path]:
        return self._path
