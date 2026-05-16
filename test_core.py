"""
DiagRover — tests/test_core.py
Validation complète des couches protocole
Vecteurs de test issus des sniffings Ekaitza_Itzali réels
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from diagrover.core.kwp2000 import (
    KWP2000, KWPFrame,
    INIT_FRAME, START_DIAG_MF, SEED_REQUEST, TESTER_PRES, CLEAR_FAULTS,
    decode_battery, decode_rpm, decode_speed, decode_temp,
    decode_pressure_mbar, decode_throttle_v, decode_temps_all,
    decode_power_balance, decode_switches, decode_ecuid_type,
    SENSOR_NOT_FITTED, LIVE_CYCLE_PAGE2, LOCAL_IDS,
)
from diagrover.core.td5keygen import (
    td5_keygen, td5_keygen_from_bytes, build_key_frame,
    keygen_count, TEST_VECTORS,
)


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════

OK = "  ✓"
FAIL = "  ✗"

def check(condition, msg):
    if condition:
        print(f"{OK} {msg}")
    else:
        print(f"{FAIL} {msg}")
    return condition


# ════════════════════════════════════════════════════════════════
# Test 1 — KWP2000 build / verify / checksum
# ════════════════════════════════════════════════════════════════

def test_kwp_build():
    print("\n── KWP2000 build/verify ──")
    all_ok = True

    # Trames validées sur sniffings réels
    cases = [
        (KWP2000.build(0x10, 0xA0),     "0210a0b2", "StartDiagSession(0xA0)"),
        (KWP2000.build(0x27, 0x01),     "0227012a", "SecurityAccess RequestSeed"),
        (KWP2000.build(0x3E, 0x01),     "023e0141", "TesterPresent"),
        (KWP2000.build(0x21, 0x3B),     "02213b5e", "ReadLocalID 0x3B (faults)"),
        (KWP2000.build(0x21, 0x09),     "0221092c", "ReadLocalID 0x09 (RPM)"),
        (KWP2000.build(0x21, 0x0D),     "02210d30", "ReadLocalID 0x0D (speed)"),
        (KWP2000.build(0x21, 0x10),     "02211033", "ReadLocalID 0x10 (battery)"),
        (KWP2000.build(0x21, 0x1A),     "02211a3d", "ReadLocalID 0x1A (temps)"),
        (KWP2000.build(0x21, 0x1B),     "02211b3e", "ReadLocalID 0x1B (throttle)"),
        (KWP2000.build(0x21, 0x1C),     "02211c3f", "ReadLocalID 0x1C (pressures)"),
        (KWP2000.build(0x21, 0x40),     "02214063", "ReadLocalID 0x40 (power bal)"),
        (KWP2000.build(0x30, 0xA3, 0xFF), "0330a3ffd5", "IOControl ACClutch ON"),
        (KWP2000.build(0x30, 0xA1, 0xFF), "0330a1ffd3", "IOControl FuelPump ON"),
        (KWP2000.build(0x31, 0xC2, 0x01), "0331c201f7", "StartRoutine Injector 1"),
        (KWP2000.build(0x31, 0xC2, 0x05), "0331c205fb", "StartRoutine Injector 5"),
    ]

    for frame, expected_hex, desc in cases:
        ok = frame.hex() == expected_hex
        all_ok = all_ok and ok
        check(ok, f"{desc}: {frame.hex()} (expected {expected_hex})")

    return all_ok


# ════════════════════════════════════════════════════════════════
# Test 2 — Checksums sur trames réelles des logs
# ════════════════════════════════════════════════════════════════

def test_real_frames():
    print("\n── Vérification checksums sur trames réelles ──")
    all_ok = True

    # Toutes les trames uniques des sniffings
    real_frames = [
        # Settings.txt
        ("8113f7810c", "Init frame"),
        ("0210a0b2",   "StartDiagSession"),
        ("015051",     "Session OK"),
        ("0227012a",   "Seed request"),
        ("046701173fc2","Seed response 0x173F"),
        ("042702c17361","Key 0xC173"),
        ("0267026b",   "AUTH OK"),
        ("023e0141",   "TesterPresent"),
        ("017e7f",     "TesterPresent resp"),
        # Read_Faults.log
        ("0467010439a9","Seed 0x0439"),
        ("0427024043b0","Key 0x4043"),
        # Outputs.log
        ("04670171d4b1","Seed 0x71D4"),
        ("042702ace3bc","Key 0xACE3"),
        ("0330a3ffd5",  "IOCtrl ACClutch"),
        ("0330a4ffd6",  "IOCtrl ACFan"),
        ("0330a2ffd4",  "IOCtrl MIL"),
        ("0330a1ffd3",  "IOCtrl FuelPump"),
        ("0330b3ffe5",  "IOCtrl GlowPlugs"),
        ("0330b7ffe9",  "IOCtrl RevCounter"),
        ("0330baffec",  "IOCtrl TempGauge"),
        ("0331c201f7",  "Injector 1"),
        ("0331c202f8",  "Injector 2"),
        ("0331c203f9",  "Injector 3"),
        ("0331c204fa",  "Injector 4"),
        ("0331c205fb",  "Injector 5"),
        # Inputs_Switches.log
        ("0467018c0800","Seed 0x8C08"),
        ("042702e6475a","Key 0xE647"),
        # Read_Faults_and_clear.log
        ("1431dd00000000000000000000000000000000000022", "Clear faults"),
    ]

    for hex_str, desc in real_frames:
        raw = bytes.fromhex(hex_str)
        ok = KWP2000.verify(raw)
        all_ok = all_ok and ok
        check(ok, f"{desc} [{hex_str[:20]}{'...' if len(hex_str)>20 else ''}]")

    return all_ok


# ════════════════════════════════════════════════════════════════
# Test 3 — Décodeurs sur valeurs réelles
# ════════════════════════════════════════════════════════════════

def test_decoders():
    print("\n── Décodeurs sur données réelles ──")
    all_ok = True

    # Batterie : 0x36C6 → 14.022V (moteur tournant, alternateur)
    v = decode_battery(bytes.fromhex("36C6"))
    ok = abs(v - 14.022) < 0.001
    all_ok = all_ok and ok
    check(ok, f"Batterie 0x36C6 → {v:.3f}V (attendu 14.022V)")

    # RPM : 0x0000 → 0 (moteur arrêté)
    r = decode_rpm(bytes.fromhex("0000"))
    all_ok = all_ok and check(r == 0, f"RPM 0x0000 → {r} rpm")

    # Vitesse : 0x00 → 0 km/h
    s = decode_speed(bytes.fromhex("00"))
    all_ok = all_ok and check(s == 0, f"Vitesse 0x00 → {s} km/h")

    # Pression atmosphérique : 0x2710 → 1000.0 mbar
    p = decode_pressure_mbar(bytes.fromhex("2710"))
    all_ok = all_ok and check(abs(p - 1000.0) < 0.01,
                               f"MAP 0x2710 → {p:.1f} mbar (attendu 1000.0)")

    # Température coolant : 0x0DFE → 35.82°C
    t = decode_temp(0x0DFE)
    all_ok = all_ok and check(abs(t - 35.82) < 0.01,
                               f"Temp 0x0DFE → {t:.2f}°C (attendu 35.82°C)")

    # Capteur absent : 0x1388 → None
    t_none = decode_temp(0x1388)
    all_ok = all_ok and check(t_none is None,
                               "Temp 0x1388 → None (capteur absent)")

    # Température admission : 0x0F5C → 39.32°C
    t2 = decode_temp(0x0F5C)
    all_ok = all_ok and check(abs(t2 - 39.32) < 0.01,
                               f"Temp 0x0F5C → {t2:.2f}°C (attendu 39.32°C)")

    # Papillon ref 5V : 0x1388 → 5.000V
    th = decode_throttle_v(bytes.fromhex("00001388000013820000"))
    all_ok = all_ok and check(abs(th[1] - 5.000) < 0.001,
                               f"Throttle T2 0x1388 → {th[1]:.3f}V (ref 5V)")
    all_ok = all_ok and check(abs(th[3] - 4.994) < 0.001,
                               f"Throttle T4 0x1382 → {th[3]:.3f}V")

    # Températures complètes (Instruments_Page2.log)
    # 12 61 1A 0D FE 13 88 0F 5C 13 88 10 88 00 00 0D 04 13 88 7D
    temps_data = bytes.fromhex("0dfe13880f5c138810880000 0d041388")
    # Retirer les espaces
    temps_data = bytes.fromhex("0dfe13880f5c13881088000d041388")
    # Correction : 16 octets = 8 paires
    temps_data = bytes.fromhex("0dfe13880f5c1388108800000d041388")
    temps = decode_temps_all(temps_data)
    check(len(temps) == 8, f"Nombre températures: {len(temps)}")
    check(temps[0] is not None and abs(temps[0] - 35.82) < 0.01,
          f"T0 (coolant) = {temps[0]}")
    check(temps[1] is None, "T1 = None (capteur absent)")

    return all_ok


# ════════════════════════════════════════════════════════════════
# Test 4 — Seed-Key td5keygen
# ════════════════════════════════════════════════════════════════

def test_keygen():
    print("\n── td5keygen — 5 vecteurs réels ──")
    all_ok = True

    for seed, expected, src, exp_count in TEST_VECTORS:
        result = td5_keygen(seed)
        count  = keygen_count(seed)
        ok     = (result == expected) and (count == exp_count)
        all_ok = all_ok and ok
        check(ok, f"seed=0x{seed:04X} → 0x{result:04X} count={count} [{src}]")

    # Frames complètes
    print()
    frames = [
        (0x17, 0x3F, "042702c17361"),
        (0x71, 0xD4, "042702ace3bc"),
        (0x8C, 0x08, "042702e6475a"),
    ]
    for sh, sl, expected in frames:
        frame = build_key_frame(sh, sl)
        ok    = frame.hex() == expected
        all_ok = all_ok and ok
        check(ok, f"frame({sh:02X},{sl:02X}) → {frame.hex()}")

    return all_ok


# ════════════════════════════════════════════════════════════════
# Test 5 — Cohérence LIVE_CYCLE_PAGE2
# ════════════════════════════════════════════════════════════════

def test_live_cycle():
    print("\n── Cycle live data Page 2 ──")
    expected = [0x40, 0x23, 0x37, 0x38, 0x10, 0x09, 0x0D, 0x1A, 0x1B, 0x1C, 0x21]
    ok = LIVE_CYCLE_PAGE2 == expected
    check(ok, f"Cycle 11 PIDs: {[hex(x) for x in LIVE_CYCLE_PAGE2]}")

    # Tous les LID du cycle sont dans la table LOCAL_IDS
    for lid in LIVE_CYCLE_PAGE2:
        in_table = lid in LOCAL_IDS
        check(in_table, f"LID 0x{lid:02X} ({LOCAL_IDS.get(lid,'?')}) dans LOCAL_IDS")

    return ok


# ════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("DiagRover — Tests couche protocole")
    print("=" * 60)

    results = [
        test_kwp_build(),
        test_real_frames(),
        test_decoders(),
        test_keygen(),
        test_live_cycle(),
    ]

    passed = sum(1 for r in results if r)
    total  = len(results)

    print(f"\n{'='*60}")
    print(f"  {passed}/{total} suites PASS")
    if all(results):
        print("  ✓ TOUS LES TESTS PASSENT")
    else:
        print("  ✗ CERTAINS TESTS ÉCHOUENT")
    print("=" * 60)

    sys.exit(0 if all(results) else 1)
