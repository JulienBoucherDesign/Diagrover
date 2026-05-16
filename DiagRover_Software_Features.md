# DiagRover — Fonctionnalités
### Cahier des charges v3 · Mis à jour avec sniffings Ekaitza_Itzali réels
### Land Rover Discovery 2 / Range Rover · ECU TD5 Storm

---

## Vue d'ensemble du protocole

Le mode diagnostic fabricant Land Rover utilise KWP2000 (ISO 14230) avec une **authentification Seed-Key propriétaire**. Les sniffings de Ekaitza_Itzali révèlent la séquence exacte, tous les service IDs, et les Local IDs de tous les paramètres.

```
Mode OBD-II standard (sans auth)    Mode fabricant LR (après Seed-Key)
  SID 0x01 : RPM, Speed, etc.          SID 0x21 : Tous paramètres TD5
  SID 0x03 : DTC standard               SID 0x1A : VIN, ECU type
  → limité, pas de fuelling             SID 0x30 : Actuations outputs
                                         SID 0x31 : Routines (injecteurs, clear)
                                         SID 0x27 : Seed-Key auth
```

---

## Module 0 — Protocole KWP2000 (couche transport)

### Structure des trames (validée sur sniffings réels, 6 fichiers, tous CS corrects)

```
[LEN][SID][DATA...][CS]
LEN = nombre d'octets (SID+DATA)
CS  = somme de tous les octets modulo 256
```

Exemples réels extraits des logs :
```
0210a0b2   len=2 SID=0x10 StartDiagSession(0xA0)   CS=0xB2 ✓
0227012a   len=2 SID=0x27 SecurityAccess(seed_req) CS=0x2A ✓
02211c3f   len=2 SID=0x21 ReadDataLocalID(0x1C)    CS=0x3F ✓
023e0141   len=2 SID=0x3E TesterPresent(0x01)       CS=0x41 ✓
0330a3ffd5 len=3 SID=0x30 IOControl(0xA3,0xFF)      CS=0xD5 ✓
```

### Séquence init complète (avec header 3 octets)

```
00                  → pause ~300ms avant init
8113f7810c          → StartComm FMT=0x81 TGT=0x13 SRC=0xF7 SID=0x81
03c1578faa          → StartComm resp KW1=0x57 KW2=0x8F
0210a0b2            → StartDiagSession(0xA0) = mode fabricant LR
015051              → Session OK
0227012a            → SecurityAccess: RequestSeed
046701[SL][SH][CS]  → Seed (2 octets aléatoires par session)
042702[KH][KL][CS]  → SendKey = td5keygen(seed_H<<8|seed_L)
0267026b            → AUTH OK ← session fabricant ouverte
```

### Paires Seed→Key observées dans les 4 sessions

| Seed | Key | Source |
|---|---|---|
| 0x173F | 0xC173 | Settings.txt |
| 0x0439 | 0x4043 | Read_Faults.log |
| 0x71D4 | 0xACE3 | Outputs.log |
| 0x8C08 | 0xE647 | Inputs_Switches.log |

### Keep-alive (validé dans tous les logs)

```
023e0141  → TesterPresent(0x01)   CS=0x41 ✓
017e7f    → TesterPresent_RESP    CS=0x7F ✓
```
Envoyé toutes les **2500ms**. Sans ça, la session KWP2000 se ferme après 5s de silence.
Le timer est géré dans le firmware Nano : `if (millis() - last_cmd_ms > 2500) sendAT("3E");`

---

## Module 1 — Identification véhicule

### VIN et infos ECU — SID 0x1A (ReadECUID)

| Commande | Param | Données | Décodage |
|---|---|---|---|
| `021a87a3` | 0x87 | 48 octets | VIN + infos système |
| `021a9ab6` | 0x9A | 8 octets | Type ECU (ASCII : "NNN" ou "MSB") |
| `021a9bb7` | 0x9B | 3 octets | Sous-version |
| `021a9cb8` | 0x9C | 3 octets | Révision |

Exemple réel (Settings.txt) :
```
021a87 → VIN: SALLTGM844A + données système
021a9a → ECU type: 4E 4E 4E = "NNN" (ASCII) → ECU NNN P030
```

### Variante map / carburant — SID 0x21

