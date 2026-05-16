# DiagRover — État de l'art
### Analyse des projets open source de référence

---

## Vue d'ensemble

| Projet | Lien | Langage | Pertinence DiagRover |
|---|---|---|---|
| **Td5OpenDiag-android** | https://github.com/Td5OpenDiag/Td5OpenDiag-android | Java/Android | ⭐⭐⭐⭐⭐ Directement applicable — TD5 LR |
| **python-OBD** | https://github.com/brendan-w/python-OBD | Python | ⭐⭐⭐⭐⭐ Couche OBD PC à réutiliser |
| **CanCat** | https://github.com/atlas0fd00m/CanCat | Python + Arduino C++ | ⭐⭐⭐⭐ Architecture firmware identique |
| **pyftdi** | https://github.com/eblot/pyftdi | Python | ⭐⭐⭐ Patron USB-série en Python pur |
| **OBDb** | https://github.com/OBDb | JSON / communauté | ⭐⭐⭐ Base de données PIDs à exploiter |
| **Discovery 2 Technical Academy** | https://fr.scribd.com/doc/211358372/Discovery-2-Land-Rover-Technical-Academy | PDF | ⭐⭐⭐⭐⭐ Documentation officielle LR |

---

## 1. Td5OpenDiag-android

**Lien :** https://github.com/Td5OpenDiag/Td5OpenDiag-android
**Langage :** Java · Android
**Licence :** Apache 2.0
**Activité :** 17 stars · 5 forks · 117 commits

### Architecture globale

Application Android qui communique avec l'ECU TD5 via un adaptateur ELM327 Bluetooth. Architecture en couches strictement séparées :

```
UI Layer (Activities / Fragments)
        ↓
ViewModel / Presenter
        ↓
ECU Service Layer (sessions KWP2000)
        ↓
ELM327 Driver (AT commands)
        ↓
Bluetooth SPP (BluetoothSocket)
        ↓
ELM327 adapter → K-Line → ECU TD5
```

Pas de dépendance sur des bibliothèques OBD tierces — tout le stack KWP2000 est réimplémenté en Java natif, ce qui donne un contrôle total sur les timings et les trames propriétaires Land Rover.

### Features & stratégies

**Connexion ELM327 Bluetooth**
Utilise le profil SPP (Serial Port Profile) de Android via `BluetoothSocket`. L'UUID SPP standard est `00001101-0000-1000-8000-00805F9B34FB`.

```java
// Connexion SPP Bluetooth vers ELM327
BluetoothDevice device = bluetoothAdapter.getRemoteDevice(address);
BluetoothSocket socket = device.createRfcommSocketToServiceRecord(
    UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
);
socket.connect();
InputStream in  = socket.getInputStream();
OutputStream out = socket.getOutputStream();
```

> **Pour DiagRover :** remplacer `BluetoothSocket` par `serial.Serial` Python côté PC. La logique de l'init AT et du parsing est identique.

**Séquence d'initialisation AT spécifique TD5**
Le projet force le protocole KWP2000 slow init pour les ECU Land Rover qui ne répondent pas en fast init :

```java
private void initELM327() {
    sendCommand("ATZ");         // reset
    sendCommand("ATE0");        // no echo
    sendCommand("ATH1");        // headers
    sendCommand("ATSP5");       // KWP2000 slow init — critique pour certains ECU LR
    sendCommand("ATST96");      // timeout 150ms × 4 = 600ms — nécessaire pour ECU lents
    sendCommand("ATAL");        // allow long messages
}
```

> **Vigilance DiagRover :** `ATSP5` (slow init) à tester systématiquement si `ATSP4` (fast init) échoue sur BCU ou Immo. La commande `ATST` contrôle le timeout ELM327 en multiples de 4ms.

**Parsing de trames KWP2000 propriétaires TD5**
Le projet décode directement les octets bruts sans bibliothèque tierce :

```java
// Décodage trame KWP2000 retournée par ELM327
// Format : "48 6B 10 41 0C 1A F0 XX" (avec header)
private float decodeRPM(String response) {
    String[] bytes = response.trim().split("\\s+");
    // bytes[4]=mode_resp bytes[5]=PID bytes[6]=A bytes[7]=B
    int A = Integer.parseInt(bytes[6], 16);
    int B = Integer.parseInt(bytes[7], 16);
    return (A * 256 + B) / 4.0f;
}
```

**Lecture live data temps réel**
Threading Android : lecture série sur `AsyncTask` ou `HandlerThread`, mise à jour UI via `runOnUiThread()`. Même contrainte que PyQt : jamais de mise à jour UI directe depuis le thread série.

**Sessions KWP2000 avec keep-alive**
KWP2000 ferme la session si aucune requête pendant plus de 5 secondes. Le projet envoie périodiquement une requête `tester present` (0x3E) pour maintenir la session :

```java
// Keep-alive KWP2000 : envoyer toutes les 2-3s
private void sendTesterPresent() {
    sendCommand("3E");   // service 0x3E = tester present
}
```

> **Vigilance DiagRover :** implémenter un timer de keep-alive dans le firmware Nano. Sans ça, l'ECU ferme la session KWP2000 et il faut reinitier l'init complète (3-5s de perdu).

### Ce qui est directement réutilisable

- La séquence AT complète pour TD5
- La logique de parsing des trames avec headers
- La gestion du keep-alive KWP2000
- La liste des PIDs TD5 testés et validés

---

## 2. python-OBD

**Lien :** https://github.com/brendan-w/python-OBD
**Langage :** Python 3
**Licence :** GNU GPL v2
**Activité :** Stable, utilisé comme dépendance dans de nombreux projets

### Architecture globale

Bibliothèque Python pour interfacer n'importe quel adaptateur ELM327 via port série. Architecture en 4 couches indépendantes :

