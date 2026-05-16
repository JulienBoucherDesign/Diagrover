# DiagRover — TD5 Keygen
### Algorithme d'authentification Seed-Key · ECU Land Rover TD5 Storm
### Source : pajacobson/td5keygen · Licence BSD 2-Clause

---

## Contexte

L'ECU TD5 Storm exige une **authentification challenge-response** (Seed-Key) avant d'autoriser l'accès au mode diagnostic fabricant Land Rover (session KWP2000 mode `0xA0`). Sans cette authentification, seul l'OBD-II standard est accessible (RPM, vitesse, température basique).

L'algorithme est issu du **disassembly du firmware ECU NNN/MSB** par OffTrack (paul@discotd5.com), porté en C et Python par pajacobson et EA2EGA (Ekaitza_Itzali).

---

## Protocole KWP2000 Security Access (ISO 14230, SID 0x27)

### Séquence complète dans les échanges réels

```
Diag → ECU : 02 27 01 2A           ← RequestSeed (SID=0x27, subFn=0x01)
ECU  → Diag : 04 67 01 [SH] [SL] [CS] ← Seed (2 octets, big-endian)

    seed_16bit = (SH << 8) | SL
    key_16bit  = td5_keygen(seed_16bit)
    KH = key_16bit >> 8
    KL = key_16bit & 0xFF

Diag → ECU : 04 27 02 [KH] [KL] [CS] ← SendKey (subFn=0x02)
ECU  → Diag : 02 67 02 6B            ← AUTH OK (si clé correcte)
```

### Paires seed→key validées (5 sniffings + README demo)

| Source | Seed (hex) | Seed (bytes) | Key (hex) | Key (bytes) | count |
|---|---|---|---|---|---|
| Settings.txt | `0x173F` | 17 3F | `0xC173` | C1 73 | 4 |
| Read_Faults.log | `0x0439` | 04 39 | `0x4043` | 40 43 | 4 |
| Outputs.log | `0x71D4` | 71 D4 | `0xACE3` | AC E3 | 7 |
| Inputs_Switches.log | `0x8C08` | 8C 08 | `0xE647` | E6 47 | 9 |
| README demo | `0x34A5` | 34 A5 | `0x54D3` | 54 D3 | 6 |

Toutes validées par le port Python 3 ci-dessous.

---

## Analyse de l'algorithme

### Vue d'ensemble

L'algorithme est un **LFSR (Linear Feedback Shift Register) à 16 bits** modifié, avec :
- Taps (feedback) aux positions 1, 2, 8, 9
- Décalage vers la droite
- Bit 0 déterminé par une condition non-linéaire sur bits 3 et 13
- Nombre d'itérations variable (1 à 16) selon 4 bits du seed

### Étape 1 — Calcul du nombre d'itérations (count)

```
count = (bit15_seed × 8) + (bit7_seed × 4) + (bit4_seed × 2) + (bit0_seed × 1) + 1
```

Implémentation C :
```c
count = ((seed >> 0xC & 0x8) | (seed >> 0x5 & 0x4) |
         (seed >> 0x3 & 0x2) | (seed & 0x1)) + 1;
```

- `seed >> 12 & 8` : bit 15 du seed, pondéré ×8 (valeur 0 ou 8)
- `seed >> 5 & 4` : bit 7 du seed, pondéré ×4 (valeur 0 ou 4)
- `seed >> 3 & 2` : bit 4 du seed, pondéré ×2 (valeur 0 ou 2)
- `seed & 1` : bit 0 du seed, pondéré ×1 (valeur 0 ou 1)
- `+ 1` : au moins 1 itération

**Count minimal = 1** (tous les 4 bits à 0), **maximal = 16** (tous à 1).

Distribution uniforme : chaque valeur de count de 1 à 16 couvre exactement 4096 seeds (6.25% des 65536 seeds possibles).

### Étape 2 — Itérations LFSR (répétées count fois)

Chaque itération :

