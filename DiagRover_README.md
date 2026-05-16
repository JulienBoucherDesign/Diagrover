# DiagRover — Fonctionnalités complètes
### Land Rover Discovery 2 · Range Rover (1998–2004) · ECU TD5 / GEMS V8

---

## Matériel nécessaire (~77€)

| Pièce | Prix |
|---|---|
| Arduino Nano 33 BLE | ~22€ |
| SparkFun OBD-II UART (STN1110) | ~35€ |
| Câble DB9 → J1962 OBD ⚠️ non inclus avec SparkFun | ~3€ |
| Shield proto + composants VOM | ~10€ |
| Câble USB-A → Micro-USB | ~2€ |
| Divers | ~5€ |
| **Total** | **~77€** |

Branchement : `PC ──USB──► Nano 33 BLE ──UART──► STN1110 ──DB9──► Prise OBD J1962`

---

## Diagnostic

### Codes défauts (DTC)
- Lire tous les codes défauts actifs sur **tous les modules simultanément** (moteur, carrosserie, freins, suspension, immobiliseur)
- Lire les codes mémorisés (historique)
- Afficher la description en clair pour chaque code
- Afficher le **freeze frame** — état du moteur au moment où la panne s'est déclenchée (régime, température, vitesse...)
- Effacer les codes après réparation
- Exporter le rapport en PDF ou CSV

### Identification véhicule
- Lire le **VIN** complet
- Identifier le type d'ECU (**NNN** ou **MSB**) — important avant toute programmation
- Lire la variante de cartographie moteur (map variant)
- Lire la variante carburant (fuel variant)
- Lire le code d'homologation marché
- Lire la version firmware ECU

---

## Données en temps réel

### Moteur TD5
- Régime moteur (RPM)
- Vitesse véhicule (km/h)
- Tension batterie (V)
- Température liquide refroidissement (°C)
- Température carburant (°C)
- Température air admission (°C)
- 5 températures supplémentaires (capteurs moteur)
- Pression MAP / turbo (mbar)
- Pression ambiante (mbar)
- Débit air (MAF)
- Position papillon — 4 pistes de mesure (V)
- Modulation EGR (%)
- Position EGR inlet (%)
- **Balance de puissance** — contribution de chaque cylindre (1 à 5)
- Erreur de régime calculée

### Moteur GEMS V8 (4.0 / 4.6)
- Régime moteur, vitesse, températures
- Richesse mélange (lambda)
- Sondes O2 amont / aval
- Avance allumage (°)
- Trim carburant court terme / long terme
- Charge moteur calculée (%)

### Suspension SLS
- Hauteur caisse sur les 4 coins (mm)
- Mode actif (Normal / High / Low / Access)
- État compresseur (on/off)
- État électrovannes (ouvert/fermé)

### ABS / ETC
- Vitesse roue avant gauche / droite / arrière gauche / droite (km/h)
- Déclenchement ABS actif
- Déclenchement contrôle de traction actif

### Entrées / Switches
- Frein 1 (pédale, interrupteur B16)
- Frein 2 (interrupteur B10)
- Pédale d'embrayage (B35)
- Régulateur de vitesse : master / set / resume (B15 / B11 / B17)
- Demande compresseur AC (B9)
- Demande ventilateur AC (B23)
- Rapport de transfert (A33)
- Données boîte automatique (position sélecteur, température ATF...)

### Affichage et enregistrement
- Jauges graphiques en temps réel
- Courbes avec historique glissant (30s / 5min / session)
- Sélection libre des paramètres à afficher
- Alertes seuils paramétrables (ex : température > 100°C)
- **Enregistrement de session** (data logging CSV)
- Rejeu d'une session enregistrée
- Fréquence jusqu'à 5 Hz sur K-Line, 10 Hz sur CAN

---

## Commandes et tests (actuations)

### Sorties moteur
- Pompe à carburant (on/off)
- Bougies de préchauffage (on/off)
- Vanne EGR — ouverture forcée (%)
- Modulateur wastegate turbo (% duty cycle)
- Modulateur EGR inlet (% duty cycle)

### Éclairage et signalisation
- Témoin moteur MIL (on/off)
- Jauge température tableau de bord (on/off)
- Compteur de tours pulse (on/off)

### Climatisation
- Embrayage compresseur AC (on/off)
- Ventilateur AC (on/off)

### Suspension SLS
- Monter / descendre chaque coin indépendamment
- Forcer le mode accès (position basse)
- Forcer le mode haute garde au sol
- Activer le compresseur
- Tester chaque électrovanne individuellement

### ABS
- Tester la pompe ABS
- Tester chaque électrovanne de roue
- Procédure de purge freins assistée (ABS pump)

### Carrosserie (BCU)
- Verrouillage / déverrouillage portes
- Test klaxon
- Test phares / feux

### Test injecteurs (Power Balance)
- Couper chaque injecteur individuellement (1 à 5)
- Mesurer la chute de régime par cylindre
- Identifier l'injecteur défaillant sans dépose moteur

---

## Réglages ECU

### Lecture
- Tous les paramètres de cartographie actifs (tune settings block)
- Codes d'ajustement injecteurs (injector idle codes)
- Type d'accélérateur (2 voies ou 3 voies)
- Codes de sécurité (security code learning)

### Écriture
- Modifier le type d'accélérateur (2-Way ↔ 3-Way)
- Programmer les codes d'ajustement injecteurs (A–U selon type map 10P/15P)
- Reset des adaptations moteur (trim carburant, apprentissage papillon)
- Reset intervalle de service (vidange, révision)
- **Effacement voyants** — extinction forcée des témoins ABS, SLS, ACE, moteur, carrosserie après réparation ou modification