```
obd.py / async.py          ← API publique (OBD, Async)
        ↓ ↑
OBDCommand.py              ← définition des commandes (PID + décodeur)
        ↓ ↑
elm327.py + protocol/      ← driver ELM327 + protocoles OBD
        ↓ ↑
pyserial                   ← couche transport série
```

Chaque couche est testable indépendamment. Le décodage est séparé de la communication — une commande OBD est un objet (`OBDCommand`) avec son PID, son décodeur, et son unité de mesure.

### Features & stratégies

**API synchrone simple**

```python
import obd

connection = obd.OBD()               # auto-connect sur port COM/USB
cmd = obd.commands.RPM               # sélectionner une commande
response = connection.query(cmd)     # envoyer, attendre, décoder
print(response.value)                # Quantity avec unité (pint)
print(response.value.to("rpm"))      # conversion d'unité
```

**API asynchrone avec callbacks**
Stratégie : un thread background poll les commandes surveillées en boucle. L'API publique retourne immédiatement la dernière valeur connue (non-bloquant).

```python
connection = obd.Async()

def on_rpm(response):
    print(f"RPM : {response.value}")

connection.watch(obd.commands.RPM, callback=on_rpm)
connection.start()      # démarre le thread de polling
# ... plus tard ...
connection.stop()
```

> **Pour DiagRover :** adopter ce pattern Async pour le module live data. Le thread série lit en continu, les callbacks mettent à jour les graphes PyQt via signaux Qt. C'est exactement ce que notre `SerialManager` doit faire.

**Définition déclarative des commandes**
Chaque commande OBD est définie comme un objet avec PID, mode, décodeur et unité :

```python
# Extrait de commands.py python-OBD
RPM = OBDCommand(
    name     = "RPM",
    desc     = "Engine RPM",
    command  = b"010C",
    bytes    = 4,
    decoder  = lambda messages: Unit.Quantity(
        ((messages[0].data[2] * 256) + messages[0].data[3]) / 4,
        Unit.rpm
    )
)
```

> **Pour DiagRover :** utiliser ce pattern pour définir les PIDs TD5 propriétaires LR. Créer un fichier `pid_definitions_lr.py` avec les mêmes structures pour les PIDs non-standard Land Rover.

**Auto-détection des commandes supportées**
À la connexion, python-OBD interroge le véhicule sur ses PIDs supportés (mode 0x01 PID 0x00, 0x20, 0x40...) et marque chaque commande comme `supported=True/False`.

```python
def __load_commands(self):
    """Interroge le véhicule pour ses PIDs supportés."""
    for mode in [1, 2, 5, 7, 9]:
        supported = self.query(obd.commands["GET_CURRENT_DTC"])
        # marque chaque commande en conséquence
```

> **Vigilance DiagRover :** certains ECU Land Rover (BCU, SLS) ne répondent pas correctement aux requêtes de découverte de PIDs supportés. Bypasser cette étape et hardcoder les PIDs connus pour les modules LR propriétaires.

**Gestion robuste des non-réponses**

```python
response = connection.query(cmd)
if response.is_null():
    print("Pas de réponse — ECU non supporté ou déconnecté")
else:
    print(response.value)
```

> **Pour DiagRover :** toujours vérifier `is_null()` avant d'accéder à `.value`. Les ECU Land Rover peuvent retourner NO DATA ou UNABLE TO CONNECT selon leur état.

**Units avec Pint**
Toutes les valeurs retournées sont des `Quantity` avec unité via la bibliothèque Pint. Permet les conversions automatiques (km/h → mph, °C → °F).

> **Pour DiagRover :** adopter Pint pour toutes les valeurs du module live data. Permet à l'utilisateur de choisir son système d'unités (métrique/impérial) sans toucher au décodage.

### Ce qui est directement réutilisable

- Le pattern `OBDCommand` déclaratif — adopter pour les PIDs LR
- Le pattern `Async` avec callbacks — adopter pour le live data
- La gestion `is_null()` des non-réponses
- Le `scan_serial()` pour l'auto-détection du port COM

---

## 3. CanCat

**Lien :** https://github.com/atlas0fd00m/CanCat
**Langage :** Python (PC) + C++ Arduino (firmware)
**Licence :** BSD
**Activité :** 170 stars · 34 forks

### Architecture globale

Architecture deux couches identique à DiagRover : un firmware Arduino qui tourne sur le hardware CAN, et une bibliothèque Python côté PC qui le pilote via USB série. C'est le "couteau suisse du CAN bus".

```
PC — Python
  cancat.CAN()              ← API principale
  cancat.uds.UDS()          ← protocole UDS (proche KWP2000)
  cancat.J1939              ← protocole J1939 camion
  cancat.canmap             ← scanner ECU UDS
        ↓ USB série (binaire)
Arduino Firmware (C++)
  MCP2515 driver
  CAN frame capture/inject
  USB serial bridge
        ↓ CAN bus
  Véhicule
```

La communication PC ↔ Arduino est en **binaire structuré** (pas JSON), ce qui la rend plus compacte et rapide — important pour ne rater aucune trame CAN à 500kbps.

### Features & stratégies

**Capture passive du bus CAN (Monitor All)**
Capture toutes les trames en transit sans perturber le bus :

```python
import cancat

# Ouvrir une session CanCat
cc = cancat.CAN('/dev/ttyACM0', cancat.BAUD_500KBPS)

# Capturer pendant 10s
cc.CANrecv(timeout=10)

# Analyser les trames capturées
for arb_id, data in cc.recvd_frames.items():
    print(f"ID: {hex(arb_id)} Data: {data.hex()}")
```

> **Pour DiagRover :** la commande `STMA` du STN1110 fait exactement ça. Mais l'approche CanCat de stocker toutes les trames dans un dictionnaire `{arb_id: [frames]}` est un excellent patron pour le module de logging CAN.

