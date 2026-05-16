# DiagRover — Hardware
### Architecture matérielle · Land Rover Discovery 2 / Range Rover
### v2 — mise à jour avec DiscoTD5.com + Td5OpenDiag

---

## Vue d'ensemble

Le hardware DiagRover reproduit l'architecture du TestBook T4 (Omitec) en deux blocs :

- **PC** : logiciel DiagRover, interface, base de données, rapports
- **Arduino Nano 33 BLE + SparkFun STN1110** : équivalent du boîtier VCSI Omitec

```
TESTBOOK T4 (original)          DIAGROVER (clone)
┌──────────────────┐            ┌──────────────────┐
│  Dell Latitude   │            │  PC / Laptop     │
│  Windows XP      │            │  Win/Linux/macOS │
│  RDS / IDS       │            │  DiagRover SW    │
└────────┬─────────┘            └────────┬─────────┘
         │ Ethernet                       │ USB CDC
┌────────▼─────────┐            ┌────────▼─────────┐
│  VCSI Omitec     │     =      │  Nano 33 BLE     │
│  VOM intégré     │            │  + Shield VOM    │
│  Transceiver     │            │  STN1110         │
└────────┬─────────┘            └────────┬─────────┘
         │ 25 broches D-type              │ DB9 → J1962
┌────────▼─────────┐            ┌────────▼─────────┐
│  Land Rover      │            │  Land Rover      │
│  Discovery 2     │            │  Discovery 2     │
└──────────────────┘            └──────────────────┘
```

---

## Composants — Liste complète

### Cerveau central

| Composant | Référence | Prix | Rôle |
|---|---|---|---|
| **Arduino Nano 33 BLE** | ABX00030 | ~22€ | VCSI — traitement protocoles, VOM, USB CDC |
| **Shield proto Nano** | — | ~4€ | Support composants VOM |
| **Câble USB-A → Micro-USB** | — | ~2€ | Liaison PC (données + alimentation) |

**Pourquoi le Nano 33 BLE :**
- nRF52840 ARM Cortex-M4 64MHz — timings précis bare-metal
- USB CDC natif dans le silicium — port COM virtuel sans driver
- ADC 12 bits — mesures VOM directes
- 3.3V natif — compatible STN1110 sans level shifter
- BLE 5.0 — option future interface mobile

### Interface véhicule — SparkFun OBD-II UART (STN1110)

| Composant | Référence | Prix | Rôle |
|---|---|---|---|
| **SparkFun OBD-II UART** | WIG-09555 | ~35€ | Tous protocoles OBD → UART |
| **Câble DB9 femelle → J1962 mâle** | — | ~3€ | ⚠️ À commander — non inclus |

**Pourquoi le STN1110 :**
- Gère K-Line (ISO9141/KWP2000 fast ET slow init), CAN, J1850 en hardware
- 3.3V natif — connexion directe Nano sans level shifter
- Commandes AT étendues (STPX, STMA) — multi-PID, trame raw
- Remplace L9637D + MCP2515 en une seule carte

### VOM — Shield Nano

| Composant | Qté | Prix | Rôle |
|---|---|---|---|
| Résistance 33kΩ 1% | 2 | ~0.10€ | Pont diviseur A0 — plage 0-20V |
| Résistance 5.6kΩ 1% | 2 | ~0.10€ | Pont diviseur A0 bas |
| Résistance 10kΩ 1% | 4 | ~0.10€ | Pont A1 + pont Wheatstone |
| Résistance 2.7kΩ 1% | 2 | ~0.10€ | Pont diviseur A1 — plage 0-15V |
| Module INA219 I2C | 1 | ~1.50€ | Mesure courant 0-3.2A |
| Jacks banane femelle 4mm | 4 | ~3€ | Sondes VOM |
| Condensateurs 100nF | 5 | ~0.10€ | Découplage |

---

## Budget total

| Catégorie | Coût |
|---|---|
| Nano 33 BLE + shield + câble USB | ~28€ |
| SparkFun STN1110 | ~35€ |
| Câble DB9 → J1962 ⚠️ | ~3€ |
| Composants VOM | ~6€ |
| Divers | ~5€ |
| **Total** | **~77€** |

---

## Timings ECU TD5 — données DiscoTD5

Source : reverse engineering firmware NNN/MSB par DiscoTD5.com

