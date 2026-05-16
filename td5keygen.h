#pragma once
// ═══════════════════════════════════════════════════════════════
// DiagRover — td5keygen.h
// Algorithme Seed-Key ECU TD5 Storm
// Source : paul@discotd5.com (BSD 2-Clause) + EA2EGA
// Validé sur 5 paires réelles (sniffings Ekaitza_Itzali)
// ═══════════════════════════════════════════════════════════════
#include <stdint.h>

/**
 * Calcule la clé KWP2000 SecurityAccess pour l'ECU TD5 Storm.
 *
 * Algorithme LFSR 16 bits modifié :
 *   count = (bit15×8 + bit7×4 + bit4×2 + bit0×1) + 1   [1–16 itérations]
 *   tap   = bit1 ^ bit2 ^ bit8 ^ bit9
 *   tmp   = (seed >> 1) | (tap << 15)
 *   bit0  = 0 si (bit3 && bit13), sinon 1
 *
 * Vecteurs validés :
 *   0x173F → 0xC173  (Settings.txt,         count=4)
 *   0x0439 → 0x4043  (Read_Faults.log,       count=4)
 *   0x71D4 → 0xACE3  (Outputs.log,           count=7)
 *   0x8C08 → 0xE647  (Inputs_Switches.log,   count=9)
 *   0x34A5 → 0x54D3  (README demo,           count=6)
 *
 * @param seed  16 bits big-endian : (seed_H << 8) | seed_L
 * @return      Clé 16 bits : key_H = ret >> 8, key_L = ret & 0xFF
 * @timing      < 5µs sur nRF52840 @ 64MHz
 */
inline uint16_t td5_keygen(uint16_t seed) {
    uint8_t count = ((seed >> 12 & 0x8) | (seed >> 5 & 0x4) |
                     (seed >> 3  & 0x2) | (seed & 0x1)) + 1;

    for (uint8_t i = 0; i < count; i++) {
        uint8_t  tap = ((seed >> 1) ^ (seed >> 2) ^
                        (seed >> 8) ^ (seed >> 9)) & 1;
        uint16_t tmp = (seed >> 1) | ((uint16_t)tap << 15);
        seed = ((seed >> 3 & 1) && (seed >> 13 & 1))
                 ? (tmp & (uint16_t)~1)   // forcer bit0 = 0
                 : (tmp | 1);             // forcer bit0 = 1
    }
    return seed;
}

/**
 * Construit la trame KWP2000 SecurityAccess SendKey complète (6 octets).
 *
 * Format : 04 27 02 [KH] [KL] [CS]
 * Validé sur Outputs.log : seed=0x71D4 → 04 27 02 AC E3 BC ✓
 *
 * @param seed_h  4e octet de la réponse ECU 0x67 01 [SH] [SL]
 * @param seed_l  5e octet
 * @param frame   Buffer de sortie (6 octets minimum)
 * @return        Toujours 6
 */
inline uint8_t td5_key_frame(uint8_t seed_h, uint8_t seed_l, uint8_t* frame) {
    uint16_t key = td5_keygen(((uint16_t)seed_h << 8) | seed_l);
    frame[0] = 0x04;
    frame[1] = 0x27;
    frame[2] = 0x02;
    frame[3] = (uint8_t)(key >> 8);
    frame[4] = (uint8_t)(key & 0xFF);
    uint8_t cs = 0;
    for (int i = 0; i < 5; i++) cs += frame[i];
    frame[5] = cs;
    return 6;
}