**Scanner ECU via UDS / Canmap**
CanCat inclut un outil `canmap` qui scanne le bus pour trouver tous les ECU répondant à UDS :

```bash
# Scanner ECU à 500kbps, scan DTC + DID
./canmap -p /dev/ttyACM0 -b 500K -sEDS -o scan_results.yml
```

Résultats sauvegardés en YAML — les scans peuvent être repris sans réanalyser les ECU déjà connus.

> **Pour DiagRover :** adopter ce principe de scan incrémental avec sauvegarde YAML. Lors de la première connexion à un Discovery 2, scanner tous les ECU et sauvegarder le profil. Les sessions suivantes chargent le profil sans rescanner.

**CAN-in-the-Middle**
CanCat supporte deux shields CAN sur un même Arduino pour faire du man-in-the-middle CAN — utile pour isoler un ECU et observer ses messages sans le retirer du bus.

> **Note DiagRover :** pas immédiatement utile, mais la technique peut servir pour le reverse-engineering des PIDs propriétaires LR non documentés.

**Protocol binaire PC ↔ Arduino**
CanCat utilise un protocole binaire simple au lieu de JSON. Chaque message est : `[longueur 1B][commande 1B][données nB]`

```cpp
// Firmware Arduino CanCat
void loop() {
    if (Serial.available() >= 2) {
        uint8_t len = Serial.read();
        uint8_t cmd = Serial.read();
        // dispatcher selon cmd
        switch(cmd) {
            case CMD_RECV:  handleRecv(); break;
            case CMD_SEND:  handleSend(); break;
            case CMD_SNIFF: handleSniff(); break;
        }
    }
}
```

> **Vigilance DiagRover :** notre choix JSON est plus lisible mais ~3× plus gourmand en bytes. Pour le live data haute fréquence (>5Hz), envisager un format binaire compact pour les messages de type `live` (type 1B + pid 1B + value 4B = 6B vs ~40B JSON).

**Watchfor — filtrage par ID CAN**
API pour ne recevoir que les trames d'un ECU spécifique :

```python
cc.watchFor(0x7E8)              # ECU moteur uniquement
cc.watchFor(0x730, 0x7FF)       # SLS avec masque
cc.watchForRange(0x700, 0x7FF)  # tous ECU 0x700-0x7FF
```

> **Pour DiagRover :** implémenter ce filtrage côté STN1110 avec `ATCF` (CAN filter) et `ATCM` (CAN mask). Réduit le traffic USB et le charge CPU Nano.

### Ce qui est directement réutilisable

- Architecture firmware Arduino (loop + dispatcher commandes)
- Pattern de stockage trames `{arb_id: [frames]}` pour le logging
- Approche scan incrémental avec sauvegarde de profil
- Filtrage par ID CAN pour le live data ciblé

---

## 4. pyftdi

**Lien :** https://github.com/eblot/pyftdi
**Langage :** Python pur
**Licence :** BSD
**Activité :** 370 stars

### Architecture globale

Driver Python pur pour les chips FTDI (FT232H, FT2232H, FT4232H) qui permet de contrôler UART, SPI, I2C, GPIO et JTAG depuis Python sans driver noyau. Utilise `pyusb` pour accéder au chip FTDI directement en USB.

```
Application Python
        ↓
pyftdi API (uart/spi/i2c/gpio)
        ↓
FtdiDevice (USB MPSSE mode)
        ↓
pyusb (libusb)
        ↓
Chip FTDI FT232H/FT2232H
        ↓
Périphérique (UART → K-Line, SPI → MCP2515, I2C → INA219)
```

### Pertinence pour DiagRover

pyftdi est **indirectement pertinent** : il démontre comment abstraire une couche USB-série en Python pur, sans dépendre d'un driver noyau. Le patron d'architecture est applicable à notre couche `SerialManager`.

### Features & stratégies

**URL-based device addressing**
pyftdi identifie les devices FTDI par URL plutôt que par numéro de port :

```python
from pyftdi.uart import UartController

uart = UartController()
uart.configure('ftdi://ftdi:232h/1', baudrate=115200)
uart.write(b'ATZ\r')
response = uart.read(64)
```

> **Pour DiagRover :** adopter ce pattern URL pour identifier le Nano. L'USB CDC du nRF52840 peut être adressé par son `VID:PID` plutôt que par son nom de port COM (plus stable entre rebranchements).

**MPSSE — protocoles synchrones en Python pur**
Le mode MPSSE du chip FTDI permet de faire du SPI/I2C/JTAG directement en Python, sans firmware intermédiaire. C'est l'équivalent de ce que fait notre firmware Nano, mais côté PC via un chip FTDI.

```python
from pyftdi.spi import SpiController

spi = SpiController()
spi.configure('ftdi://ftdi:2232h/1')
slave = spi.get_port(cs=0, freq=1E6, mode=0)
data = slave.exchange([0x03, 0x00, 0x00], 4)  # lire registre CANSTAT MCP2515
```