| Local ID | Description | Taille |
|---|---|---|
| `0x0E` | Map Variant ID (ASCII 16 chars) | 16 octets |
| `0x32` | Map Variant + Fuel Variant + Homologation | 24 octets |
| `0x24` | Accelerator Type (0x01=2-Way 0x02=3-Way) | 1 octet |

Exemple réel :
```
0x9A → "NNN" + variante
0x0E → "sswwttnnpp000066" (map variant courant)
0x32 → "swtnp006" + "swdxe007" + "4190    " (map+fuel+homol)
0x24 → 0x01 = 2-Way throttle
```

---

## Module 2 — Codes défauts (DTC)

### Lecture — Local ID 0x3B

Commande : `02213b5e` → réponse 37 octets = 35 octets de bits de défauts

Exemple réel (Read_Faults.log) :
```
Response: 25 61 3B | C0 C0 00 07 80 87 00 00 70 1D 00 00 00 FF 00 CF
                     00 8F 00 00 38 01 00 80 00 28 00 00 00 00 00 00
                     00 00 00 | 1A
35 octets = 280 bits = 280 codes défauts potentiels
Bits actifs = défauts présents (table à construire depuis Technical Academy LR)
```

### Effacement — SID 0x31, routine 0xDD

Commande : `14 31 DD` + 17 × `0x00` + CS
```
1431dd00000000000000000000000000000000000022 → clear faults
0271dd50                                      → positive response ✓
```

---

## Module 3 — Live Data (mode fabricant)

### Cycle complet Page 2 — validé sur Instruments_Page2.log

| Local ID | Paramètre | Taille | Décodage |
|---|---|---|---|
| `0x40` | Power Balance (5 cyl.) | 10 octets | 5 × int16 : écart injection |
| `0x23` | Pression ambiante | 4 octets | int16 × 0.1 mbar |
| `0x37` | EGR Modulation | 2 octets | int16 |
| `0x38` | EGR Inlet | 2 octets | int16 |
| `0x10` | Tension batterie | 4 octets | 2 × int16 / 1000 = Volts |
| `0x09` | Régime moteur | 2 octets | int16 = RPM direct |
| `0x0D` | Vitesse véhicule | 1 octet | uint8 = km/h direct |
| `0x1A` | 8 températures | 16 octets | 8 × int16 / 100 = °C |
| `0x1B` | Papillon (4 pistes) | 8 octets | 4 × int16 / 1000 = Volts |
| `0x1C` | Pressions (4) | 8 octets | int16 × 0.1 mbar |
| `0x21` | Erreur RPM | 2 octets | int16 signé |

### Valeurs réelles décodées (moteur arrêté, contact mis)

```python
Batterie     : V1=14.022V V2=14.040V  # 0x36C6/1000 et 0x36D8/1000
RPM          : 0 rpm                   # 0x0000
Vitesse      : 0 km/h                  # 0x00
Temps[0]     : 35.82°C                 # 0x0DFE/100 = Coolant
Temps[1]     : 50.00°C                 # 0x1388 → None (capteur absent)
Temps[2]     : 39.32°C                 # 0x0F5C/100 = Air inlet
Papillon T2  : 5.000V                  # 0x1388/1000 = référence 5V
Papillon T4  : 4.994V                  # 0x1382/1000 = référence 5V
MAP          : 1000.0 mbar             # 0x2710 × 0.1 = atmosphérique ✓
```

### Périmètre du mode fabricant

Le cycle live data ci-dessus couvre l'**ECU TD5 Storm uniquement** (SID 0x21 en mode fabricant LR).

Pour le moteur **GEMS V8**, les PIDs sont accessibles en OBD-II standard (SID 0x01) — pas de session fabricant requise. Paramètres principaux : RPM (010C), vitesse (010D), températures (0105/010F), Lambda/O2 (0136/0138/013B/013C), avance allumage (010E), trim carburant (0106/0107).

Pour la **suspension SLS** (CAN 0x730) et l'**ABS** (CAN 0x7A8), les PIDs sont accessibles via ATSP6 + adresse CAN respective. À documenter en Phase 2.

### Règle critique : valeur 0x1388

La valeur `0x1388 = 5000` apparaît sur les capteurs non connectés ou absents.
C'est la tension de référence 5V convertie (5000 mV).

```python
def decode_temp(raw: int) -> float | None:
    if raw == 0x1388:   # capteur non câblé
        return None
    return raw / 100.0  # en °C
```

---

## Module 4 — Actuations (SID 0x30 IOControlByLocalID)