```
1. tap = (bit1 XOR bit2 XOR bit8 XOR bit9) du seed courant

2. tmp = seed >> 1             ← décalage droit 1 bit
         | (tap << 15)          ← tap injecté en bit 15

3. Si (bit3 = 1) ET (bit13 = 1) :
       seed = tmp & ~1           ← forcer bit0 à 0
   Sinon :
       seed = tmp | 1            ← forcer bit0 à 1
```

**Tap (feedback LFSR) :** les positions 1, 2, 8, 9 forment le polynôme de feedback XOR. Cette combinaison est issue du disassembly du firmware ECU.

**Condition non-linéaire :** le bit 0 du résultat n'est PAS le tap, mais est fixé à 0 ou 1 selon l'état des bits 3 et 13. C'est ce qui rend l'algorithme non-standard et propriétaire.

### Trace manuelle — seed = 0x173F → key = 0xC173

```
seed = 0x173F = 0001 0111 0011 1111
count = (0×8)+(0×4)+(1×2)+(1×1)+1 = 4

Itération 1 : seed = 0x173F
  tap = bit1^bit2^bit8^bit9 = 1^1^1^1 = 0
  tmp = 0x0B9F | 0 = 0x0B9F
  bit3=1, bit13=0 → FALSE → seed = 0x0B9F | 1 = 0x0B9F

Itération 2 : seed = 0x0B9F
  tap = 1^1^1^1 = 0
  tmp = 0x05CF
  bit3=1, bit13=0 → FALSE → seed = 0x05CF | 1 = 0x05CF

Itération 3 : seed = 0x05CF
  tap = 1^1^1^0 = 1
  tmp = 0x02E7 | 0x8000 = 0x82E7
  bit3=1, bit13=0 → FALSE → seed = 0x82E7 | 1 = 0x82E7

Itération 4 : seed = 0x82E7
  tap = 1^1^0^1 = 1
  tmp = 0x4173 | 0x8000 = 0xC173
  bit3=0 → FALSE → seed = 0xC173 | 1 = 0xC173

Résultat : key = 0xC173 ✓
```

---

## Implémentations

### Python 3 (PC — module DiagRover)

```python
# diagrover/core/td5keygen.py
# BSD 2-Clause — paul@discotd5.com / EA2EGA
# Port Python 3 depuis keytool.py (Python 2) et keygen.c

def td5_keygen(seed: int) -> int:
    """
    Calcule la clé d'authentification pour un seed ECU TD5.
    
    Args:
        seed: entier 16 bits (0x0000 à 0xFFFF), big-endian
              construit depuis les octets ECU : (seed_H << 8) | seed_L
    
    Returns:
        clé 16 bits à transmettre à l'ECU (big-endian)
        key_H = result >> 8
        key_L = result & 0xFF
    
    Validé sur 5 paires seed/key réelles (sniffings Ekaitza_Itzali + README)
    """
    seed = seed & 0xFFFF  # garantir 16 bits

    count = ((seed >> 0xC & 0x8) + (seed >> 0x5 & 0x4) +
             (seed >> 0x3 & 0x2) + (seed & 0x1)) + 1

    for _ in range(count):
        tap = ((seed >> 1) ^ (seed >> 2) ^ (seed >> 8) ^ (seed >> 9)) & 1
        tmp = (seed >> 1) | (tap << 0xF)
        if (seed >> 0x3 & 1) and (seed >> 0xD & 1):
            seed = tmp & ~1  # forcer bit0 à 0
        else:
            seed = tmp | 1   # forcer bit0 à 1

    return seed & 0xFFFF


def td5_keygen_from_frame(seed_h: int, seed_l: int) -> tuple[int, int]:
    """
    Wrapper direct depuis les octets de la trame KWP2000 ECU.

    Exemple :
        trame ECU : 04 67 01 17 3F C2
        → seed_h=0x17, seed_l=0x3F
        → td5_keygen_from_frame(0x17, 0x3F) → (0xC1, 0x73)

    Returns:
        (key_h, key_l) : les 2 octets à envoyer dans la trame SecurityAccess
    """
    seed = (seed_h << 8) | seed_l
    key = td5_keygen(seed)
    return key >> 8, key & 0xFF


def build_key_frame(seed_h: int, seed_l: int) -> bytes:
    """
    Construit la trame KWP2000 SecurityAccess complète prête à envoyer.

    Exemple :
        build_key_frame(0x17, 0x3F) → b'\\x04\\x27\\x02\\xC1\\x73\\x61'
    """
    kh, kl = td5_keygen_from_frame(seed_h, seed_l)
    payload = bytes([0x04, 0x27, 0x02, kh, kl])
    cs = sum(payload) & 0xFF
    return payload + bytes([cs])


# ─── Tests intégrés ────────────────────────────────────────────────────────
if __name__ == "__main__":
    TEST_VECTORS = [
        (0x173F, 0xC173, "Settings.txt"),
        (0x0439, 0x4043, "Read_Faults.log"),
        (0x71D4, 0xACE3, "Outputs.log"),
        (0x8C08, 0xE647, "Inputs_Switches.log"),
        (0x34A5, 0x54D3, "README demo"),
    ]
    print("=== td5keygen validation ===")
    all_ok = True
    for seed, expected, src in TEST_VECTORS:
        result = td5_keygen(seed)
        ok = result == expected
        if not ok:
            all_ok = False
        print(f"  seed=0x{seed:04X} → 0x{result:04X} {'✓' if ok else f'✗ expected 0x{expected:04X}'} [{src}]")
    print("PASS" if all_ok else "FAIL")
```

