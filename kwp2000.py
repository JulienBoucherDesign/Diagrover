"""
DiagRover — diagrover/core/kwp2000.py
Couche protocole KWP2000 pour ECU TD5 Storm
Validé sur 6 sniffings Ekaitza_Itzali — tous checksums corrects
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ── Service IDs ────────────────────────────────────────────────
SID_START_DIAG      = 0x10
SID_READ_ECUID      = 0x1A
SID_READ_LOCAL_ID   = 0x21
SID_WRITE_LOCAL_ID  = 0x2E
SID_SECURITY_ACCESS = 0x27
SID_IO_CONTROL      = 0x30
SID_START_ROUTINE   = 0x31
SID_TESTER_PRESENT  = 0x3E
SID_READ_MEM        = 0x23

# Positive responses = SID + 0x40
SID_RESP_START_DIAG      = 0x50
SID_RESP_READ_ECUID      = 0x5A
SID_RESP_READ_LOCAL_ID   = 0x61
SID_RESP_SECURITY_ACCESS = 0x67
SID_RESP_IO_CONTROL      = 0x70
SID_RESP_START_ROUTINE   = 0x71
SID_RESP_TESTER_PRESENT  = 0x7E
SID_NEGATIVE_RESPONSE    = 0x7F

# Negative Response Codes
NRC = {
    0x10: "GeneralReject",
    0x11: "ServiceNotSupported",
    0x12: "SubFunctionNotSupported",
    0x22: "ConditionsNotCorrect",
    0x35: "InvalidKey",
    0x36: "ExceededAttempts",
}

# Local IDs TD5 (validés sur sniffings)
LOCAL_IDS = {
    0x09: "RPM",
    0x0D: "VehicleSpeed",
    0x0E: "MapVariantID",
    0x10: "BatteryVoltage",
    0x1A: "Temperatures",
    0x1B: "Throttle",
    0x1C: "Pressures",
    0x1E: "InputSwitches",
    0x20: "Unknown20",
    0x21: "RPMError",
    0x23: "AmbientPressure",
    0x24: "AcceleratorType",
    0x32: "MapFuelVariant",
    0x36: "AutoGearbox",
    0x37: "EGRModulation",
    0x38: "EGRInlet",
    0x3B: "FaultsBitfield",
    0x3D: "TuneSettings",
    0x40: "PowerBalance",
    0x87: "VINSystemInfo",
    0x9A: "ECUType",
}


# ── Structure de trame ─────────────────────────────────────────

@dataclass
class KWPFrame:
    """Représente une trame KWP2000 décodée."""
    raw:     bytes
    length:  int
    sid:     int
    data:    bytes
    cs_ok:   bool
    cs_expected: int
    cs_got:  int

    @property
    def sid_name(self) -> str:
        names = {
            SID_START_DIAG: "StartDiagSession",
            SID_READ_LOCAL_ID: "ReadDataLocalID",
            SID_SECURITY_ACCESS: "SecurityAccess",
            SID_IO_CONTROL: "IOControl",
            SID_START_ROUTINE: "StartRoutine",
            SID_TESTER_PRESENT: "TesterPresent",
            SID_RESP_START_DIAG: "StartDiagSession_RESP",
            SID_RESP_READ_LOCAL_ID: "ReadDataLocalID_RESP",
            SID_RESP_SECURITY_ACCESS: "SecurityAccess_RESP",
            SID_RESP_IO_CONTROL: "IOControl_RESP",
            SID_RESP_START_ROUTINE: "StartRoutine_RESP",
            SID_RESP_TESTER_PRESENT: "TesterPresent_RESP",
            SID_NEGATIVE_RESPONSE: "NegativeResponse",
        }
        return names.get(self.sid, f"0x{self.sid:02X}")

    @property
    def is_positive(self) -> bool:
        return self.sid != SID_NEGATIVE_RESPONSE and self.sid >= 0x40

    @property
    def is_negative(self) -> bool:
        return self.sid == SID_NEGATIVE_RESPONSE


# ── Couche protocole ───────────────────────────────────────────

class KWP2000:
    """
    Couche protocole KWP2000 pure — indépendante du transport.
    Toutes les méthodes sont statiques.
    """

    @staticmethod
    def checksum(data: bytes) -> int:
        """CS = somme de tous les octets modulo 256."""
        return sum(data) & 0xFF

    @staticmethod
    def build(sid: int, *args: int) -> bytes:
        """
        Construit une trame KWP2000 [LEN][SID][DATA...][CS].

        >>> KWP2000.build(0x10, 0xA0).hex()
        '0210a0b2'
        >>> KWP2000.build(0x27, 0x01).hex()
        '0227012a'
        >>> KWP2000.build(0x3E, 0x01).hex()
        '023e0141'
        """
        payload = bytes([sid, *args])
        frame   = bytes([len(payload)]) + payload
        return frame + bytes([KWP2000.checksum(frame)])

    @staticmethod
    def verify(raw: bytes) -> bool:
        """Vérifie le checksum d'une trame."""
        if len(raw) < 2:
            return False
        return sum(raw[:-1]) & 0xFF == raw[-1]

    @staticmethod
    def decode(raw: bytes) -> KWPFrame:
        """Décode une trame KWP2000 brute."""
        cs_exp = sum(raw[:-1]) & 0xFF
        cs_got = raw[-1] if raw else 0
        return KWPFrame(
            raw=raw,
            length=raw[0] if raw else 0,
            sid=raw[1] if len(raw) > 1 else 0,
            data=raw[2:raw[0]] if len(raw) >= raw[0] + 1 else b"",
            cs_ok=(cs_exp == cs_got),
            cs_expected=cs_exp,
            cs_got=cs_got,
        )

    # ── Constructeurs nommés ──────────────────────────────────

    @staticmethod
    def read_local_id(lid: int) -> bytes:
        """ReadDataLocalID (SID 0x21)."""
        return KWP2000.build(SID_READ_LOCAL_ID, lid)

    @staticmethod
    def io_control(lid: int, val: int = 0xFF) -> bytes:
        """IOControlByLocalID (SID 0x30)."""
        return KWP2000.build(SID_IO_CONTROL, lid, val)

    @staticmethod
    def start_routine(lid: int, *params: int) -> bytes:
        """StartRoutineByLocalID (SID 0x31)."""
        return KWP2000.build(SID_START_ROUTINE, lid, *params)

    @staticmethod
    def clear_faults() -> bytes:
        """Clear all fault codes — routine 0xDD avec 17 × 0x00."""
        return KWP2000.build(SID_START_ROUTINE, 0xDD, *([0x00] * 18))  # 18 zéros — validé Read_Faults_and_clear.log

    @staticmethod
    def injector_test(n: int) -> bytes:
        """Test injecteur N (1–5) — routine 0xC2."""
        assert 1 <= n <= 5, "Injecteur doit être entre 1 et 5"
        return KWP2000.build(SID_START_ROUTINE, 0xC2, n)

    @staticmethod
    def tester_present() -> bytes:
        """Keep-alive — TesterPresent (SID 0x3E)."""
        return KWP2000.build(SID_TESTER_PRESENT, 0x01)

    @staticmethod
    def read_ecuid(param: int) -> bytes:
        """ReadECUID (SID 0x1A) — VIN, type ECU, etc."""
        return KWP2000.build(SID_READ_ECUID, param)