| Paramètre | Valeur | Implications |
|---|---|---|
| Crystal ECU | 4.0768 MHz | — |
| Clock système ECU | **16.3072 MHz** | Période = 61.32ns |
| Baud rate K-Line | 10 400 bps | 1 bit = 96.15µs = 1568 cycles ECU |
| P2 max (réponse ECU) | 50ms | ATST20=80ms suffisant en live data |
| P3 max (inter-message) | 5000ms | Keep-alive requis si pause > 2.5s |
| W1 (5-baud, 1 bit) | **200ms exact** | STN1110 gère nativement avec ATSP5 |

Le STN1110 respecte tous ces timings nativement. Le Nano n'a pas besoin d'implémenter
les délais ISO14230 en bare-metal.

---

## Protocoles par ECU — Discovery 2

| ECU | Protocole AT | Adresse CAN | Fallback | MY |
|---|---|---|---|---|
| Moteur TD5 | `ATSP4` (KWP fast) | 0x7E0/7E8 | ATSP5 si fail | 98-04 |
| Moteur GEMS V8 | `ATSP3` (ISO9141) | 0x7E0/7E8 | ATSP5 | 98-04 |
| BCU carrosserie | `ATSP6` (CAN) | 0x760 | **ATSP5 K-Line** | 02-04 / 98-01 |
| ABS / ETC | `ATSP6` (CAN) | 0x7A8 | ATSP8 (250k) | 98-04 |
| SLS suspension | `ATSP6` (CAN) | 0x730 | — | 98-04 |
| Immo / Clés | **`ATSP5`** (KWP slow) | — | — | 98-04 |

> **Règle de fallback** (source : Td5OpenDiag-android) : si ATSP4 retourne `UNABLE TO CONNECT`,
> réessayer automatiquement avec ATSP5. Sauvegarder le protocole retenu dans le profil véhicule.

---

## Paramètre ATST — adaptatif selon le mode

Source : timings TD5 DiscoTD5 + tests Td5OpenDiag

| Mode | Commande | Timeout | Justification |
|---|---|---|---|
| **Live data** | `ATST20` | 80ms | P2 max = 50ms, marge ×1.6 |
| **Diagnostic DTC** | `ATST96` | 384ms | Sécurité, ECU BCU/Immo lents |
| **Programmation ECU** | `ATSFF` | 1020ms | Timeout max, aucun risque |

Le mode est sélectionné par commande JSON depuis le PC : `{"cmd":"set_mode","mode":"livedata"}`.

---

## Performance sampling K-Line — comparatif

Source : DiscoTD5.com mesures réelles vs Nanocom

| Mode | Fréquence (7 PIDs) | vs Nanocom |
|---|---|---|
| Nanocom (référence) | 0.8 Hz | ×1 |
| STN1110 AT séquentiel | 1.6 Hz | ×2 |
| **STN1110 STPX multi-PID** | **~5 Hz** | **×6** |
| ISO14230 direct (Phase 3) | >10 Hz | >×12 |

La stratégie STPX groupe plusieurs PIDs en une seule trame :
```
STPX H:7DF,D:010C0D050B11  → 5 PIDs en ~110ms
STPX H:7DF,D:01100142      → 2 PIDs en ~95ms
Total 7 PIDs : ~205ms → 4.9Hz
```

> ⚠️ Certains ECU ne supportent pas le multi-PID. Tester au démarrage ;
> fallback sur mode séquentiel si `NO DATA`.

---

## Détection NNN vs MSB — NOUVEAU

Source : DiscoTD5.com reverse engineering firmware

Avant toute programmation d'injecteurs, l'ECU doit être identifié.
La commande `1A 92` (SystemSupplierSpecific ECUID) retourne le variant code en ASCII.

```
ATSH 8110F0     → adresser l'ECU moteur
1A 92           → lire variant code
Réponse NNN : 8190F0 09 5A 92 4E 4E 4E ...  ("NNN" en bytes 4-6)
Réponse MSB : 8190F0 09 5A 92 4D 53 42 ...  ("MSB" en bytes 4-6)
```

| Type ECU | Masque codes injecteurs | Plage valide |
|---|---|---|
| **MSB** | modulo 4 | 0–3 uniquement |
| **NNN** | modulo 16 | 0–15 (10P) / 0–9 (15P) |