### C++ Arduino (Firmware Nano 33 BLE)

```cpp
// diagrover_nano/td5keygen.h
// BSD 2-Clause — paul@discotd5.com
// Port C++ Arduino depuis keygen.c

#pragma once
#include <stdint.h>

/**
 * Calcule la clé KWP2000 SecurityAccess pour l'ECU TD5 Storm.
 *
 * @param seed  Seed 16 bits reçu de l'ECU (big-endian : seed_H << 8 | seed_L)
 * @return      Clé 16 bits à transmettre (key_H = ret >> 8, key_L = ret & 0xFF)
 *
 * Validé sur 5 vecteurs de test, compatible nRF52840 (Nano 33 BLE).
 * Cycle count typique : ~300 cycles CPU à 64MHz = < 5µs
 */
inline uint16_t td5_keygen(uint16_t seed) {
    uint8_t count = ((seed >> 12 & 0x8) | (seed >> 5 & 0x4) |
                     (seed >> 3 & 0x2) | (seed & 0x1)) + 1;

    for (uint8_t i = 0; i < count; i++) {
        uint8_t tap = ((seed >> 1) ^ (seed >> 2) ^
                       (seed >> 8) ^ (seed >> 9)) & 1;
        uint16_t tmp = (seed >> 1) | ((uint16_t)tap << 15);

        seed = ((seed >> 3 & 1) && (seed >> 13 & 1))
                 ? (tmp & ~1)    // forcer bit0 à 0
                 : (tmp | 1);    // forcer bit0 à 1
    }
    return seed;
}

/**
 * Construit la trame KWP2000 SecurityAccess complète.
 *
 * @param seed_h  Octet high du seed (4e octet de la réponse ECU 0x67)
 * @param seed_l  Octet low  du seed (5e octet de la réponse ECU 0x67)
 * @param frame   Buffer de sortie (minimum 6 octets)
 * @return        Longueur de la trame (toujours 6)
 */
inline uint8_t td5_key_frame(uint8_t seed_h, uint8_t seed_l, uint8_t* frame) {
    uint16_t key = td5_keygen((uint16_t)(seed_h << 8) | seed_l);
    frame[0] = 0x04;               // LEN
    frame[1] = 0x27;               // SID SecurityAccess
    frame[2] = 0x02;               // SendKey
    frame[3] = key >> 8;           // key high
    frame[4] = key & 0xFF;         // key low
    // checksum
    uint8_t cs = 0;
    for (int i = 0; i < 5; i++) cs += frame[i];
    frame[5] = cs & 0xFF;
    return 6;
}
```