### Structure : `03 30 [LID] [VAL] [CS]`

Validés sur Outputs.log — tous les checksums vérifiés :

| Local ID | Actionneur | Frame ON | Frame OFF |
|---|---|---|---|
| `0xA1` | Pompe carburant | `0330a1ffd3` | `0330a10003` |
| `0xA2` | Témoin MIL | `0330a2ffd4` | `0330a20004` |
| `0xA3` | Compresseur AC | `0330a3ffd5` | `0330a30005` |
| `0xA4` | Ventilateur AC | `0330a4ffd6` | `0330a40006` |
| `0xB3` | Bougies préchauffage | `0330b3ffe5` | `0330b30015` |
| `0xB7` | Compteur tours | `0330b7ffe9` | `0330b70019` |
| `0xBA` | Jauge température | `0330baffec` | `0330ba001c` |

### Actuations 7 octets (paramètres supplémentaires)

```
0730beff000a138899  → Wastegate Modulator (duty=10000, ref=5000)
0730bdff00fa138888  → EGR Inlet Modulator (duty=250, ref=5000)
```

---

## Module 5 — Test injecteurs (SID 0x31 StartRoutine)

### Structure : `03 31 C2 [N] [CS]`

Validés sur Outputs.log :

| Frame | Injecteur | CS |
|---|---|---|
| `0331c201f7` | Injecteur 1 | 0xF7 ✓ |
| `0331c202f8` | Injecteur 2 | 0xF8 ✓ |
| `0331c203f9` | Injecteur 3 | 0xF9 ✓ |
| `0331c204fa` | Injecteur 4 | 0xFA ✓ |
| `0331c205fb` | Injecteur 5 | 0xFB ✓ |

Réponse identique pour tous : `0271c235` ✓

Mécanisme : l'ECU coupe momentanément l'injecteur et mesure la chute de RPM.
Lire 0x40 (Power Balance) avant et après pour quantifier la contribution.

---

## Module 6 — Entrées / Switches (Local ID 0x1E)

### 2 octets = 16 switches (validé Inputs_Switches.log)

```python
switches = {
    'TransferRatio' : byte1 & 0x01,   # Pin A33
    'Brake2'        : byte1 & 0x10,   # Pin B10
    'Brake1'        : byte1 & 0x40,   # Pin B16
    'ClutchSwitch'  : byte2 & 0x04,   # Pin B35
    'CruiseMaster'  : byte2 & 0x08,   # Pin B15
    'CruiseSet'     : byte2 & 0x10,   # Pin B11
    'CruiseResume'  : byte2 & 0x20,   # Pin B17
    'ACClutchREQ'   : byte2 & 0x10,   # Pin B9
    'ACFanREQ'      : byte2 & 0x20,   # Pin B23
}
```

Exemple réel : `04 61 1E 01 E0` → TransferRatio=ON, ACFanREQ=ON

Local ID `0x36` = données boîte automatique (0x0000 sur boîte manuelle).

---

## Module 7 — Settings (lecture et écriture)

### Lecture settings — Local ID 0x3D

```
02213d60 → 14613d [16 bytes données tune] CS
           f6 00 fa ec f4 00 0c fe 1e fc fe 00 00 00 00 00
```

### Écriture type accélérateur (3 étapes obligatoires dans l'ordre)

```
Étape 1 : 14 31 DF [16 bytes settings courants] CS  → StartRoutine 0xDF
Étape 2 : 0A 31 D5 [8 bytes "SE007   "] CS          → StartRoutine 0xD5
Étape 3a: 03 30 C1 F0 E4                            → IOControl 0xC1 val=0xF0 (2-Way)
       OU 03 30 C1 FF F3                            → IOControl 0xC1 val=0xFF (3-Way)
```

### Codage BCU (ZCS — Zone Coding System)