### Immobiliseur & Clés
- Lire l'état de l'immobiliseur
- **Coder une nouvelle clé** — associer une clé vierge ou de remplacement à l'ECU (procédure apprentissage sécurisé)
- Programmer jusqu'à 4 clés sur le même véhicule
- Supprimer une clé perdue de la mémoire ECU
- Reset immobiliseur après remplacement ECU moteur
- Lire le code de sécurité (security code) nécessaire pour l'apprentissage clé

### Ouverture et verrouillage via logiciel
- **Verrouiller / déverrouiller les portes** directement depuis le PC (commande BCU)
- Ouvrir le véhicule sans clé physique — utile en cas de clé perdue ou de télécommande défaillante
- Vérifier l'état de verrouillage de chaque porte
- Commander l'ouverture du coffre

### Codage ECU (ZCS)
- Lire le codage Zone (options véhicule)
- Écrire le ZCS sur un ECU de remplacement
- Coder le VIN sur un ECU neuf
- Cloner la configuration d'un ECU vers un autre

---

## Procédures guidées

Chaque procédure se déroule **étape par étape** avec validation à chaque étape :

- **Calibration suspension SLS** — après remplacement d'un capteur de hauteur
- **Apprentissage papillon** — après nettoyage ou remplacement du corps de papillon
- **Purge freins** — avec activation séquentielle des vannes ABS
- **Reset service** — réinitialisation kilométrage entretien
- **Remplacement BCU** — procédure de codage d'un BCU neuf (5 étapes)
- **Remplacement ECU moteur** — séquence VIN + immobiliseur
- **Codage nouvelle clé** — associer une clé vierge ou de remplacement, supprimer une clé perdue
- **Association télécommandes** — jusqu'à 4 télécommandes

---


## Conversions et suppressions d'options

Indispensable lors de conversions mécaniques ou suppressions de systèmes.

### Suppression suspension pneumatique (SLS delete)
Quand la suspension pneumatique est remplacée par des ressorts mécaniques, le BCU continue de détecter l'absence du système SLS et maintient les voyants d'alerte allumés en permanence. DiagRover permet de :
- Désactiver l'option SLS dans le **ZCS (Zone Coding System)** du BCU
- Effacer tous les codes défauts SLS résiduels
- Éteindre définitivement les voyants liés à la suspension pneumatique
- Valider que le BCU ne génère plus de codes SLS après conversion

### Suppression ACE (Active Cornering Enhancement)
Même procédure lors de la dépose du système ACE :
- Désactiver l'option ACE dans le ZCS du BCU
- Effacer les codes défauts ACE
- Extinction des voyants associés

### Effacement voyants de tableau de bord
Extinction ciblée des voyants qui restent allumés après intervention ou conversion :
- Voyant ABS — après remplacement d'un capteur ABS ou conversion freins
- Voyant SLS — après SLS delete
- Voyant ACE — après suppression ACE
- Voyant moteur (MIL) — après réparation défaut moteur
- Voyant carrosserie — après intervention BCU
- Tous les voyants simultanément (effacement global tous modules)

> **Note :** l'effacement des voyants sans réparation préalable est temporaire — les codes reviendront si la cause n'est pas traitée. Les suppressions d'options ZCS (SLS, ACE) sont définitives tant que le BCU n'est pas réinitialisé.

## Programmation ECU (Phase 3)

*Disponible uniquement sur ECU NNN*

- Sauvegarde complète du firmware ECU (backup avant toute intervention)
- Lecture mémoire flash par adresse (SID 0x23)
- Reprogrammation cartographie moteur (flashage)
- Mécanisme brick-proof — l'ECU ne peut booter qu'après une écriture complète et vérifiée

---

## Multimètre intégré (VOM)

Le shield Nano dispose d'un multimètre intégré, sans instrument séparé :

- **Voltmètre DC** — 3 plages : 0–3.3V / 0–15V / 0–20V
- **Ohmmètre** — via pont de Wheatstone, plage 100Ω–100kΩ
- **Test de continuité** — bip sonore
- **Ampèremètre** — 0–3.2A via module INA219
- **Fréquencemètre** — signal injecteur, capteurs PWM (résolution 15 ns)
- Calibration par canal (tension de référence connue)
- Historique des mesures
- Export CSV

---

## Rapports et journal de bord

- **Rapport diagnostic PDF** — codes défauts + descriptions + freeze frame + données live + recommandations
- **Journal de bord véhicule** — historique de toutes les sessions par VIN
- Suivi kilométrage et date par intervention
- Comparaison avec la session précédente (mêmes codes ?)
- Notes libres par session
- Export CSV des données live

---

## Gestion multi-véhicules

- Profils sauvegardés par VIN
- Type ECU mémorisé (NNN/MSB) — évite la détection à chaque connexion
- Protocoles mémorisés par module (ATSP4 pour TD5, ATSP5 pour BCU...)
- Historique des sessions par véhicule

---

## Véhicules et protocoles supportés

| Module | Protocole | MY |
|---|---|---|
| ECU moteur TD5 | KWP2000 fast init | 98–04 |
| ECU moteur GEMS V8 | ISO 9141-2 | 98–04 |
| BCU carrosserie | CAN (MY02+) / K-Line (MY98-01) | 98–04 |
| ABS / ETC | CAN | 98–04 |
| Suspension SLS | CAN | 98–04 |
| Immobiliseur | KWP2000 slow init | 98–04 |

---

## Ce qui n'est pas prévu

- Moteurs hors Discovery 2 / Range Rover P38 de cette génération
- Véhicules post-2004 (architecture électronique différente)
- Reprogrammation de la cartographie moteur sur mesure *(pas un outil de tuning)*