### Version C originale (keygen.c — référence)

```c
/* keygen.c — paul@discotd5.com — BSD 2-Clause */
#include "keygen.h"

void keyGenerate(keyBytes_t * key) {
    uint16_t seed = key->keyword;
    uint8_t  count = ((seed >> 0xC & 0x8) | (seed >> 0x5 & 0x4) |
                      (seed >> 0x3 & 0x2) | (seed & 0x1)) + 1;
    for (uint8_t idx = 0; idx < count; idx++) {
        uint8_t  tap = ((seed >> 1) ^ (seed >> 2) ^
                        (seed >> 8) ^ (seed >> 9)) & 1;
        uint16_t tmp = (seed >> 1) | ((uint16_t)tap << 0xF);
        seed = ((seed >> 0x3 & 1) && (seed >> 0xD & 1))
                 ? (tmp & ~1)
                 : (tmp | 1);
    }
    key->keyword = seed;
}
```

### Version C bitfield (keygen_bitfield.c — plus rapide sur PIC32)

Utilise les union C bitfield pour éliminer les masques/décalages. **295 cycles CPU** contre 328 pour keygen.c sur PIC32MX795F512.

```c
void keyGenerate(keyBytes_t * key) {
    typedef union {
        uint16_t all;
        struct { uint16_t bit00:1, bit01:1, bit02:1, bit03:1,
                          bit04:1, bit05:1, bit06:1, bit07:1,
                          bit08:1, bit09:1, bit10:1, bit11:1,
                          bit12:1, bit13:1, bit14:1, bit15:1; };
    } seedbits_t;

    seedbits_t seed = { .all = key->keyword }, tmp;
    uint8_t count = (seed.bit15*8) + (seed.bit07*4) +
                    (seed.bit04*2) + (seed.bit00) + 1;

    for (uint8_t idx = 0; idx < count; idx++) {
        uint8_t tap = seed.bit01 ^ seed.bit02 ^
                       seed.bit08 ^ seed.bit09;
        tmp.all     = seed.all >> 1;
        tmp.bit15   = tap;
        tmp.bit00   = (seed.bit03 && seed.bit13) ? 0 : 1;
        seed.all    = tmp.all;
    }
    key->keyword = seed.all;
}
```

> **Note portabilité :** la version bitfield dépend du compilateur et de l'endianness (bits fields C non portable entre architectures). À éviter sur le nRF52840. Utiliser la version keygen.c ou le port C++ inline ci-dessus.

---

## Intégration DiagRover — Séquence complète

### Firmware Nano 33 BLE (C++ Arduino)

```cpp
// Dans stn_driver.cpp — après START_DIAG_SESSION réussie

bool STNDriver::authenticate() {
    // 1. Request seed
    uint8_t seed_req[] = {0x02, 0x27, 0x01, 0x2A};
    stpx_send(seed_req, 4);

    // 2. Parser la réponse seed
    uint8_t response[16];
    if (!stpx_recv(response, sizeof(response))) return false;
    // réponse format : 04 67 01 [SH] [SL] [CS]
    uint8_t seed_h = response[3];
    uint8_t seed_l = response[4];

    // 3. Calculer la clé
    uint8_t key_frame[6];
    td5_key_frame(seed_h, seed_l, key_frame);

    // 4. Envoyer la clé
    stpx_send(key_frame, 6);

    // 5. Vérifier AUTH OK : 02 67 02 6B
    if (!stpx_recv(response, sizeof(response))) return false;
    return (response[1] == 0x67 && response[2] == 0x02);
}
```

### Logiciel PC Python (module core)

