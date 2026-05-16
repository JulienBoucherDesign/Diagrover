"""
DiagRover — diagrover/core/protocol_trace.py
Trace protocole KWP2000 — journal commenté de chaque échange avec le véhicule

Génère un fichier .trace horodaté par session :
  logs/trace_20240115_143205_SALLTGM844A.trace

Chaque trame envoyée et reçue est :
  - loggée en hexadécimal brut (comme les sniffings Ekaitza_Itzali)
  - annotée avec son sens, son SID, son Local ID, sa signification
  - décodée en valeurs physiques quand applicable
  - validée en checksum

Format :
  [14:32:05.123] → 02 21 09 2C    ReadDataLocalID(RPM)    CS=0x2C ✓
  [14:32:05.215] ← 04 61 09 00 00 6E  RPM=0 rpm           CS=0x6E ✓
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Noms des SIDs KWP2000 ─────────────────────────────────────
SID_NAMES = {
    0x10: "StartDiagSession",
    0x1A: "ReadECUID",
    0x21: "ReadDataLocalID",
    0x27: "SecurityAccess",
    0x2E: "WriteDataByLocalID",
    0x30: "IOControlByLocalID",
    0x31: "StartRoutineByLocalID",
    0x3E: "TesterPresent",
    0x50: "StartDiagSession_RESP",
    0x5A: "ReadECUID_RESP",
    0x61: "ReadDataLocalID_RESP",
    0x67: "SecurityAccess_RESP",
    0x70: "IOControl_RESP",
    0x71: "StartRoutine_RESP",
    0x7E: "TesterPresent_RESP",
    0x7F: "NegativeResponse",
    0x81: "StartComm",
    0xC1: "StartComm_RESP",
}

# ── Noms des Local IDs TD5 ────────────────────────────────────
LOCAL_ID_NAMES = {
    0x09: "RPM",
    0x0D: "VehicleSpeed",
    0x0E: "MapVariantID",
    0x10: "BatteryVoltage",
    0x1A: "Temperatures_8x",
    0x1B: "ThrottleTracks_4x",
    0x1C: "Pressures_4x",
    0x1E: "InputSwitches",
    0x20: "Unknown_0x20",
    0x21: "RPM_Error",
    0x23: "AmbientPressure",
    0x24: "AcceleratorType",
    0x32: "MapFuelVariant",
    0x36: "AutoGearbox",
    0x37: "EGR_Modulation",
    0x38: "EGR_Inlet",
    0x3B: "FaultsBitfield_35bytes",
    0x3D: "TuneSettings",
    0x40: "PowerBalance_5cyl",
    0x87: "VIN_SystemInfo",
    0x9A: "ECU_Type",
    0x9B: "ECU_SubVersion",
    0x9C: "ECU_Revision",
    0xA1: "OUT_FuelPump",
    0xA2: "OUT_MIL",
    0xA3: "OUT_ACClutch",
    0xA4: "OUT_ACFan",
    0xB3: "OUT_GlowPlugs",
    0xB7: "OUT_RevCounter",
    0xBA: "OUT_TempGauge",
    0xBD: "OUT_EGRInletMod",
    0xBE: "OUT_Wastegate",
    0xC1: "WRITE_AccelType",
    0xC2: "ROUTINE_InjectorTest",
    0xDD: "ROUTINE_ClearFaults",
    0xDF: "WRITE_Settings",
    0xD5: "WRITE_SettingsStr",
}

NRC_NAMES = {
    0x10: "GeneralReject",
    0x11: "ServiceNotSupported",
    0x12: "SubFunctionNotSupported",
    0x22: "ConditionsNotCorrect",
    0x35: "InvalidKey",
    0x36: "ExceededAttempts",
    0x37: "RequiredTimeDelayNotExpired",
}

SENSOR_NOT_FITTED = 0x1388


# ── Décodeurs inline ──────────────────────────────────────────

def _decode_response(sid: int, data: bytes) -> str:
    """Retourne une annotation lisible pour les réponses ECU."""
    if not data:
        return ""

    # ReadDataLocalID_RESP (0x61)
    if sid == 0x61 and len(data) >= 1:
        lid  = data[0]
        vals = data[1:]
        name = LOCAL_ID_NAMES.get(lid, f"LID=0x{lid:02X}")

        try:
            if lid == 0x09 and len(vals) >= 2:
                rpm = (vals[0] << 8) | vals[1]
                return f"{name} → {rpm} rpm"

            elif lid == 0x0D and len(vals) >= 1:
                return f"{name} → {vals[0]} km/h"

            elif lid == 0x10 and len(vals) >= 4:
                v1 = ((vals[0] << 8) | vals[1]) / 1000.0
                v2 = ((vals[2] << 8) | vals[3]) / 1000.0
                return f"{name} → V1={v1:.3f}V V2={v2:.3f}V"

            elif lid == 0x1A and len(vals) >= 2:
                temps = []
                for i in range(0, min(len(vals) - 1, 16), 2):
                    raw = (vals[i] << 8) | vals[i + 1]
                    if raw == SENSOR_NOT_FITTED:
                        temps.append("—")
                    else:
                        temps.append(f"{raw / 100.0:.1f}°C")
                return f"{name} → [{', '.join(temps)}]"

            elif lid == 0x1B and len(vals) >= 2:
                tracks = []
                for i in range(0, min(len(vals) - 1, 8), 2):
                    raw = (vals[i] << 8) | vals[i + 1]
                    tracks.append(f"{raw / 1000.0:.3f}V")
                return f"{name} → [{', '.join(tracks)}]"

            elif lid == 0x1C and len(vals) >= 4:
                p1 = ((vals[0] << 8) | vals[1]) * 0.1
                p2 = ((vals[2] << 8) | vals[3]) * 0.1
                return f"{name} → MAP={p1:.1f}mbar P2={p2:.1f}mbar"

            elif lid == 0x1E and len(vals) >= 2:
                b1, b2 = vals[0], vals[1]
                active = []
                if b1 & 0x01: active.append("TransferRatio")
                if b1 & 0x10: active.append("Brake2")
                if b1 & 0x40: active.append("Brake1")
                if b2 & 0x04: active.append("Clutch")
                if b2 & 0x10: active.append("CruiseSet")
                if b2 & 0x20: active.append("ACFan")
                sw_str = ", ".join(active) if active else "all OFF"
                return f"{name} → [{sw_str}]"

            elif lid == 0x21 and len(vals) >= 2:
                err = int.from_bytes(vals[:2], 'big', signed=True)
                return f"{name} → {err:+d} rpm"

            elif lid == 0x23 and len(vals) >= 2:
                p = ((vals[0] << 8) | vals[1]) * 0.1
                return f"{name} → {p:.1f} mbar"

            elif lid == 0x24 and len(vals) >= 1:
                t = {0x01: "2-Way", 0x02: "3-Way"}.get(vals[0], f"0x{vals[0]:02X}")
                return f"{name} → {t}"

            elif lid == 0x37 and len(vals) >= 2:
                v = (vals[0] << 8) | vals[1]
                return f"{name} → {v}"

            elif lid == 0x38 and len(vals) >= 2:
                v = (vals[0] << 8) | vals[1]
                return f"{name} → {v}"

            elif lid == 0x3B:
                n_bits = sum(bin(b).count('1') for b in vals)
                return f"{name} → {len(vals)} bytes, {n_bits} faults actifs"

            elif lid == 0x40 and len(vals) >= 10:
                pb = [int.from_bytes(vals[i:i+2], 'big', signed=True) for i in range(0, 10, 2)]
                pb_str = " ".join(f"C{i+1}:{pb[i]:+d}" for i in range(5))
                return f"{name} → [{pb_str}]"

            elif lid == 0x9A and len(vals) >= 3:
                ecu = ''.join(chr(b) if 32 <= b < 127 else '?' for b in vals[:3])
                return f"{name} → '{ecu}'"

            elif lid == 0x87 and len(vals) >= 11:
                vin_part = ''.join(chr(b) if 32 <= b < 127 else '' for b in vals[:17]).strip()
                return f"{name} → VIN={vin_part}"

        except Exception:
            pass
        return name

    # SecurityAccess_RESP (0x67)
    elif sid == 0x67 and len(data) >= 1:
        if data[0] == 0x01 and len(data) >= 3:
            seed = (data[1] << 8) | data[2]
            return f"Seed=0x{seed:04X} (seed_H=0x{data[1]:02X} seed_L=0x{data[2]:02X})"
        elif data[0] == 0x02:
            return "AUTH OK ✓"

    # StartDiagSession_RESP (0x50)
    elif sid == 0x50:
        return "Session ouverte ✓"

    # TesterPresent_RESP (0x7E)
    elif sid == 0x7E:
        return "keep-alive ACK"

    # NegativeResponse (0x7F)
    elif sid == 0x7F and len(data) >= 2:
        rej  = SID_NAMES.get(data[0], f"0x{data[0]:02X}")
        nrc  = NRC_NAMES.get(data[1], f"0x{data[1]:02X}")
        return f"REJECTED: {rej} — NRC={nrc}"

    # StartComm_RESP (0xC1)
    elif sid == 0xC1 and len(data) >= 2:
        return f"KW1=0x{data[0]:02X} KW2=0x{data[1]:02X} (KWP2000 confirmé)"

    # ReadECUID_RESP (0x5A)
    elif sid == 0x5A and len(data) >= 2:
        param = LOCAL_ID_NAMES.get(data[0], f"0x{data[0]:02X}")
        raw = data[1:]
        txt = ''.join(chr(b) if 32 <= b < 127 else '.' for b in raw[:20])
        return f"{param} → {txt.strip()}"

    # IOControl_RESP (0x70)
    elif sid == 0x70 and len(data) >= 1:
        lid = LOCAL_ID_NAMES.get(data[0], f"0x{data[0]:02X}")
        return f"{lid} ✓"

    # StartRoutine_RESP (0x71)
    elif sid == 0x71 and len(data) >= 1:
        lid = LOCAL_ID_NAMES.get(data[0], f"0x{data[0]:02X}")
        return f"{lid} ✓"

    return ""


def _decode_request(sid: int, data: bytes) -> str:
    """Retourne une annotation lisible pour les requêtes PC→ECU."""
    if not data:
        return ""

    if sid == 0x21:
        lid = data[0]
        return LOCAL_ID_NAMES.get(lid, f"LID=0x{lid:02X}")

    elif sid == 0x27:
        if data[0] == 0x01: return "RequestSeed"
        elif data[0] == 0x02 and len(data) >= 3:
            key = (data[1] << 8) | data[2]
            return f"SendKey=0x{key:04X} (H=0x{data[1]:02X} L=0x{data[2]:02X})"

    elif sid == 0x10:
        mode = {0xA0: "fabricant LR"}.get(data[0], f"0x{data[0]:02X}")
        return f"mode={mode}"

    elif sid == 0x30:
        lid  = LOCAL_ID_NAMES.get(data[0], f"0x{data[0]:02X}")
        val  = f" val=0x{data[1]:02X}" if len(data) > 1 else ""
        return f"{lid}{val}"

    elif sid == 0x31:
        lid = LOCAL_ID_NAMES.get(data[0], f"0x{data[0]:02X}")
        param = f" param={data[1]}" if len(data) > 1 else ""
        return f"{lid}{param}"

    elif sid == 0x3E:
        return "keep-alive"

    elif sid == 0x1A:
        return LOCAL_ID_NAMES.get(data[0], f"param=0x{data[0]:02X}")

    return ""


# ── Trace Logger ──────────────────────────────────────────────

class ProtocolTrace:
    """
    Journal bas niveau de chaque trame KWP2000 échangée avec le véhicule.

    Chaque trame est loggée avec :
    - Horodatage précis (ms)
    - Direction (→ PC→ECU  ← ECU→PC)
    - Octets bruts (hex, format sniffing)
    - SID décodé
    - Local ID / paramètre décodé
    - Valeurs physiques
    - Validation checksum
    - Commentaire si fourni
    """

    LOGS_DIR = Path(__file__).parent.parent.parent / "logs"

    def __init__(self, logs_dir: Optional[Path] = None):
        self._dir   = Path(logs_dir or self.LOGS_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file  = None
        self._lock  = threading.Lock()
        self._path: Optional[Path] = None
        self._vin   = "UNKNOWN"
        self._frame_count = 0
        self._keepalive_count = 0  # comptés mais pas loggés un par un

    # ── Cycle de vie ─────────────────────────────────────────

    def start(self, port: str = "?", demo: bool = False):
        ts = datetime.now()
        fname = f"trace_{ts.strftime('%Y%m%d_%H%M%S')}.trace"
        self._path = self._dir / fname
        self._file = open(self._path, "w", encoding="utf-8", buffering=1)
        mode = "[DEMO]" if demo else f"port={port}"
        self._write_header(mode, ts)

    def stop(self):
        if not self._file:
            return
        self._write_separator()
        ts = datetime.now().strftime("%H:%M:%S")
        self._raw_write(
            f"[{ts}] FIN TRACE — {self._frame_count} trames, "
            f"{self._keepalive_count} keep-alives silencieux\n"
        )
        self._raw_write("=" * 80 + "\n")
        with self._lock:
            self._file.close()
            self._file = None

    def rename_with_vin(self, vin: str):
        if not self._path or not self._path.exists():
            return
        self._vin = vin[:17]
        new = self._path.parent / f"{self._path.stem}_{self._vin}.trace"
        try:
            os.rename(self._path, new)
            self._path = new
        except OSError:
            pass

    # ── Logging des trames ────────────────────────────────────

    def log_tx(self, raw: bytes, comment: str = ""):
        """Trame PC → ECU."""
        if not self._file:
            return
        if len(raw) >= 2 and raw[1] == 0x3E:
            # Keep-alive : compter silencieusement
            self._keepalive_count += 1
            return
        self._log_frame("→", raw, comment)

    def log_rx(self, raw: bytes, comment: str = ""):
        """Trame ECU → PC."""
        if not self._file:
            return
        if len(raw) >= 2 and raw[1] == 0x7E:
            # Keep-alive response : silencieux
            self._keepalive_count += 1
            return
        self._log_frame("←", raw, comment)

    def log_raw_tx(self, hex_str: str, comment: str = ""):
        """Trame TX depuis une chaîne hex (usage firmware)."""
        try:
            self.log_tx(bytes.fromhex(hex_str.replace(" ", "")), comment)
        except ValueError:
            pass

    def log_raw_rx(self, hex_str: str, comment: str = ""):
        """Trame RX depuis une chaîne hex."""
        try:
            self.log_rx(bytes.fromhex(hex_str.replace(" ", "")), comment)
        except ValueError:
            pass

    def log_section(self, title: str):
        """Séparateur de section dans la trace."""
        self._write_separator()
        self._raw_write(f"  {title.upper()}\n")
        self._write_separator()

    def log_comment(self, comment: str):
        """Ligne de commentaire libre."""
        ts = self._ts()
        self._raw_write(f"[{ts}] # {comment}\n")

    def log_at_command(self, cmd: str, response: str = ""):
        """Commande AT STN1110 (non-KWP2000)."""
        ts = self._ts()
        resp_str = f"  →  {response}" if response else ""
        self._raw_write(f"[{ts}] [AT] {cmd}{resp_str}\n")

    def log_keepalive_summary(self):
        """Logge un résumé des keep-alives silencieux."""
        if self._keepalive_count > 0:
            ts = self._ts()
            self._raw_write(
                f"[{ts}] # keep-alives (0x3E/0x7E) depuis dernier log: "
                f"{self._keepalive_count}\n"
            )

    # ── Interne ───────────────────────────────────────────────

    def _log_frame(self, direction: str, raw: bytes, comment: str):
        with self._lock:
            if not self._file:
                return

            self._frame_count += 1
            ts = self._ts()

            # ── Décodage ────────────────────────────────────
            cs_ok   = len(raw) >= 2 and (sum(raw[:-1]) & 0xFF) == raw[-1]
            cs_icon = "✓" if cs_ok else "✗ CHECKSUM INVALID!"

            # StartComm header frame (8113f7810c) = format spécial, pas [LEN][SID]
            is_startcomm = (len(raw) == 5 and raw[0] == 0x81)
            sid     = (0x81 if is_startcomm else raw[1]) if len(raw) > 1 else 0
            data    = (raw[2:] if is_startcomm else
                       raw[2:raw[0]] if len(raw) >= raw[0] + 1 else raw[2:])
            sid_name = SID_NAMES.get(sid, f"SID=0x{sid:02X}")

            if direction == "→":
                decoded = _decode_request(sid, data)
            else:
                decoded = _decode_response(sid, data)

            # ── Formatage hex (2 chars par octet, espaces) ──
            hex_str = " ".join(f"{b:02X}" for b in raw)

            # ── Ligne principale ─────────────────────────────
            # Format : [HH:MM:SS.mmm] → XX XX XX XX  SID_NAME(decoded)  CS=0xXX ✓
            frame_part = f"{hex_str:<45}"
            sid_part   = f"{sid_name}"
            if decoded:
                sid_part += f"({decoded})"
            cs_part = f"  CS={cs_icon}"

            line = f"[{ts}] {direction} {frame_part}  {sid_part}{cs_part}"
            if comment:
                line += f"  # {comment}"

            self._raw_write(line + "\n")

            # ── Lignes de détail pour les réponses volumineuses ──
            if direction == "←" and sid == 0x61 and data and len(data) > 3:
                self._write_detail(data)

    def _write_detail(self, data: bytes):
        """Détail octet par octet pour les trames longues (températures, faults...)."""
        lid = data[0]
        vals = data[1:]

        if lid == 0x1A and len(vals) >= 16:
            # 8 températures détaillées
            labels = ["Coolant","Fuel","Air","T3","T4","T5","T6","T7"]
            n_temps = min(8, len(vals) // 2)
            self._raw_write(f"                    # {n_temps} températures:\n")
            for i in range(n_temps):
                raw = (vals[i*2] << 8) | vals[i*2 + 1]
                if raw == SENSOR_NOT_FITTED:
                    s = "— (capteur absent, tension 5V référence)"
                else:
                    s = f"{raw/100.0:.2f}°C  (0x{raw:04X})"
                self._raw_write(f"                    #   T{i} {labels[i]:<8}: {s}\n")

        elif lid == 0x1B and len(vals) >= 8:
            self._raw_write("                    # Papillon (4 pistes):\n")
            for i in range(4):
                raw = (vals[i*2] << 8) | vals[i*2 + 1]
                v = raw / 1000.0
                note = " (réf 5V)" if raw == SENSOR_NOT_FITTED else ""
                self._raw_write(f"                    #   Piste {i+1}: {v:.3f}V{note}\n")

        elif lid == 0x3B:
            n_bits = sum(bin(b).count('1') for b in vals)
            self._raw_write(f"                    # Faults: {len(vals)} bytes ({len(vals)*8} bits possibles), {n_bits} faults actifs\n")

        elif lid == 0x40 and len(vals) >= 10:
            self._raw_write("                    # Power Balance:\n")
            for i in range(5):
                pb = int.from_bytes(vals[i*2:i*2+2], 'big', signed=True)
                quality = "OK" if abs(pb) <= 20 else "SUSPECT" if abs(pb) <= 50 else "DÉFAUT"
                self._raw_write(f"                    #   Cyl{i+1}: {pb:+d}  [{quality}]\n")

    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:12]

    def _raw_write(self, s: str):
        if self._file:
            self._file.write(s)

    def _write_separator(self):
        ts = self._ts()
        self._raw_write(f"[{ts}] {'─' * 70}\n")

    def _write_header(self, mode: str, ts: datetime):
        sep = "=" * 80
        self._file.write(f"{sep}\n")
        self._file.write(f"  DiagRover — Trace protocole KWP2000\n")
        self._file.write(f"  Date         : {ts.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._file.write(f"  Mode         : {mode}\n")
        self._file.write(f"  Format       : [HH:MM:SS.mmm] → TRAME_HEX   SID(décodé)  CS ✓\n")
        self._file.write(f"  Protocole    : KWP2000 / ISO14230 via STN1110\n")
        self._file.write(f"  Note         : TesterPresent (keep-alive) filtré — comptés en fin\n")
        self._file.write(f"{sep}\n\n")

    @property
    def path(self) -> Optional[Path]:
        return self._path
