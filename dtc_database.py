"""
DiagRover — diagrover/data/dtc_database.py
Base de données DTC Land Rover TD5
SQLite — codes SAE standard + codes propriétaires LR

Bit positions issues de l'analyse des sniffings Ekaitza_Itzali.
Sources : Technical Academy LR, DiscoTD5.com, sniffings réels.
"""

from __future__ import annotations
import sqlite3
import os
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "diagrover.db"


# ── Codes DTC connus pour le TD5 ──────────────────────────────
# Format : (bit_pos, code_sae, description_fr, severity)
# severity : 1=info  2=warning  3=critical
# bit_pos : position dans les 280 bits du Local ID 0x3B (byte*8 + bit)
# Convention bits : byte 0 bit 7 = pos 0, byte 0 bit 0 = pos 7, etc.

TD5_DTC_TABLE: list[tuple[int, str, str, int]] = [
    # ── Byte 0 (pos 0-7) — Moteur général ─────────────────────
    (0,  "P0100", "Débit d'air masse (MAF) — circuit ouvert/court-circuit", 3),
    (1,  "P0105", "Capteur pression collecteur (MAP) — circuit défectueux", 3),
    (2,  "P0110", "Capteur température admission — circuit défectueux", 2),
    (3,  "P0115", "Capteur température liquide refroidissement — défaut", 2),
    (4,  "P0120", "Capteur position papillon (TPS) — circuit A défectueux", 3),
    (5,  "P0121", "Capteur position papillon — plage/performance hors spec", 2),
    (6,  "P1120", "Capteur position papillon B — circuit défectueux (LR)", 3),
    (7,  "P1121", "Capteur position papillon — incohérence entre pistes", 3),

    # ── Byte 1 (pos 8-15) — Injection ──────────────────────────
    (8,  "P0190", "Capteur pression rampe carburant — circuit défectueux", 3),
    (9,  "P0191", "Capteur pression rampe carburant — performance", 2),
    (10, "P0192", "Capteur pression rampe — tension trop basse", 3),
    (11, "P0193", "Capteur pression rampe — tension trop haute", 3),
    (12, "P0200", "Circuit injecteur — défaut général", 3),
    (13, "P0201", "Circuit injecteur 1 — circuit ouvert", 3),
    (14, "P0202", "Circuit injecteur 2 — circuit ouvert", 3),
    (15, "P0203", "Circuit injecteur 3 — circuit ouvert", 3),

    # ── Byte 2 (pos 16-23) — Injecteurs suite ──────────────────
    (16, "P0204", "Circuit injecteur 4 — circuit ouvert", 3),
    (17, "P0205", "Circuit injecteur 5 — circuit ouvert", 3),
    (18, "P1201", "Injecteur 1 — défaut de contrôle", 3),
    (19, "P1202", "Injecteur 2 — défaut de contrôle", 3),
    (20, "P1203", "Injecteur 3 — défaut de contrôle", 3),
    (21, "P1204", "Injecteur 4 — défaut de contrôle", 3),
    (22, "P1205", "Injecteur 5 — défaut de contrôle", 3),
    (23, "P0300", "Raté d'allumage multiple détecté", 3),

    # ── Byte 3 (pos 24-31) — Ratés / combustion ────────────────
    (24, "P0301", "Raté d'allumage cylindre 1", 3),
    (25, "P0302", "Raté d'allumage cylindre 2", 3),
    (26, "P0303", "Raté d'allumage cylindre 3", 3),
    (27, "P0304", "Raté d'allumage cylindre 4", 3),
    (28, "P0305", "Raté d'allumage cylindre 5", 3),
    (29, "P0380", "Circuit bougies de préchauffage — groupe A", 2),
    (30, "P0381", "Voyant bougies préchauffage — circuit", 1),
    (31, "P1380", "Circuit bougies de préchauffage — surchauffe (LR)", 2),

    # ── Byte 4 (pos 32-39) — EGR / turbo ───────────────────────
    (32, "P0400", "Débit recirculation gaz échappement (EGR) insuffisant", 2),
    (33, "P0401", "Débit EGR insuffisant détecté", 2),
    (34, "P0402", "Débit EGR excessif détecté", 2),
    (35, "P0403", "Vanne EGR — circuit défectueux", 3),
    (36, "P0404", "Vanne EGR — plage/performance", 2),
    (37, "P0405", "Capteur position vanne EGR A — tension basse", 2),
    (38, "P0406", "Capteur position vanne EGR A — tension haute", 2),
    (39, "P1400", "Modulateur wastegate turbo — circuit défectueux (LR)", 3),

    # ── Byte 5 (pos 40-47) — Turbo / pression ──────────────────
    (40, "P0234", "Régulation turbocompresseur — surpression détectée", 3),
    (41, "P0235", "Capteur pression suralimentation A — circuit", 2),
    (42, "P0236", "Capteur pression suralimentation A — performance", 2),
    (43, "P0237", "Capteur pression suralimentation A — tension basse", 2),
    (44, "P0238", "Capteur pression suralimentation A — tension haute", 2),
    (45, "P1235", "Pompe injection — circuit basse vitesse (LR)", 3),
    (46, "P1236", "Pompe injection — circuit haute vitesse (LR)", 3),
    (47, "P1237", "Pompe injection — commande abandonnée (LR)", 3),

    # ── Byte 6-7 (pos 48-63) — Transmission / vitesse ──────────
    (48, "P0500", "Capteur vitesse véhicule (VSS) — défaut", 2),
    (49, "P0501", "Capteur vitesse — plage/performance", 2),
    (50, "P0502", "Capteur vitesse — signal trop bas", 2),
    (51, "P0503", "Capteur vitesse — signal instable/intermittent", 2),
    (56, "P0700", "Défaut système contrôle transmission (TCM)", 2),
    (57, "P0705", "Capteur position sélecteur boîte auto — circuit", 2),

    # ── Byte 8 (pos 64-71) — Carburant ─────────────────────────
    (64, "P0087", "Pression système carburant — trop basse", 3),
    (65, "P0088", "Pression système carburant — trop haute", 3),
    (66, "P0089", "Régulateur pression carburant — performance", 3),
    (67, "P0090", "Régulateur pression carburant — circuit", 3),
    (68, "P1093", "Pompe injection — défaut haute pression (LR)", 3),
    (69, "P1094", "Pompe injection — défaut basse pression (LR)", 3),
    (70, "P1095", "Capteur pression carburant — circuit court à masse (LR)", 3),
    (71, "P0460", "Capteur niveau carburant — plage/performance", 1),

    # ── Byte 9 (pos 72-79) — Température / refroidissement ─────
    (72, "P0217", "Surchauffe moteur — condition détectée", 3),
    (73, "P0218", "Surchauffe boîte transmission — condition détectée", 2),
    (74, "P0597", "Thermostat refroidissement — stuck open", 2),
    (75, "P0598", "Circuit commande thermostat — tension basse", 2),
    (76, "P0599", "Circuit commande thermostat — tension haute", 2),
    (77, "P1293", "Capteur température carburant — court à masse (LR)", 2),
    (78, "P1294", "Capteur température carburant — circuit ouvert (LR)", 2),
    (79, "P1295", "Capteur température carburant — tension haute (LR)", 2),

    # ── Bytes 10-12 (pos 80-103) — Système électrique ──────────
    (80, "P0562", "Tension système — trop basse", 3),
    (81, "P0563", "Tension système — trop haute", 3),
    (82, "P0606", "ECU — défaut processeur", 3),
    (83, "P0601", "ECU — erreur mémoire interne", 3),
    (84, "P0602", "ECU — erreur programmation", 3),
    (85, "P0603", "ECU — KAM défectueux (Keep Alive Memory)", 2),
    (86, "P0604", "ECU — RAM interne défectueuse", 3),
    (87, "P0605", "ECU — ROM interne défectueuse", 3),
    (88, "P0613", "ECU — processeur transmission défectueux", 3),
    (96, "P0615", "Circuit relais démarreur — défaut", 2),
    (97, "P0620", "Circuit commande alternateur — défaut", 2),

    # ── Byte 13 (pos 104-111) — Communication (0xFF dans logs!) ─
    (104, "U0001", "Bus CAN — communication lente", 2),
    (105, "U0100", "Perte communication avec ECU moteur", 3),
    (106, "U0101", "Perte communication avec ECU transmission", 2),
    (107, "U0114", "Perte communication avec module 4WD", 2),
    (108, "U0121", "Perte communication avec ABS/ETC", 2),
    (109, "U0140", "Perte communication avec BCU", 2),
    (110, "U0155", "Perte communication avec tableau de bord", 1),
    (111, "U0415", "Données invalides reçues de l'ABS/ETC", 2),

    # ── Byte 14-15 (pos 112-127) — Capteurs divers ─────────────
    (112, "P0650", "Circuit voyant témoin défaut (MIL) — défaut", 1),
    (113, "P0653", "Circuit capteur température admission — tension haute", 2),
    (114, "P0654", "Circuit voyant régime moteur — défaut", 1),
    (115, "P0657", "Circuit alimentation actionneur A — tension haute", 2),
    (116, "P0658", "Circuit alimentation actionneur A — tension basse", 2),
    (120, "P1600", "Alimentation ECU — perturbation détectée (LR)", 2),
    (121, "P1601", "Perte communication ECU avec immobiliseur (LR)", 3),
    (124, "P1609", "Immobiliseur — code sécurité invalide (LR)", 3),
    (125, "P1610", "Immobiliseur — ECU verrouillé (LR)", 3),
    (126, "P1611", "Immobiliseur — défaut clé (LR)", 3),
    (127, "P1612", "Immobiliseur — défaut mémoire (LR)", 3),

    # ── Bytes 16-17 (pos 128-143) — ABS / traction ─────────────
    (128, "C1200", "ABS — défaut capteur roue avant gauche", 3),
    (129, "C1201", "ABS — défaut capteur roue avant droite", 3),
    (130, "C1202", "ABS — défaut capteur roue arrière gauche", 3),
    (131, "C1203", "ABS — défaut capteur roue arrière droite", 3),
    (132, "C1204", "ABS — défaut module hydraulique", 3),
    (133, "C1205", "ABS — défaut moteur pompe", 3),
    (136, "C1210", "ETC — défaut capteur vitesse roue", 3),
    (137, "C1211", "ETC — défaut circuit commande vanne", 3),
    (138, "C1212", "ETC — défaut alimentation", 3),
    (139, "C1213", "ETC — surchauffe module hydraulique", 2),
    (140, "C1214", "ABS/ETC — défaut capteur décélération", 2),
    (141, "C1215", "ABS — défaut capteur roue — signal absent", 3),
    (142, "C1216", "ABS — défaut capteur roue — fréquence hors plage", 2),
    (143, "C1217", "ABS — pression hydraulique résiduelle détectée", 2),

    # ── Bytes 18-19 (pos 144-159) — Suspension SLS ─────────────
    (144, "C1232", "SLS — capteur hauteur avant gauche — défaut", 3),
    (145, "C1233", "SLS — capteur hauteur avant droite — défaut", 3),
    (146, "C1234", "SLS — capteur hauteur arrière gauche — défaut", 3),
    (147, "C1235", "SLS — capteur hauteur arrière droite — défaut", 3),
    (148, "C1236", "SLS — compresseur — surchauffe", 2),
    (149, "C1237", "SLS — compresseur — temps fonctionnement excessif", 2),
    (150, "C1238", "SLS — fuite de pression détectée", 3),
    (151, "C1239", "SLS — soupape échappement — défaut", 3),
    (152, "C1240", "SLS — circuit électrovanne avant gauche — défaut", 3),
    (153, "C1241", "SLS — circuit électrovanne avant droite — défaut", 3),
    (154, "C1242", "SLS — circuit électrovanne arrière gauche — défaut", 3),
    (155, "C1243", "SLS — circuit électrovanne arrière droite — défaut", 3),

    # ── Bytes 20-21 (pos 160-175) — BCU / carrosserie ──────────
    (160, "B1200", "BCU — défaut alimentation capteur", 2),
    (161, "B1201", "BCU — défaut circuit verrouillage portes", 2),
    (162, "B1202", "BCU — défaut capteur porte conducteur", 1),
    (163, "B1203", "BCU — défaut capteur porte passager", 1),
    (164, "B1204", "BCU — défaut capteur porte arrière gauche", 1),
    (165, "B1205", "BCU — défaut capteur porte arrière droite", 1),
    (166, "B1206", "BCU — défaut circuit lève-vitre", 2),
    (167, "B1207", "BCU — défaut circuit déverrouillage coffre", 1),
    (168, "B1208", "BCU — défaut capteur température intérieure", 1),
    (169, "B1209", "BCU — défaut circuit rétroviseurs chauffants", 1),
    (170, "B1210", "BCU — défaut circuit phares", 2),
    (171, "B1211", "BCU — défaut circuit feux arrière", 2),
    (175, "B1215", "BCU — défaut circuit klaxon", 1),

    # ── Bytes 22-25 (pos 176-207) — Divers ─────────────────────
    (184, "P1800", "Embrayage AC — défaut circuit commande (LR)", 2),
    (185, "P1801", "Ventilateur AC — défaut circuit commande (LR)", 2),
    (186, "P1802", "Compresseur AC — surchauffe détectée (LR)", 2),
    (202, "P1900", "Défaut interne ECU — non-volatile memory (LR)", 3),
    (203, "P1901", "Défaut calibration ECU (LR)", 2),
    (204, "P1902", "Défaut configuration ECU — type accélérateur (LR)", 2),
    (205, "P1903", "Défaut configuration ECU — type map (LR)", 2),
]