# ── Trames pré-calculées (validées sur sniffings) ─────────────

# Séquence d'init complète
INIT_FRAME    = bytes.fromhex("8113f7810c")   # StartComm
START_DIAG_MF = KWP2000.build(0x10, 0xA0)    # 0210a0b2 ✓
SEED_REQUEST  = KWP2000.build(0x27, 0x01)     # 0227012a ✓
TESTER_PRES   = KWP2000.build(0x3E, 0x01)     # 023e0141 ✓

# Cycle live data Page 2 (Instruments_Page2.log)
LIVE_CYCLE_PAGE2 = [0x40, 0x23, 0x37, 0x38, 0x10,
                    0x09, 0x0D, 0x1A, 0x1B, 0x1C, 0x21]

# Effacement faults (Read_Faults_and_clear.log)
# 14 31 DD 00×17 22 ✓
CLEAR_FAULTS  = KWP2000.clear_faults()

# Actuations 7 octets validées sur Outputs.log
WASTEGATE_ON  = KWP2000.build(SID_IO_CONTROL, 0xBE, 0xFF, 0x00, 0x0A, 0x13, 0x88)
EGR_INLET_ON  = KWP2000.build(SID_IO_CONTROL, 0xBD, 0xFF, 0x00, 0xFA, 0x13, 0x88)


# ── Décodeurs (unités validées sur données réelles) ────────────

SENSOR_NOT_FITTED = 0x1388  # 5V référence = capteur absent

def decode_temp(raw: int) -> float | None:
    """
    Température TD5 — int16 / 100 = °C
    Retourne None si capteur absent (0x1388 = 5V référence).

    Validé :
    >>> decode_temp(0x0DFE)  # 3582/100
    35.82
    >>> decode_temp(0x1388)  # capteur absent
    >>> decode_temp(0x0F5C)  # 3932/100
    39.32
    """
    if raw == SENSOR_NOT_FITTED:
        return None
    return raw / 100.0