```python
# Dans diagrover/core/session.py

from .td5keygen import td5_keygen_from_frame, build_key_frame
from .kwp2000 import KWP2000

class TD5Session:
    def authenticate(self) -> bool:
        # 1. Envoyer RequestSeed
        self.send(KWP2000.build(0x27, 0x01))  # 02 27 01 2A

        # 2. Recevoir seed
        resp = self.recv(timeout_ms=500)
        if resp['sid'] != 0x67:
            return False
        seed_h, seed_l = resp['data'][1], resp['data'][2]

        # 3. Calculer et envoyer la clé
        key_frame = build_key_frame(seed_h, seed_l)
        self.send(key_frame)

        # 4. Vérifier AUTH OK
        resp = self.recv(timeout_ms=500)
        return resp['sid'] == 0x67 and resp['data'][0] == 0x02
```

---

## Propriétés de l'algorithme

### Distribution du count

L'algorithme effectue entre 1 et 16 itérations LFSR selon les bits 0, 4, 7, 15 du seed :

| Count | Seeds | Proportion |
|---|---|---|
| 1 | 4096 | 6.25% |
| 2 | 4096 | 6.25% |
| ... | ... | ... |
| 16 | 4096 | 6.25% |

Distribution parfaitement uniforme — chaque valeur de count est équiprobable.

### Complexité

| Métrique | Valeur |
|---|---|
| Entrée | Seed 16 bits (0x0000–0xFFFF) |
| Sortie | Key 16 bits (1:1 mapping) |
| Itérations | 1 à 16 (moyenne : 8.5) |
| Cycles CPU (PIC32, keygen.c) | 328 avec seed=0x8091 |
| Cycles CPU (PIC32, bitfield) | 295 avec seed=0x8091 |
| Cycles CPU (nRF52840 64MHz) | ~200 (estimé) |
| Temps (nRF52840 64MHz) | < 5µs |

### Caractéristiques cryptographiques

L'algorithme est **propriétaire mais pas cryptographiquement sûr** au sens moderne. Il s'agit d'un LFSR modifié de type « security by obscurity » :

- Le seed est visible sur le bus K-Line (pas de confidentialité)
- La clé se calcule en < 5µs sur n'importe quel microcontrôleur
- Le paramètre clé (seed → key) peut être pré-calculé pour les 65536 seeds possibles (table 128 Ko)
- Aucune protection contre le replay

Son objectif est d'empêcher l'accès au mode diagnostic fabricant par des outils génériques ELM327, pas de protéger contre un adversaire déterminé.

---

## Cas limites

| Seed | Key | Count | Note |
|---|---|---|---|
| `0x0000` | `0x0001` | 1 | Seed nul → 1 itération |
| `0xFFFF` | `0x8081` | 16 | Seed maximum → 16 itérations |
| `0x0001` | `0x0001` | 2 | — |
| `0x9191` | `0xA3F5` | 16 | bits 15+7+4+0 tous à 1 |

---

## Fichiers du projet (pajacobson/td5keygen)

| Fichier | Rôle |
|---|---|
| `keygen.c` | Implémentation C portable (référence) |
| `keygen.h` | Header avec typedef `keyBytes_t` |
| `keygen_bitfield.c` | Implémentation C bitfield (rapide, peu portable) |
| `demo.c` | Usage en ligne de commande (`gcc demo.c keygen.c -o demo`) |
| `table_generator.c` | Génère la table complète seed→key (65536 paires) |
| `keytool.py` | Outil Python 2 en ligne de commande |
| `README.md` | Documentation protocole + byte ordering |

---

## Notes de licence

Tout le code ci-dessus est dérivé de travaux sous **BSD 2-Clause License** :
- `paul@discotd5.com` (algorithme C original, reverse engineering firmware ECU)
- `xabiergarmendia@gmail.com` / EA2EGA (port Python, table_generator.c)

Toute redistribution (modification incluse) doit conserver la notice de copyright BSD 2-Clause.