> **Note DiagRover :** cette approche alternative (FTDI FT2232H au lieu d'un Nano) permettrait de contrôler le MCP2515 directement depuis Python, sans firmware Arduino. Plus rapide à développer mais plus cher et moins portable.

**Gestion latence USB**
pyftdi expose directement la latence USB du chip FTDI. Paramètre critique pour les protocoles temps-réel :

```python
# Latence par défaut = 16ms — trop lent pour K-Line !
uart.configure('ftdi://ftdi:232h/1', baudrate=9600, latency=1)
# Latence 1ms — acceptable pour KWP2000
```

> **Vigilance DiagRover :** le Nano 33 BLE avec USB CDC natif nRF52840 a une latence USB de ~1ms (Full Speed, 1ms par microframe). C'est suffisant. Si des problèmes de latence apparaissent, vérifier que le driver USB CDC n'a pas un buffer de 16ms comme les FTDI par défaut.

**pyserial emulation layer**
pyftdi inclut une couche de compatibilité pyserial, permettant d'utiliser le code pyserial existant sans modification :

```python
# Code pyserial standard
import serial
ser = serial.Serial('/dev/ttyUSB0', 115200)

# Même code avec pyftdi — compatible à 100%
from pyftdi.serialext import serial_for_url
ser = serial_for_url('ftdi://ftdi:232h/1', baudrate=115200)
```

> **Pour DiagRover :** notre `SerialManager` doit utiliser l'interface pyserial standard. Ainsi, si quelqu'un veut remplacer le Nano par un FTDI, il suffira de changer l'URL de connexion sans toucher au code.

### Ce qui est directement réutilisable

- Pattern URL pour l'adressage hardware (plus stable que le nom de port COM)
- Paramètre latence USB — à vérifier sur le Nano
- Couche d'abstraction pyserial — adopter pour la portabilité

---

## 5. OBDb — The OBD Database

**Lien :** https://github.com/OBDb
**Format :** JSON structuré par véhicule
**Licence :** CC BY-SA 4.0
**Site :** https://obdb.community

### Architecture globale

Base de données communautaire open source des paramètres OBD de tous les véhicules. Organisée en repositories GitHub individuels par marque/modèle. Chaque repo contient des fichiers JSON décrivant les PIDs supportés, leurs formules de décodage, et les signaux retournés.

```
github.com/OBDb/
├── SAEJ1979/             ← PIDs standards SAE
│   └── signalsets/v3/default.json
├── Land-Rover-Discovery/ ← si disponible
│   └── signalsets/v3/
│       ├── default.json        ← config par défaut
│       └── 1999-2004.json      ← override pour Série II
├── Ford-F-150/
├── Toyota-Camry/
└── ...400+ véhicules

obdb.community/           ← interface web de navigation
```

### Structure d'un signalset JSON

```json
{
  "commands": [
    {
      "id": "ENGINE_RPM",
      "command": "010C",
      "freq": 1.0,
      "signals": [
        {
          "id": "ENGINE_RPM",
          "path": "Engine.RPM",
          "fmt": {
            "len": 16,
            "max": 16383.75,
            "min": 0,
            "mul": 0.25,
            "unit": "rpm"
          },
          "name": "Engine RPM"
        }
      ]
    }
  ]
}
```

### Features & stratégies

**Structure Commands / Signals**
Un Command (requête OBD) peut retourner plusieurs Signals (valeurs décodées). Cette distinction est cruciale pour les PIDs qui retournent plusieurs bytes encodant plusieurs grandeurs physiques.

> **Pour DiagRover :** adopter le schéma `commands/signals` de l'OBDb pour la base de données des PIDs. Plus propre que de stocker formule et unité directement dans le code.

**Versionning des signalsets par année**
Un fichier `default.json` sert de fallback, des fichiers `2002-2004.json` surchargent pour les années spécifiques. Parfait pour gérer les différences MY98-01 vs MY02-04 du Discovery 2 (BCU CAN vs K-Line uniquement).

```
signalsets/v3/
├── default.json          ← comportement standard
└── 1998-2001.json        ← override : BCU sur K-Line uniquement, pas CAN
```

> **Pour DiagRover :** créer un repo OBDb-compatible pour le Discovery 2. Deux signalsets : `default.json` (MY02+, CAN) et `1998-2001.json` (K-Line uniquement pour BCU). Permet une contribution à la communauté.

**Outil d'extraction en Python**

```python
# extract_data.py — pattern OBDb
import json, os, glob

def extract_pids(make, model, year):
    """Charge le signalset approprié selon l'année."""
    base_path = f"workspace/{make}-{model}/signalsets/v3/"
    # Cherche un override pour l'année
    override = f"{base_path}/{year}.json"
    if os.path.exists(override):
        return json.load(open(override))
    # Fallback sur default
    return json.load(open(f"{base_path}/default.json"))
```

> **Pour DiagRover :** réutiliser ce pattern pour charger dynamiquement les PIDs selon le millésime du véhicule détecté via le VIN.

**Validation JSON avec schema**
OBDb fournit un schema JSON pour valider les contributions :

```bash
python validate_json.py --input default.json \
                        --output normalized.json \
                        --schema signal_schema.json
```

> **Pour DiagRover :** créer un schema JSON pour les PIDs Land Rover propriétaires et valider la base DTC avant chaque release.

### Ce qui est directement réutilisable

- Format JSON `commands/signals` pour la base des PIDs
- Pattern versionning par année
- Séparation Command / Signal (une requête → plusieurs valeurs)
- L'organisation `signalsets/v3/` comme convention de nommage

---

## 6. Discovery 2 — Land Rover Technical Academy

**Lien :** https://fr.scribd.com/doc/211358372/Discovery-2-Land-Rover-Technical-Academy
**Type :** Documentation officielle Land Rover
**Pertinence :** Source primaire pour tous les protocoles et PIDs LR

### Contenu

Document de formation technique officiel Land Rover pour les techniciens agréés. Contient :

- Architecture électronique complète du Discovery 2
- Adresses ECU et protocoles de communication de chaque module
- Procédures de diagnostic officielles TestBook
- PIDs propriétaires LR documentés
- Valeurs nominales par paramètre (plages normales)
- Procédures de calibration step-by-step

### Points clés pour DiagRover

**Adresses ECU confirmées**

| ECU | Adresse KWP | Adresse CAN | Protocole |
|---|---|---|---|
| Moteur TD5 | 0x10 | 0x7E0/7E8 | KWP2000 fast |
| BCU | 0x20 | 0x760 (MY02+) | KWP / CAN |
| ABS/ETC | 0x57 | 0x7A8 | CAN |
| SLS | 0x6A | 0x730 | CAN |
| Immo | 0x44 | — | KWP slow |

**Init KWP2000 Land Rover spécifique**
Land Rover utilise le slow init (5-baud) pour certains modules même sur des véhicules MY02+. La Technical Academy précise que le BCU et l'Immo nécessitent TOUJOURS le slow init quelle que soit l'année.

**PIDs propriétaires TD5 documentés**
La documentation liste les PIDs spécifiques TD5 non standard SAE :

| PID | Paramètre | Formule |
|---|---|---|
| 21C3 | Pression turbo | (A×256+B) / 100 bar |
| 2124 | Temp. carburant | A - 40 °C |
| 2108 | Correction débit injecteurs | A - 128 mg/stroke |
| 210A | Position EGR | A × 100 / 255 % |
| 2109 | Pression rampe carburant | (A×256+B) bar |

---

## Synthèse — Ce qu'on retient pour DiagRover

### Patterns à adopter directement

| Pattern | Source | Application DiagRover |
|---|---|---|
| `OBDCommand` déclaratif | python-OBD | Définition PIDs TD5/LR |
| `Async` + callbacks | python-OBD | Module live data |
| Keep-alive KWP2000 (0x3E) | Td5OpenDiag | Firmware Nano, toutes sessions |
| `ATSP5` + `ATST96` pour LR | Td5OpenDiag | Init BCU / Immo |
| Firmware dispatcher binaire | CanCat | Alternative JSON si performance insuffisante |
| Scan incrémental + YAML | CanCat | Profil véhicule au premier scan |
| URL device addressing | pyftdi | SerialManager portable |
| Format commands/signals JSON | OBDb | Base de données PIDs |
| Versionning par année | OBDb | MY98-01 vs MY02-04 |

### Vigilances identifiées

**1. ATSP5 obligatoire pour BCU et Immo LR**
Td5OpenDiag le confirme : `ATSP4` (fast init) échoue sur certains modules Land Rover. Implémenter un fallback automatique `ATSP4 → ATSP5` si NO DATA.

**2. Keep-alive KWP2000 toutes les 2-3 secondes**
Sans `tester present (0x3E)` périodique, l'ECU ferme la session après 5s. Td5OpenDiag l'implémente, nous devons aussi.

**3. Timeout ELM327/STN1110 à ajuster**
`ATST96` (timeout 600ms) est nécessaire pour les ECU LR lents. Le timeout par défaut (200ms) est trop court pour BCU et SLS.

**4. PIDs propriétaires LR non dans python-OBD**
python-OBD ne couvre que les PIDs SAE standard. Les PIDs TD5 (pression turbo, débit injecteurs, EGR) doivent être ajoutés manuellement avec le pattern `OBDCommand`.

**5. Format binaire vs JSON selon la fréquence**
CanCat utilise du binaire pour ne rater aucune trame CAN. Pour DiagRover, JSON est suffisant pour le live data K-Line (~2Hz). Si on monte en fréquence avec CAN (>10Hz), prévoir un format binaire compact.

**6. Adresses ECU LR à hardcoder**
La Technical Academy LR confirme que les ECU Land Rover ne répondent pas systématiquement aux requêtes de découverte de PIDs supportés. Hardcoder les adresses ECU connues plutôt que de dépendre de l'auto-détection.


---

## 7. DiscoTD5.com — ECU Tech

**Lien :** https://discotd5.com/ecu_tech
**Sous-sections clés :**
- https://discotd5.com/ecu-tech/ecu-reverse-engineering
- https://discotd5.com/ecu-tech/data-logging
- https://discotd5.com/logger-project
- https://discotd5.com/scripts-and-code
**Type :** Site communautaire · recherche indépendante · 2012–2024
**Pertinence :** ⭐⭐⭐⭐⭐ Source primaire la plus complète sur l'ECU TD5 disponible en open source

### Architecture globale

DiscoTD5.com n'est pas un projet GitHub unique mais un corpus de recherche technique approfondi sur le TD5, maintenu par un développeur indépendant anonyme depuis 2012. Il couvre six axes majeurs :

```
discotd5.com/ecu_tech
├── ECU Reverse Engineering     ← firmware NNN/MSB disassemblé
│   ├── Architecture flash ECU
│   ├── Protocole KWP2000 LR propriétaire
│   ├── Codes injecteurs (idle codes)
│   └── Bugs Nanocom documentés
├── Td5 Tuning                  ← cartographies et maps
│   ├── MAP sensor recalibration
│   ├── Injector Duration Maps
│   ├── Wastegate Modulator
│   └── Overboost Fuel Cut
├── Data Logging                ← projet logger hardware+software
│   ├── Interface K-Line custom (C, Microchip PIC)
│   └── Logging >4 samples/s via ISO14230 direct
├── Logger Project              ← app Python cross-platform
│   ├── ECU Read/Write
│   ├── Map Programming (brick-proof)
│   └── XDL format (TunerPro compatible)
├── Scripts and Code            ← Python + C
│   ├── Map Finder (Kivy)
│   ├── Injector code programming
│   └── Scripts GitHub engine maps
└── Tuner Pro                   ← XDF donor files pour TD5
```

L'auteur a fait ce que nous voulons faire pour DiagRover, mais uniquement côté tuning/reflash. Sa recherche sur le protocole KWP2000 LR et les commandes diagnostics propriétaires est la plus précise disponible open source.

---

### Features & stratégies détaillées

#### Architecture hardware du logger

L'auteur utilise une interface K-Line custom (firmware C sur microcontrôleur Microchip PIC) qui expose une interface de commandes AT simplifiée, similaire à l'ELM327, permettant de se connecter à un ECU TD5 sans se préoccuper des protocoles sous-jacents.

```
PC (Python)
    ↕ USB série AT commands
Interface K-Line custom (PIC)
    ↕ ISO14230 / KWP2000
ECU TD5
```

La décision de l'auteur : utiliser un framework publish & subscribe pour résoudre les problèmes rencontrés avec le code bloquant précédent. L'approche est de construire un module gérant les commandes `startCommunications`, `sendData` et `stopCommunications` de l'ISO14230 comme base du logger/interface.

> **Pour DiagRover :** ce patron publish/subscribe est exactement le `event_bus.py` dans notre architecture PC. Chaque module (DTC, live data, actuations) s'abonne aux événements qu'il veut recevoir sans couplage direct.

#### Fréquence de logging réelle sur TD5

Les paramètres sont échantillonnés à plus de 4 fois par seconde, contre une fois toutes les 1,25 secondes pour le Nanocom. Certains paramètres disponibles comme requête unique peuvent être loggés à plus de 10 fois par seconde, donnant un snapshot très détaillé des performances des capteurs.

> **Pour DiagRover :** confirmation que >4Hz est atteignable sur K-Line TD5 en mode ISO14230 direct (sans passer par un ELM327 intermédiaire). Avec notre STN1110, `STPX` multi-PID peut théoriquement approcher cette fréquence.

#### Mécanisme "brick-proof" de programmation NNN

Le NNN possède un mécanisme extrêmement robuste qui ne rend l'ECU bootable qu'après que la fuel map a été complètement programmée et que les données ont été vérifiées. Mais seulement si la map uploadée coche toutes les cases. Le problème est qu'aucune des maps produites pour le Nanocom ne sont configurées pour utiliser cette fonctionnalité.

> **Vigilance DiagRover :** pour le Module 7 (programmation ECU), toujours écrire des maps avec les checksums et les bytes de validation correctement configurés. Une map incomplète sur NNN = ECU briqué si le contact est coupé pendant l'écriture.

#### Horloge ECU TD5 — donnée critique

Le cristal de l'ECU TD5 est à 4.0768MHz et le clock système tourne à 16.3072MHz. Cette information est nécessaire après avoir localisé le code gérant la configuration du clock pour les communications OBD-II.

> **Pour DiagRover :** cette fréquence détermine les timings exacts du protocole KWP2000 dans l'ECU. Si des problèmes de timing apparaissent lors de la communication directe ISO14230 (sans STN1110), ces valeurs permettent de calculer les délais inter-octets exacts.

#### Différences NNN vs MSB — critique pour l'adressage

L'ECU MSB masque les valeurs envoyées par l'outil de diagnostic en effectuant l'équivalent d'un modulo 4 de la valeur envoyée. L'ECU NNN masque les valeurs avec l'équivalent d'un modulo 16, ce qui signifie qu'il peut sauvegarder des valeurs de 0 à 15 en EEPROM.

```python
# Comportement différent selon le hardware ECU
# MSB : modulo 4
def encode_injector_code_msb(code: int) -> int:
    return code % 4

# NNN : modulo 16
def encode_injector_code_nnn(code: int) -> int:
    return code % 16
```

> **Vigilance DiagRover :** détecter le type d'ECU (MSB ou NNN) avant toute opération de programmation des codes injecteurs. La lecture du variant code via KWP2000 `0x1A 0x92` permet de distinguer MSB/NNN.

#### App Python cross-platform — Logger Project

L'app fonctionne sur macOS et Windows 10+. Les modules Map Tools gèrent le flux input → information → output. Les inputs sont Map Finder (base de données), Open File (formats Nanocom .map, .tun, 16kb/256kb bin, Kess bin, MEMS3) et Read from ECU. Les outputs sont Write File et Write ECU (programmation).

L'app présente des problèmes avec les exécutables PyInstaller identifiés comme malware — faux positifs nécessitant une signature de code payante pour être résolus.

> **Vigilance DiagRover :** distribuer DiagRover comme script Python (avec `requirements.txt`) plutôt que comme exécutable PyInstaller pour éviter ce problème. Sur Windows, proposer un script `install.bat` qui installe Python et les dépendances.

#### Format XDL (TunerPro)

Le logging au format XDL TunerPro est opérationnel. La bibliothèque FAT32 event-driven non-bloquante intégrée dans le module de logging fonctionne bien avec l'auto-détection hardware MSB/NNN et le switch du mapping throttle selon le hardware détecté.

> **Pour DiagRover :** ajouter le format XDL en export depuis le module live data — permet aux utilisateurs TD5 de visualiser leurs logs dans TunerPro RT avec les tables de cartographie en overlay temps réel.

#### Bugs Nanocom documentés

La section Nanocom Bugs de DiscoTD5 documente des comportements incorrects du Nanocom sur Discovery 2 TD5 — autant d'erreurs à ne pas reproduire dans DiagRover :

- Gestion incorrecte des codes injecteurs 15P sur ECU NNN (modulo incorrect)
- Affichage de valeurs AAT incorrectes sur ECU MSB avec support throttle 3 voies
- Absence de l'AAT dans les logs EU3 malgré la lecture depuis l'ECU
- Comportement incorrect lors de la programmation de maps sans brick-proof activé

> **Pour DiagRover :** tester spécifiquement chaque point documenté comme bugué dans le Nanocom et s'assurer que DiagRover les gère correctement.

---

### Tableau des PIDs TD5 additionnels documentés sur DiscoTD5

Au-delà des PIDs standards SAE, DiscoTD5 documente des paramètres accessibles via les commandes diagnostics propriétaires LR :

| Paramètre | Commande | ECU | Notes |
|---|---|---|---|
| Codes injecteurs (idle) | `0x1A + local ID` | TD5 | 10P modulo 4 / 15P modulo 16 |
| Throttle tracks 1 & 2 | `0x21 + local ID` | MSB/NNN | NNN = 3 tracks |
| Conversion ADC brute | Requête spécifique | MSB/NNN | Debug capteurs |
| Variant code ECU | `0x1A 0x92` | TD5 | Identifie NNN vs MSB |
| Fuel map programming record | Via programmation | NNN | Date + metadata |

---

### Ce qui est directement réutilisable

- Architecture publish/subscribe pour le firmware et l'app PC
- Confirmation >4Hz atteignable en ISO14230 direct sur TD5
- Timing critique : crystal 4.0768MHz, clock 16.3072MHz
- Distinction NNN vs MSB obligatoire avant programmation injecteurs
- Format XDL export pour compatibilité TunerPro
- Liste des bugs Nanocom à éviter dans DiagRover
- Mécanisme brick-proof : validation checksums avant flash ECU
- Distribution comme script Python plutôt qu'exécutable PyInstaller

---

## Synthèse mise à jour — 7 projets

| Projet | Pertinence | Contribution principale pour DiagRover |
|---|---|---|
| **Td5OpenDiag-android** | ⭐⭐⭐⭐⭐ | ATSP5 LR, keep-alive KWP2000, parsing trames |
| **python-OBD** | ⭐⭐⭐⭐⭐ | OBDCommand déclaratif, Async callbacks |
| **CanCat** | ⭐⭐⭐⭐ | Architecture firmware, scan incrémental |
| **pyftdi** | ⭐⭐⭐ | URL device, latence USB |
| **OBDb** | ⭐⭐⭐ | Format JSON commands/signals |
| **Discovery 2 Technical Academy** | ⭐⭐⭐⭐⭐ | Adresses ECU, PIDs LR officiels |
| **DiscoTD5.com ECU Tech** | ⭐⭐⭐⭐⭐ | Reverse engineering TD5, fréquence réelle, brick-proof, bugs Nanocom |


---

## 9. Ekaitza_Itzali (EA2EGA)

**Lien :** https://github.com/EA2EGA/Ekaitza_Itzali
**Nom :** "Ekaitza Itzali" = "Éteindre la tempête" en basque (Euskara)
**Auteur :** Xabier Garmendia Iztueta, Gipuzkoa (Pays Basque)
**Langage :** JavaScript (Node.js)
**Licence :** Non précisée
**Activité :** 36 stars · 11 forks · référencé par Td5OpenDiag et TD5Tester
**Pertinence :** ⭐⭐⭐⭐⭐ — **Découverte critique** : révèle l'authentification Seed-Key manquante dans notre architecture

---

### Architecture globale

Application Node.js qui communique directement avec l'ECU TD5 via K-Line **sans ELM327 intermédiaire**. Implémente ISO 9141-2 en bare-metal sur port série Node.js (`serialport` npm), incluant le mode diagnostic fabricant Land Rover et l'authentification propriétaire Seed-Key.

```
Browser UI (HTML/JS)
      ↓
Node.js backend
      ↓
npm serialport (accès port série direct)
      ↓
K-Line interface (VAG KKL ou équivalent)
      ↓
ISO 9141-2 / KWP2000 — mode fabricant LR
      ↓
ECU TD5 (mode diagnostic fabricant 0x10 0xa0)
```

Pas de couche ELM327. Le protocole ISO 9141-2 complet est implémenté en JavaScript, incluant les timings (fast init 25ms), les checksums, et la machine d'états de session.

---

### Feature cruciale : authentification Seed-Key TD5

**C'est le point le plus important de ce projet pour DiagRover.**

Le mode diagnostic fabricant Land Rover (nécessaire pour fuelling, switches, settings, reflash) n'est **pas accessible via les commandes OBD-II standard**. Il exige une session de type `0x10 0xa0` (Start Diagnostic Session — manufacturer specific) suivie d'une **authentification challenge-response propriétaire** :

```
─── Séquence complète d'init ECU TD5 (mode fabricant) ───

Diag → K-Line LOW pendant 25ms              ← fast init
Diag → K-Line HIGH pendant 25ms
Diag → switch à 10400 baud

Diag → ECU : 0x81 0x13 0xF7 0x81 (0x0C)   ← trame init
ECU  → Diag : 0x03 0xC1 0x57 0x8F (0xAA)  ← ACK ECU

Diag → ECU : 0x02 0x10 0xA0 (0xB2)         ← start diag session fabricant
ECU  → Diag : 0x01 0x50 (0x51)             ← OK

Diag → ECU : 0x02 0x27 0x01 (0x2A)         ← seed request
ECU  → Diag : 0x04 0x67 0x01 [SL] [SH] (xx) ← seed 2 octets

# -- calcul de la clé via algorithme td5keygen --
key = td5keygen(seed_high << 8 | seed_low)
Key_H = key >> 8
Key_L = key & 0xFF

Diag → ECU : 0x04 0x27 0x02 [KH] [KL] (xx) ← key response
ECU  → Diag : 0x02 0x67 0x02 (0x6B)         ← AUTH OK → session ouverte
```

**Sans cette séquence, l'ECU refuse tout accès au mode fabricant.** Les commandes OBD-II standard (RPM, vitesse via mode 0x01) restent accessibles, mais les paramètres spécifiques TD5 (fuelling, switches, injecteurs, reflash) nécessitent impérativement le mode 0x10 0xa0 + Seed-Key.

---

### Algorithme td5keygen — détails techniques

Référence : https://github.com/pajacobson/td5keygen (C)
Obtenu par disassembly du firmware ECU par OffTrack.

L'algorithme prend un seed 16 bits (big-endian) et retourne une clé 16 bits :

```c
/* keygen.c — extrait (pajacobson/td5keygen) */
/* Input  : seed 16 bits = (high_byte << 8) | low_byte */
/* Output : key  16 bits → à découper en high/low pour transmission */

uint16_t td5_keygen(uint16_t seed);  /* prototype — algo dans keygen.c */

/* Utilisation */
uint16_t seed = (seed_L_from_ECU << 8) | seed_H_from_ECU;
uint16_t key  = td5_keygen(seed);
uint8_t key_high = key >> 8;
uint8_t key_low  = key & 0xFF;
/* Envoyer : 0x27 0x02 key_high key_low */
```

DiscoTD5 a validé cet algorithme contre 65 228 paires seed/key — précision confirmée.

---

### Features & état de complétion

| Feature | Statut dans Ekaitza_Itzali | Notes |
|---|---|---|
| Read Fuelling | **110% done** | Plus de paramètres que le Nanocom |
| Read Switches | 95% done | Données boîte auto manquantes |
| Read/Write Settings | 30% done | VIN, variantes fuel/map |
| Read/Clear Faults (DTC) | Done | Standard |
| NNN reflashing | Décrit | Firmware ECU complet |
| EGR / Wastegate | À tester | Paramètres présents |

"110% done" sur le fuelling signifie que le projet expose **plus de paramètres que le Nanocom** — c'est l'objectif DiagRover.

---

### Liste des paramètres fuelling documentés

Ekaitza_Itzali expose via la session fabricant des paramètres non accessibles en OBD-II standard :

| Paramètre | Mode | Disponible Nanocom |
|---|---|---|
| Fuelling demand | Fabricant | ✅ |
| Actual fuelling | Fabricant | ✅ |
| EGR position | Fabricant | ✅ |
| Wastegate modulator | Fabricant | ⚠️ à tester |
| Throttle tracks 1 & 2 | Fabricant | ✅ |
| Injector balance rates | Fabricant | ✅ |
| Fuel temperature | Fabricant | ✅ |
| Boost pressure (réel) | Fabricant | ✅ |
| Airmass (mg/stroke) | Fabricant | ✅ |
| All input switches | Fabricant | ✅ |

---

### Impact sur l'architecture DiagRover

#### Ce que le STN1110 peut faire (via STPX)

Bonne nouvelle : le STN1110 supporte l'envoi de **trames raw** via la commande `STPX`. Il est possible d'implémenter toute la séquence Seed-Key en passant par le STN1110 comme transceiver K-Line physique, avec la logique côté Nano ou PC :

```
# Étape 1 — trame init via STPX (STN1110)
STPX H:81 13 F7 81

# Étape 2 — start diag session fabricant
STPX H:02,D:10 A0

# Étape 3 — seed request
STPX H:02,D:27 01
→ Réponse : 67 01 [SL] [SH]

# Étape 4 — calcul clé dans Nano (C) ou PC (Python)
key = td5_keygen((SL << 8) | SH)

# Étape 5 — envoyer la clé
STPX H:04,D:27 02 [KH] [KL]
→ Réponse : 67 02 → AUTH OK
```

Le Nano calcule la clé en C (keygen.c est portable). La logique de la machine d'états de session est dans le firmware Nano.

#### ⚠️ Vigilance critique pour DiagRover

**La session OBD-II standard (ATSP4 + 010C) ne donne accès qu'à un sous-ensemble de paramètres.** Le mode fabricant (0x10 0xa0 + Seed-Key) est obligatoire pour :
- Fuelling, EGR, Wastegate, injecteurs
- Lecture/écriture des settings ECU
- Programmation codes injecteurs
- Reflash NNN

**Sans td5keygen intégré, DiagRover ne peut pas dépasser les capacités d'un ELM327 générique.** C'est la différence entre un outil de diagnostic de base et un équivalent TestBook.

---

### Ce qui est directement réutilisable

- **Séquence d'init complète** avec toutes les trames (checksums inclus)
- **Algorithme td5keygen** (C portable → à porter en Python et en C++ Nano)
- **Liste des paramètres fuelling** accessibles en mode fabricant
- **Architecture Node.js sans ELM327** — valide le concept direct ISO14230

---

### Projets connexes référencés

| Projet | Rôle |
|---|---|
| https://github.com/pajacobson/td5keygen | Algorithme Seed-Key en C (issu du disassembly ECU) |
| http://luca72.xoom.it/td5mapsuiteweb/archive/td5opencom/ | Interface diagnostic sur Arduino Mega 2650 (Luca72) |

---

## Synthèse finale — 9 projets

| Projet | Contribution principale |
|---|---|
| **Ekaitza_Itzali** ← NOUVEAU | **Seed-Key auth obligatoire · init fabricant complète · paramètres fuelling** |
| DiscoTD5.com | Timing ECU, >4Hz, NNN/MSB, brick-proof |
| Td5OpenDiag-android | ATSP5 LR, keep-alive, parsing trames |
| python-OBD | OBDCommand déclaratif, Async callbacks |
| CanCat | Architecture firmware, scan incrémental |
| pyftdi | URL device, latence USB |
| OBDb | Format JSON commands/signals |
| Discovery 2 Technical Academy | Adresses ECU officielles, PIDs LR |

### Priorité d'implémentation mise à jour

Suite à la découverte du Seed-Key, la roadmap Phase 1 doit être amendée :

**Phase 1 — MVP (amendé) :**
- Connexion + init STN1110
- Lecture DTC (OBD-II standard) — sans Seed-Key
- Live data 7 PIDs OBD-II standard

**Phase 1b — Mode fabricant (nouveau) :**
- Intégration td5keygen (C → firmware Nano)
- Séquence init fabricant 0x10 0xa0 via STPX
- Paramètres fuelling TD5 complets

**Phase 2 — Parité TestBook :**
- Actuations, SLS, BCU, Immo, calibrations