Le BCU stocke les options véhicule dans le ZCS. Nécessaire lors de :
- SLS delete (supprimer l'option suspension pneumatique)
- ACE delete (supprimer l'option Active Cornering Enhancement)
- Remplacement d'un BCU neuf
- Clonage de configuration BCU

Protocole : `ATSP6` (CAN BCU 0x760) ou `ATSP5` K-Line (MY98-01).
Les commandes ZCS utilisent SID 0x2E (WriteDataByLocalID) avec les paramètres BCU propriétaires LR.

---

## Module 8 — Lecture mémoire ECU (NNN only)

Service 0x23 (ReadMemoryByAddress) + adresse + longueur.
Disponible uniquement sur ECU NNN après auth. Permet le backup firmware avant reflash.

---

## Premier code Python — couche protocole

```python
# diagrover/core/kwp2000.py
# Validé sur 6 sniffings Ekaitza_Itzali — tous CS corrects

class KWP2000:
    @staticmethod
    def checksum(data: bytes) -> int:
        return sum(data) & 0xFF

    @staticmethod
    def build(sid: int, *args) -> bytes:
        payload = bytes([sid, *args])
        frame   = bytes([len(payload)]) + payload
        return frame + bytes([KWP2000.checksum(frame)])

    @staticmethod
    def verify(raw: bytes) -> bool:
        if len(raw) < 2: return False
        return sum(raw[:-1]) & 0xFF == raw[-1]

    @staticmethod
    def decode(raw: bytes) -> dict:
        if not KWP2000.verify(raw):
            raise ValueError(f"Checksum invalide: {raw.hex()}")
        return {'len':raw[0], 'sid':raw[1], 'data':raw[2:raw[0]]}

# Frames validées sur sniffings réels
INIT_FRAME    = bytes.fromhex('8113f7810c')
START_DIAG_MF = KWP2000.build(0x10, 0xA0)    # 0210a0b2
SEED_REQUEST  = KWP2000.build(0x27, 0x01)     # 0227012a
TESTER_PRES   = KWP2000.build(0x3E, 0x01)     # 023e0141

# Live data cycle complet Page2 (Instruments_Page2.log)
LIVE_PIDS_PAGE2 = [0x40,0x23,0x37,0x38,0x10,
                   0x09,0x0D,0x1A,0x1B,0x1C,0x21]

def build_read(lid: int) -> bytes:
    return KWP2000.build(0x21, lid)      # SID=0x21 ReadDataLocalID

def build_actuation(lid: int, val: int=0xFF) -> bytes:
    return KWP2000.build(0x30, lid, val) # SID=0x30 IOControl

def build_injector_test(n: int) -> bytes:
    return KWP2000.build(0x31, 0xC2, n)  # n=1..5

def clear_faults() -> bytes:
    return KWP2000.build(0x31, 0xDD, *([0x00]*17))

# Décodage des valeurs (unités validées sur données réelles)
def decode_temp(raw: int) -> float | None:
    return None if raw == 0x1388 else raw / 100.0

def decode_battery(data: bytes) -> float:
    return ((data[0]<<8)|data[1]) / 1000.0  # 0x36C6 → 14.022V ✓

def decode_rpm(data: bytes) -> int:
    return (data[0]<<8)|data[1]             # direct en RPM

def decode_speed(data: bytes) -> int:
    return data[0]                           # direct en km/h

def decode_map_mbar(data: bytes) -> float:
    return ((data[0]<<8)|data[1]) * 0.1     # 0x2710 → 1000.0 mbar ✓

def decode_throttle_v(data: bytes) -> list[float]:
    return [((data[i]<<8)|data[i+1]) / 1000.0
            for i in range(0, len(data)-1, 2)]

def decode_temps_all(data: bytes) -> list[float|None]:
    return [decode_temp((data[i]<<8)|data[i+1])
            for i in range(0, len(data)-1, 2)]

def decode_switches(data: bytes) -> dict:
    b1, b2 = data[0], data[1]
    return {
        'TransferRatio': bool(b1 & 0x01),
        'Brake2':        bool(b1 & 0x10),
        'Brake1':        bool(b1 & 0x40),
        'ClutchSwitch':  bool(b2 & 0x04),
        'CruiseMaster':  bool(b2 & 0x08),
        'ACClutchREQ':   bool(b2 & 0x10),
        'ACFanREQ':      bool(b2 & 0x20),
    }
```

### Points de vigilance du code

**td5keygen manquant** — bloaquant pour la session fabricant. À porter depuis keygen.c (pajacobson/td5keygen).

**Fault decoder** — 35 octets → 280 bits. Table bits→codes LR à construire depuis la Technical Academy.

**Timeout sur réponse ECU** — ajouter `timeout_ms=2000` sur chaque appel. Adapter selon le mode (ATST20 live / ATST96 diag / ATSFF flash).

**0x1388 = capteur absent** — ne pas afficher 50.00°C, afficher "--" dans l'UI.

---

## Tableau complet Local IDs validés

| Local ID | SID | R/W | Paramètre | Taille données |
|---|---|---|---|---|
| `0x09` | 0x21 | R | RPM | 2 |
| `0x0D` | 0x21 | R | Vitesse km/h | 1 |
| `0x0E` | 0x21 | R | Map Variant ID | 16 |
| `0x10` | 0x21 | R | Tension batterie × 2 | 4 |
| `0x1A` | 0x21 | R | Températures × 8 | 16 |
| `0x1B` | 0x21 | R | Papillon × 4 pistes | 8 |
| `0x1C` | 0x21 | R | Pressions × 4 | 8 |
| `0x1E` | 0x21 | R | Switches d'entrée | 2 |
| `0x20` | 0x21 | R | Données sup. | 4 |
| `0x21` | 0x21 | R | Erreur RPM | 2 |
| `0x23` | 0x21 | R | Pression ambiante | 4 |
| `0x24` | 0x21 | R | Type accélérateur | 1 |
| `0x32` | 0x21 | R | Map+Fuel Variant | 24 |
| `0x36` | 0x21 | R | Boîte auto | 2 |
| `0x37` | 0x21 | R | Modulation EGR | 2 |
| `0x38` | 0x21 | R | EGR Inlet | 2 |
| `0x3B` | 0x21 | R | Faults bitfield | 35 |
| `0x3D` | 0x21 | R | Settings tuning | 16 |
| `0x40` | 0x21 | R | Power Balance × 5 | 10 |
| `0x87` | 0x1A | R | VIN + infos système | 48 |
| `0x9A` | 0x1A | R | ECU Type (NNN/MSB) | 6 |
| `0xA1` | 0x30 | W | Pompe carburant | — |
| `0xA2` | 0x30 | W | MIL Lamp | — |
| `0xA3` | 0x30 | W | Compresseur AC | — |
| `0xA4` | 0x30 | W | Ventilateur AC | — |
| `0xB3` | 0x30 | W | Bougies préchauffage | — |
| `0xB7` | 0x30 | W | Compteur tours | — |
| `0xBA` | 0x30 | W | Jauge température | — |
| `0xBD` | 0x30 | W | Modulator EGR | 7 |
| `0xBE` | 0x30 | W | Wastegate Turbo | 7 |
| `0xC1` | 0x30 | W | Type accélérateur | 1 |
| `0xC2` | 0x31 | W | Test injecteur N | 1 |
| `0xD5` | 0x31 | W | Settings string | 8 |
| `0xDD` | 0x31 | W | Clear faults | 17 |
| `0xDF` | 0x31 | W | Write settings | 16 |

---

## Roadmap (mise à jour v3)

### Phase 1 — MVP + Mode fabricant (PRIORITAIRE)

- [ ] Firmware Nano : séquence KWP2000 via STPX STN1110
- [ ] Firmware Nano : **td5keygen intégré** (C++ depuis keygen.c)
- [ ] App PC : init + auth session fabricant
- [ ] App PC : Local IDs 0x09, 0x0D, 0x10, 0x1A, 0x1C (RPM, speed, batterie, temps, MAP)
- [ ] App PC : base de données VIN + type ECU
- [ ] App PC : lecture faults 0x3B

### Phase 2 — Parité TestBook

- [ ] Papillon 0x1B, Power Balance 0x40, EGR 0x37/0x38
- [ ] Switches 0x1E, Boîte auto 0x36
- [ ] Toutes les actuations 0x30 (A1-BA)
- [ ] Test injecteurs 0x31/0xC2
- [ ] Clear faults 0x31/0xDD
- [ ] Settings lecture/écriture (0x3D, 0x0E, 0x32, 0x24)
- [ ] Wastegate + EGR modulators (7 octets)
- [ ] SLS suspension — PIDs CAN (hauteurs, mode, électrovannes) via ATSP6 0x730
- [ ] ABS / ETC — PIDs CAN (vitesses roues) via ATSP6 0x7A8
- [ ] BCU ZCS — lecture/écriture codage options (SLS delete, ACE delete) via ATSP6 0x760
- [ ] GEMS V8 — PIDs OBD standard + trim O2 via ATSP3

### Phase 3 — Au-delà

- [ ] Read memory / reflash NNN (SID 0x23)
- [ ] Fault decoder complet (280 codes LR)
- [ ] Data logging + rejeu
- [ ] Interface mobile
