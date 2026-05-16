#pragma once
// ═══════════════════════════════════════════════════════════════
// DiagRover — config.h
// Nano 33 BLE (nRF52840) · Constantes et pinout
// ═══════════════════════════════════════════════════════════════

// ── Version firmware ──────────────────────────────────────────
#define FW_VERSION      "0.1.0"
#define FW_BUILD_DATE   __DATE__

// ── UART STN1110 (Serial1) ────────────────────────────────────
#define STN_SERIAL      Serial1
#define STN_BAUD_INIT   9600       // STN1110 démarre toujours à 9600 (non mémorisé)
#define STN_BAUD_RUN    115200     // baud de travail après négociation
#define STN_RESET_DELAY 1000       // ms post-ATZ obligatoire
#define STN_REBAUD_DELAY 100       // ms après STBR115200

// ── Timeouts STN1110 (ATST) ───────────────────────────────────
// Valeur en multiples de 4ms : ATST20 = 80ms, ATST96 = 384ms
#define ATST_LIVEDATA   "ATST20"   // 80ms  — P2 max TD5 = 50ms, marge ×1.6
#define ATST_DIAG       "ATST96"   // 384ms — ECU BCU/Immo lents
#define ATST_FLASH      "ATSFF"    // 1020ms — programmation ECU

// ── KWP2000 session ───────────────────────────────────────────
#define KWP_KEEPALIVE_MS  2500     // Envoyer 0x3E si inactif depuis >2500ms
#define KWP_SESSION_TIMEOUT 5000   // L'ECU ferme après 5s sans trame

// ── USB CDC (Serial) ──────────────────────────────────────────
#define USB_BAUD        115200
#define USB_BUF_SIZE    512        // Taille buffer JSON entrant

// ── VOM — ADC pins ────────────────────────────────────────────
#define VOM_PIN_A0      A0         // Pont diviseur 0–20V (33kΩ/5.6kΩ)
#define VOM_PIN_A1      A1         // Pont diviseur 0–15V (10kΩ/2.7kΩ)
#define VOM_PIN_A2      A2         // Entrée directe 0–3.3V / fréquence
#define VOM_ADC_BITS    12
#define VOM_VREF        3.3f

// Ratios des ponts diviseurs (R1+R2)/R2
#define VOM_RATIO_A0    ((33.0f + 5.6f) / 5.6f)   // 6.964
#define VOM_RATIO_A1    ((10.0f + 2.7f) / 2.7f)   // 4.704
#define VOM_RATIO_A2    1.0f                        // direct

// ── INA219 (courant) ──────────────────────────────────────────
#define INA219_ADDR     0x40       // A0=GND A1=GND → adresse par défaut

// ── LED status ────────────────────────────────────────────────
// D13 = LED built-in partagé avec SCK — forcer en INPUT pour libérer
#define LED_STATUS      LED_BUILTIN

// ── Mode debug ────────────────────────────────────────────────
// Décommenter pour activer les logs AT bruts vers USB
// #define DEBUG_AT

// ── États machine ─────────────────────────────────────────────
typedef enum {
    STATE_IDLE = 0,
    STATE_INIT_STN,
    STATE_WAIT_VEHICLE,
    STATE_KWP_INIT,
    STATE_KWP_AUTH,
    STATE_SESSION_OPEN,
    STATE_ERROR
} diagrover_state_t;