> ⚠️ **Bug Nanocom documenté** (DiscoTD5) : le Nanocom autorise silencieusement
> des codes hors plage qui sont tronqués par le hardware ECU. DiagRover doit
> refuser tout code > 3 sur MSB et valider la cohérence map/ECU sur NNN.

À stocker dans `vehicles.ecu_type` en SQLite lors de la première identification.

---

## Keep-alive KWP2000 — NOUVEAU

Source : Td5OpenDiag-android (confirmé par timing P3 ISO14230 = 5s max)

L'ECU TD5 ferme la session KWP2000 si aucune trame n'est reçue pendant plus de 5 secondes.
Le firmware Nano doit envoyer périodiquement le service `0x3E` (Tester Present) :

```
Condition : millis() - last_cmd_ms > 2500
Action    : sendAT("3E")    → STN1110 → ECU
Réponse   : 7E8 01 7E       → ignorer, session maintenue
```

Ce timer est automatique et transparent pour l'utilisateur PC.
En mode live data actif (PIDs toutes les 500ms), le keep-alive est superflu —
les requêtes maintiennent la session naturellement.

---

## Schéma de connexion

### Nano 33 BLE ↔ SparkFun STN1110

```
Nano 33 BLE          SparkFun STN1110
  D0 (RX) ◄──────── TX
  D1 (TX) ────────► RX
  GND     ──────── GND   (masse commune — obligatoire)
  (STN1110 alimenté par OBD 12V — pas de VCC depuis Nano)
```

### Shield Nano — Circuit VOM

```
Canal A0 (0-20V)
  Jack rouge ── [R 33kΩ] ── nœud ── A0 Nano
                             │
                        [R 5.6kΩ]
                             │
                            GND

Canal A1 (0-15V)
  Jack jaune ── [R 10kΩ] ── nœud ── A1 Nano
                             │
                        [R 2.7kΩ]
                             │
                            GND

Canal A2 (0-3.3V / fréquence)
  Jack blanc ──────────────────── A2 Nano
             [R 10kΩ pull-down vers GND]

INA219 (courant)
  VCC ── 3.3V Nano   SDA ── A4 Nano
  GND ── GND         SCL ── A5 Nano
```

### Connecteur OBD J1962 (via câble DB9)

```
DB9 SparkFun     J1962 OBD-II
  Pin 2  ──────► Pin 7   (K-Line)
  Pin 3  ──────► Pin 6   (CAN High)
  Pin 4  ──────► Pin 4/5 (GND)
  Pin 5  ──────► Pin 14  (CAN Low)
  VBAT   ◄────── Pin 16  (12V batterie)
```

---

## Séquence init STN1110 — complète

```
1. Serial1.begin(9600)           ← STN1110 démarre à 9600
2. sendAT("ATZ")                 ← reset, attend "STN1110 vX.X.X"
3. delay(1000)                   ← délai post-reset obligatoire
4. sendAT("STBR115200")          ← passer à 115200
5. delay(100)
6. Serial1.end(); Serial1.begin(115200)
7. sendAT("ATZ")                 ← confirmer
8. sendAT("ATE0")                ← no echo
9. sendAT("ATL0")                ← no linefeed
10. sendAT("ATH1")               ← headers ON — indispensable
11. sendAT("ATS0")               ← no spaces
12. sendAT("ATCAF1")             ← CAN auto format (multi-frame)
13. sendAT("ATAL")               ← allow long messages
14. sendAT("ATST96")             ← timeout 384ms (mode diagnostic)
15. sendAT("ATRV")               ← sanity check tension batterie
16. sendAT("1A92")               ← détecter NNN vs MSB
17. Charger profil protocoles depuis SQLite vehicles.protocol_map
```

---

## Mesures VOM

| Canal | Plage | Résolution | Usage |
|---|---|---|---|
| A0 | 0 – 20V | ~5mV | Batterie, circuits 12V |
| A1 | 0 – 15V | ~3.6mV | Capteurs 5V/12V |
| A2 | 0 – 3.3V | ~0.8mV | Capteurs 3.3V, fréquence |
| INA219 | 0 – 3.2A | ~100µA | Courant actionneurs |
| D2 | Fréquence | 15.6ns | Signal injecteur, PWM |