# ── Schéma SQLite ─────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS dtc_lr (
    bit_pos     INTEGER PRIMARY KEY,
    code        TEXT NOT NULL,
    desc_fr     TEXT NOT NULL,
    severity    INTEGER DEFAULT 2
);

CREATE TABLE IF NOT EXISTS vehicles (
    vin         TEXT PRIMARY KEY,
    name        TEXT,
    ecu_type    TEXT,
    model_year  INTEGER,
    engine      TEXT,
    protocol_map TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_vin TEXT,
    started_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    ended_at    TEXT,
    mileage_km  INTEGER,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS session_faults (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER,
    bit_pos     INTEGER,
    code        TEXT,
    status      TEXT DEFAULT 'active',
    found_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sf_session ON session_faults(session_id);
"""


# ── API ───────────────────────────────────────────────────────

def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    """Crée ou ouvre la base de données DiagRover."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _populate_dtc(conn)
    conn.commit()
    return conn


def _populate_dtc(conn: sqlite3.Connection):
    """Insère les codes DTC connus si la table est vide."""
    count = conn.execute("SELECT COUNT(*) FROM dtc_lr").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO dtc_lr(bit_pos,code,desc_fr,severity) VALUES(?,?,?,?)",
            TD5_DTC_TABLE
        )


def decode_fault_bitfield(data: bytes) -> list[dict]:
    """
    Décode les 35 octets du Local ID 0x3B en liste de codes défauts.

    Returns:
        Liste de dicts {bit_pos, code, desc_fr, severity, known}
        triée par sévérité décroissante.

    Validé sur Read_Faults.log — 45 bits actifs détectés.
    """
    # Table de lookup en mémoire (évite N requêtes SQL)
    lookup = {row[0]: row for row in TD5_DTC_TABLE}

    faults = []
    for byte_idx, byte in enumerate(data[:35]):
        for bit in range(8):
            # Convention : bit 7 du byte N = position N*8
            if byte & (1 << (7 - bit)):
                bit_pos = byte_idx * 8 + bit
                if bit_pos in lookup:
                    _, code, desc, severity = lookup[bit_pos]
                    faults.append({
                        "bit_pos":  bit_pos,
                        "code":     code,
                        "desc_fr":  desc,
                        "severity": severity,
                        "known":    True,
                    })
                else:
                    faults.append({
                        "bit_pos":  bit_pos,
                        "code":     f"LR#{bit_pos:03d}",
                        "desc_fr":  f"Code propriétaire Land Rover — bit {bit_pos} (non documenté)",
                        "severity": 1,
                        "known":    False,
                    })

    # Tri : critical d'abord, puis warning, puis info
    faults.sort(key=lambda f: -f["severity"])
    return faults


def lookup_code(bit_pos: int) -> Optional[dict]:
    """Retourne les infos d'un code par sa position de bit."""
    for row in TD5_DTC_TABLE:
        if row[0] == bit_pos:
            return {"bit_pos": row[0], "code": row[1],
                    "desc_fr": row[2], "severity": row[3]}
    return None


SEVERITY_LABEL = {1: "Info", 2: "Warning", 3: "Critical"}
SEVERITY_COLOR = {1: "cyan", 2: "yellow", 3: "red"}


# ── Self-test ─────────────────────────────────────────────────

if __name__ == "__main__":
    # Valider le décodage sur les données réelles
    test_data = bytes.fromhex(
        "c0c0000780870000701d000000ff00cf008f"
        "00003801008000280000000000000000"
    )
    faults = decode_fault_bitfield(test_data)
    print(f"=== Décodage Read_Faults.log ===")
    print(f"Bits actifs : {len(faults)}")
    for f in faults:
        known_str = "" if f["known"] else " [inconnu]"
        print(f"  [{SEVERITY_LABEL[f['severity']]}] {f['code']} — {f['desc_fr'][:60]}{known_str}")

    # Test DB
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        conn = init_db(Path(tmp.name))
        count = conn.execute("SELECT COUNT(*) FROM dtc_lr").fetchone()[0]
        print(f"\n=== Base DTC : {count} codes enregistrés ===")
        conn.close()