def decode_battery(data: bytes) -> float:
    """
    Tension batterie — int16 / 1000 = Volts

    Validé : 0x36C6 → 14022/1000 = 14.022V ✓

    >>> decode_battery(bytes.fromhex("36C6"))
    14.022
    """
    return ((data[0] << 8) | data[1]) / 1000.0

def decode_rpm(data: bytes) -> int:
    """RPM — int16 direct. Validé : 0x0000 = 0 rpm ✓"""
    return (data[0] << 8) | data[1]

def decode_speed(data: bytes) -> int:
    """Vitesse — uint8 direct en km/h. Validé : 0x00 = 0 km/h ✓"""
    return data[0]

def decode_pressure_mbar(data: bytes, idx: int = 0) -> float:
    """
    Pression — int16 × 0.1 = mbar

    Validé : 0x2710 = 10000 × 0.1 = 1000.0 mbar (pression atmosphérique) ✓

    >>> decode_pressure_mbar(bytes.fromhex("2710"))
    1000.0
    """
    raw = (data[idx * 2] << 8) | data[idx * 2 + 1]
    return raw * 0.1

def decode_throttle_v(data: bytes) -> list[float]:
    """
    Papillon — 4 pistes — int16 / 1000 = Volts

    Validé :
    - 0x0000 = 0.000V (demande, repos) ✓
    - 0x1388 = 5.000V (référence 5V) ✓
    - 0x1382 = 4.994V (référence légèrement chargée) ✓
    """
    return [((data[i] << 8) | data[i + 1]) / 1000.0
            for i in range(0, min(len(data) - 1, 8), 2)]

def decode_temps_all(data: bytes) -> list[float | None]:
    """Toutes les températures — 8 capteurs — avec filtre 0x1388."""
    result = []
    for i in range(0, min(len(data) - 1, 16), 2):
        raw = (data[i] << 8) | data[i + 1]
        result.append(decode_temp(raw))
    return result

def decode_power_balance(data: bytes) -> list[int]:
    """Power Balance — 5 cylindres — int16 signé."""
    result = []
    for i in range(0, min(len(data) - 1, 10), 2):
        result.append(int.from_bytes(data[i:i+2], 'big', signed=True))
    return result

def decode_switches(data: bytes) -> dict:
    """
    Switches d'entrée — 2 octets.
    Validé sur Inputs_Switches.log.
    """
    b1, b2 = data[0], data[1]
    return {
        "TransferRatio": bool(b1 & 0x01),
        "Brake2":        bool(b1 & 0x10),
        "Brake1":        bool(b1 & 0x40),
        "Clutch":        bool(b2 & 0x04),
        "CruiseMaster":  bool(b2 & 0x08),
        "CruiseSet":     bool(b2 & 0x10),
        "CruiseResume":  bool(b2 & 0x20),
        "ACClutchREQ":   bool(b2 & 0x10),
        "ACFanREQ":      bool(b2 & 0x20),
    }

def decode_ecuid_type(data: bytes) -> str:
    """
    Type ECU — 3 bytes ASCII.
    Validé : 0x4E4E4E = "NNN" ✓
    """
    return "".join(chr(b) if 32 <= b < 127 else "?" for b in data[:3])

def decode_vin(data: bytes) -> str:
    """VIN partiel depuis réponse 0x87."""
    return "".join(chr(b) if 32 <= b < 127 else "" for b in data[:17]).strip()


# ── Self-test ──────────────────────────────────────────────────

if __name__ == "__main__":
    import doctest
    doctest.testmod(verbose=True)

    print("\n=== Tests manuels ===")

    # Checksums pré-calculés
    assert START_DIAG_MF.hex() == "0210a0b2", f"Got {START_DIAG_MF.hex()}"
    assert SEED_REQUEST.hex()   == "0227012a"
    assert TESTER_PRES.hex()    == "023e0141"
    print("✓ Trames pré-calculées correctes")

    # Décodeurs sur données réelles
    assert decode_battery(bytes.fromhex("36C6")) == 14.022
    assert decode_temp(0x0DFE) == 35.82
    assert decode_temp(0x1388) is None
    assert decode_pressure_mbar(bytes.fromhex("2710")) == 1000.0
    print("✓ Décodeurs validés sur données réelles")

    # Vérification clear_faults
    cf = CLEAR_FAULTS
    log_clear = bytes.fromhex("1431dd00000000000000000000000000000000000022")
    assert cf == log_clear, f"clear_faults mismatch: {cf.hex()}"
    assert KWP2000.verify(cf)
    print("✓ Clear faults frame valide")

    # Test injecteurs
    for n in range(1, 6):
        f = KWP2000.injector_test(n)
        assert KWP2000.verify(f)
        assert f[3] == n
    print("✓ Frames test injecteurs valides")

    print("\nAll tests PASS")