**Calibration ADC** : appliquer 5.000V sur A2, mesurer la valeur brute,
calculer `cal_factor = 5.0 / (raw/4095.0 × 3.3)`. Non-linéarité nRF52840 = ±1%.

---

## ECU couverts — Discovery 2

| ECU | ID CAN | Protocole | ATST | Notes |
|---|---|---|---|---|
| Moteur TD5 | 0x7E8 | KWP fast ATSP4 | 20ms live / 96ms diag | NNN ou MSB |
| Moteur GEMS | 0x7E8 | ISO9141 ATSP3 | 96ms | — |
| BCU | 0x760 | CAN ATSP6 (MY02+) | 96ms | ATSP5 K-Line sur MY98-01 |
| ABS / ETC | 0x7A8 | CAN ATSP6 | 96ms | ATSP8 si 250kbps |
| SLS | 0x730 | CAN ATSP6 | 96ms | Multi-frame ISO-TP |
| Immo / Clés | — | KWP slow ATSP5 | 96ms | 5-baud init obligatoire |

---

## Checklist assemblage v2

### Étape 1 — Câble DB9 → J1962 (à commander avant tout)
- [ ] Commander câble "OBD2 DB9 female to J1962 male" (~3€ AliExpress)
- [ ] Vérifier pinout à réception (DB9 pin2 = K-Line, pin3 = CANH)

### Étape 2 — Rails de puissance shield
- [ ] Rail 3.3V horizontal (pin 3.3V Nano → rangée shield)
- [ ] Rail GND horizontal (pin GND Nano → rangée shield)
- [ ] Test continuité multimètre (aucun court-circuit)

### Étape 3 — Circuit VOM
- [ ] Pont diviseur A0 : 33kΩ / 5.6kΩ soudés
- [ ] Pont diviseur A1 : 10kΩ / 2.7kΩ soudés
- [ ] Pull-down 10kΩ sur A2
- [ ] Module INA219 (VCC/GND/SDA/SCL)
- [ ] Jacks banane fixés sur bord shield

### Étape 4 — Liaison STN1110
- [ ] Fil D0 Nano → TX SparkFun
- [ ] Fil D1 Nano → RX SparkFun
- [ ] GND Nano → GND SparkFun

### Étape 5 — Tests sans véhicule
- [ ] Loopback UART : relier D0↔D1, vérifier echo
- [ ] USB CDC détecté sur PC (port COM virtuel)
- [ ] Tensions VOM à vide : tous canaux à 0V
- [ ] STN1110 : `ATZ` → retourne `STN1110 vX.X.X`
- [ ] STN1110 : `ATRV` → tension batterie ~12.xV

### Étape 6 — Premier branchement véhicule
- [ ] Contact clé ON (pas de démarrage)
- [ ] `ATRV` → 12.x V confirmé
- [ ] `ATSP4` + `010C` → RPM valide
- [ ] `1A 92` → NNN ou MSB détecté, sauvegardé
- [ ] `ATSP6` + `STMA` → ECU CAN listés
- [ ] `ATSP5` + `ATSH8120` → BCU répond

---

## Points critiques v2

**Baud rate STN1110** : démarre à 9600, non mémorisé après coupure 12V.
Double init obligatoire à chaque connexion.

**Keep-alive KWP2000** (source : Td5OpenDiag, DiscoTD5) : timer 2500ms dans
le firmware, envoi de `0x3E` si inactif. Sans ça, session fermée après 5s de pause.

**Détection NNN vs MSB** (source : DiscoTD5) : commande `1A 92` en début de
session. Impacte la validation des codes injecteurs et la programmation ECU.

**Fallback ATSP4 → ATSP5** (source : Td5OpenDiag) : BCU et Immo ne répondent
pas en fast init. Fallback automatique, protocole sauvegardé dans le profil véhicule.

**ATST adaptatif** (source : timings DiscoTD5) : ATST20 en live data (80ms),
ATST96 en diagnostic (384ms), ATSFF en programmation (1020ms).

**GND commun** : relier GND USB PC + GND shield Nano + GND SparkFun + pin 4/5 OBD.

**Niveaux 3.3V** : Nano 33 BLE et STN1110 sont tous les deux 3.3V — aucun
level shifter ni pont diviseur sur la liaison UART.

