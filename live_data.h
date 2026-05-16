#pragma once
// ═══════════════════════════════════════════════════════════════
// DiagRover — live_data.h
// Décodeurs live data TD5 — validés sur sniffings Ekaitza_Itzali
// Toutes les unités et formules vérifiées sur données réelles
// ═══════════════════════════════════════════════════════════════
#include <Arduino.h>
#include "usb_comm.h"

// ── Constante capteur absent ──────────────────────────────────
// 0x1388 = tension 5V sur circuit ouvert (capteur non connecté)
// → retourner NaN / ne pas envoyer la valeur
#define SENSOR_NOT_FITTED 0x1388

// ── Local IDs du cycle Page 2 (Instruments_Page2.log) ────────
#define LID_RPM          0x09
#define LID_SPEED        0x0D
#define LID_BATTERY      0x10
#define LID_TEMPS        0x1A
#define LID_THROTTLE     0x1B
#define LID_PRESSURES    0x1C
#define LID_SWITCHES     0x1E
#define LID_RPM_ERROR    0x21
#define LID_AMB_PRESS    0x23
#define LID_EGR_MOD      0x37
#define LID_EGR_INLET    0x38
#define LID_FAULTS       0x3B
#define LID_SETTINGS     0x3D
#define LID_POWER_BAL    0x40

// ── Cycle live data complet ───────────────────────────────────
// Ordre validé sur Instruments_Page2.log
static const uint8_t LIVE_CYCLE_PAGE2[] = {
    LID_POWER_BAL,   // 0x40 — 10 octets
    LID_AMB_PRESS,   // 0x23 — 4 octets
    LID_EGR_MOD,     // 0x37 — 2 octets
    LID_EGR_INLET,   // 0x38 — 2 octets
    LID_BATTERY,     // 0x10 — 4 octets
    LID_RPM,         // 0x09 — 2 octets
    LID_SPEED,       // 0x0D — 1 octet
    LID_TEMPS,       // 0x1A — 16 octets
    LID_THROTTLE,    // 0x1B — 8 octets
    LID_PRESSURES,   // 0x1C — 8 octets
    LID_RPM_ERROR,   // 0x21 — 2 octets
};
static const uint8_t LIVE_CYCLE_LEN = sizeof(LIVE_CYCLE_PAGE2);

// ── Décodeurs ─────────────────────────────────────────────────

/**
 * RPM — Local ID 0x09 — 2 octets
 * Formule : int16 direct en RPM
 * Validé : 0x0000 = 0 rpm (moteur arrêté) ✓
 */
inline int decode_rpm(const uint8_t* d, uint8_t len) {
    if (len < 2) return -1;
    return (int16_t)((d[0] << 8) | d[1]);
}

/**
 * Vitesse — Local ID 0x0D — 1 octet
 * Formule : uint8 direct en km/h
 * Validé : 0x00 = 0 km/h ✓
 */
inline uint8_t decode_speed(const uint8_t* d, uint8_t len) {
    if (len < 1) return 0;
    return d[0];
}

/**
 * Batterie — Local ID 0x10 — 4 octets (2 mesures)
 * Formule : int16 / 1000 = Volts
 * Validé : 0x36C6 = 14022/1000 = 14.022V ✓
 *          0x36D8 = 14040/1000 = 14.040V ✓
 */
inline float decode_battery(const uint8_t* d, uint8_t idx = 0) {
    uint16_t raw = ((uint16_t)d[idx * 2] << 8) | d[idx * 2 + 1];
    return raw / 1000.0f;
}

/**
 * Température — int16 / 100 = °C
 * SENSOR_NOT_FITTED (0x1388) → ne pas envoyer (capteur absent)
 * Validé :
 *   0x0DFE = 3582/100 = 35.82°C (refroidissement) ✓
 *   0x1388 = capteur absent (tension ref 5V) ✓
 *   0x0F5C = 3932/100 = 39.32°C (admission) ✓
 */
inline bool decode_temp(const uint8_t* d, uint8_t idx, float& out) {
    uint16_t raw = ((uint16_t)d[idx * 2] << 8) | d[idx * 2 + 1];
    if (raw == SENSOR_NOT_FITTED) return false;  // capteur absent
    out = raw / 100.0f;
    return true;
}

/**
 * Papillon — Local ID 0x1B — 8 octets (4 pistes)
 * Formule : int16 / 1000 = Volts
 * Validé :
 *   0x0000 = 0.000V (piste demande, repos) ✓
 *   0x1388 = 5.000V (référence 5V) ✓
 *   0x1382 = 4.994V (référence 5V légèrement chargée) ✓
 */
inline float decode_throttle_track(const uint8_t* d, uint8_t idx) {
    uint16_t raw = ((uint16_t)d[idx * 2] << 8) | d[idx * 2 + 1];
    return raw / 1000.0f;
}

/**
 * Pression — int16 × 0.1 = mbar
 * Validé : 0x2710 = 10000 × 0.1 = 1000.0 mbar (atmosphérique) ✓
 */
inline float decode_pressure_mbar(const uint8_t* d, uint8_t idx = 0) {
    uint16_t raw = ((uint16_t)d[idx * 2] << 8) | d[idx * 2 + 1];
    return raw * 0.1f;
}

/**
 * Power Balance — Local ID 0x40 — 10 octets (5 cylindres)
 * Formule : int16 signé par cylindre
 * 0 = cylindre contribue normalement
 * Négatif = cylindre en défaut (chute puissance)
 */
inline int16_t decode_power_balance(const uint8_t* d, uint8_t cyl) {
    return (int16_t)((d[cyl * 2] << 8) | d[cyl * 2 + 1]);
}

/**
 * Switches — Local ID 0x1E — 2 octets
 * Validé sur Inputs_Switches.log
 */
struct switches_t {
    bool transfer_ratio;   // A33 — byte1 bit0
    bool brake2;           // B10 — byte1 bit4
    bool brake1;           // B16 — byte1 bit6
    bool clutch;           // B35 — byte2 bit2
    bool cruise_master;    // B15 — byte2 bit3
    bool cruise_set;       // B11 — byte2 bit4
    bool cruise_resume;    // B17 — byte2 bit5
    bool ac_clutch_req;    // B9  — byte2 bit4 (overlap avec cruise_set!)
    bool ac_fan_req;       // B23 — byte2 bit5
};

inline switches_t decode_switches(const uint8_t* d) {
    switches_t s;
    s.transfer_ratio = (d[0] & 0x01) != 0;
    s.brake2         = (d[0] & 0x10) != 0;
    s.brake1         = (d[0] & 0x40) != 0;
    s.clutch         = (d[1] & 0x04) != 0;
    s.cruise_master  = (d[1] & 0x08) != 0;
    s.cruise_set     = (d[1] & 0x10) != 0;
    s.cruise_resume  = (d[1] & 0x20) != 0;
    s.ac_clutch_req  = (d[1] & 0x10) != 0;
    s.ac_fan_req     = (d[1] & 0x20) != 0;
    return s;
}

// ── Dispatcher — décode et envoie via USB ─────────────────────

/**
 * Décode la réponse KWP2000 d'un Local ID et envoie le JSON au PC.
 *
 * @param lid  Local ID demandé
 * @param resp Octets de données (après SID 0x61 et LID, sans CS)
 * @param len  Nombre d'octets de données
 */
void dispatch_live_data(uint8_t lid, const uint8_t* resp, uint8_t len);
