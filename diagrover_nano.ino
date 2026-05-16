// ═══════════════════════════════════════════════════════════════
// DiagRover — diagrover_nano.ino
// Firmware principal · Arduino Nano 33 BLE (nRF52840)
// ═══════════════════════════════════════════════════════════════
//
// Architecture :
//   setup()  → init STN1110 (bloquant, une seule fois)
//   loop()   → non-bloquant : poll USB + poll STN1110 + keep-alive
//
// Communication PC : USB CDC JSON lines @ 115200
// Communication STN1110 : UART Serial1 @ 115200 (après négociation)
//
// ═══════════════════════════════════════════════════════════════

#include "config.h"
#include "stn_driver.h"
#include "kwp_session.h"
#include "usb_comm.h"
#include "live_data.h"

// ── Objets principaux ─────────────────────────────────────────
STNDriver  stn;
KWPSession session(stn);

// ── État live data ────────────────────────────────────────────
static bool     live_running  = false;
static uint8_t  live_pid_idx  = 0;
static uint32_t live_last_req = 0;
static uint16_t live_rate_ms  = 500;  // 500ms entre chaque PID → ~2Hz par PID

// ── Callback réponse live data ────────────────────────────────
void on_live_data(const uint8_t* resp, uint8_t len) {
    if (len < 3) return;
    // Format réponse : [LEN][0x61][LID][DATA...][CS]
    // Après parse_hex dans kwp_session, on a les bytes bruts
    uint8_t lid  = resp[2];
    const uint8_t* data = resp + 3;
    uint8_t dlen = (len > 4) ? len - 4 : 0;  // -4 : len, sid, lid, cs
    dispatch_live_data(lid, data, dlen);
}

// ── Callback session ready ────────────────────────────────────
void on_session_ready(bool success, const char* msg) {
    if (success) {
        usb_send_status("ok", "session_open");
        // Passer en mode live data par défaut
        stn.send(ATST_LIVEDATA);  // ATST20 = 80ms pour TD5 live
    } else {
        usb_send_error("SESSION_FAILED", msg);
    }
}

// ── Dispatch commandes PC ─────────────────────────────────────
void handle_pc_command() {
    const char* cmd = usb_get_cmd();

    // ── init : ouvrir session KWP2000 fabricant LR ──
    if (strcmp(cmd, "init") == 0) {
        session.begin_session(on_session_ready);
        usb_send_ack("init", "starting");
    }

    // ── live_start : démarrer acquisition live data ──
    else if (strcmp(cmd, "live_start") == 0) {
        live_rate_ms  = (uint16_t)usb_get_int("rate_ms", 500);
        live_pid_idx  = 0;
        live_running  = true;
        live_last_req = 0;
        stn.send(ATST_LIVEDATA);  // ATST20 pour TD5
        usb_send_ack("live_start");
    }

    // ── live_stop ──
    else if (strcmp(cmd, "live_stop") == 0) {
        live_running = false;
        stn.send(ATST_DIAG);  // revenir en ATST96
        usb_send_ack("live_stop");
    }

    // ── read_pid : lire un Local ID unique ──
    else if (strcmp(cmd, "read_pid") == 0) {
        uint8_t lid = (uint8_t)usb_get_int("lid", 0);
        if (lid != 0 && session.is_open()) {
            session.read_local_id(lid, on_live_data);
            usb_send_ack("read_pid");
        } else {
            usb_send_error("NOT_READY", "no session or invalid lid");
        }
    }

    // ── actuate : IOControl SID 0x30 ──
    else if (strcmp(cmd, "actuate") == 0) {
        uint8_t lid = (uint8_t)usb_get_int("lid", 0);
        uint8_t val = (uint8_t)usb_get_int("val", 0xFF);
        if (session.is_open()) {
            session.io_control(lid, val);
            usb_send_ack("actuate");
        } else {
            usb_send_error("NOT_READY", "no session");
        }
    }

    // ── routine : StartRoutine SID 0x31 ──
    else if (strcmp(cmd, "routine") == 0) {
        uint8_t lid   = (uint8_t)usb_get_int("lid", 0);
        uint8_t param = (uint8_t)usb_get_int("param", 0);
        if (session.is_open()) {
            session.start_routine(lid, param);
            usb_send_ack("routine");
        } else {
            usb_send_error("NOT_READY", "no session");
        }
    }

    // ── set_mode : changer ATST ──
    else if (strcmp(cmd, "set_mode") == 0) {
        const char* mode = usb_get_param("mode");
        if (mode) {
            if      (strcmp(mode, "livedata") == 0) stn.send(ATST_LIVEDATA);
            else if (strcmp(mode, "diag")     == 0) stn.send(ATST_DIAG);
            else if (strcmp(mode, "flash")    == 0) stn.send(ATST_FLASH);
            usb_send_ack("set_mode", mode);
        }
    }

    // ── raw_at : commande AT directe (debug) ──
    else if (strcmp(cmd, "raw_at") == 0) {
        const char* at = usb_get_param("at");
        if (at && !stn.is_busy()) {
            stn.send(at);
            usb_send_ack("raw_at");
        } else {
            usb_send_error("BUSY", "stn busy or no at param");
        }
    }

    // ── ping : sanity check ──
    else if (strcmp(cmd, "ping") == 0) {
        char msg[32];
        snprintf(msg, sizeof(msg), "DiagRover fw %s", FW_VERSION);
        usb_send_status("ok", msg);
    }

    else {
        usb_send_error("UNKNOWN_CMD", cmd);
    }
}

// ── Live data loop ────────────────────────────────────────────
void run_live_data() {
    if (!live_running || !session.is_open() || session.is_busy()) return;

    uint32_t now = millis();
    if (now - live_last_req < live_rate_ms) return;

    uint8_t lid = LIVE_CYCLE_PAGE2[live_pid_idx];
    session.read_local_id(lid, on_live_data);

    live_pid_idx = (live_pid_idx + 1) % LIVE_CYCLE_LEN;
    live_last_req = now;
}

// ─────────────────────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
    // USB CDC
    Serial.begin(USB_BAUD);

    // Libérer D13 (partagé avec LED built-in nRF52840)
    pinMode(LED_BUILTIN, INPUT);

    // Attendre connexion USB (optionnel, timeout 3s)
    uint32_t t0 = millis();
    while (!Serial && millis() - t0 < 3000);

    usb_send_status("info", "DiagRover booting...");

    // Init STN1110 (bloquant ~3s)
    usb_send_status("info", "Initializing STN1110...");
    if (stn.init_blocking()) {
        usb_send_status("ok", "STN1110 ready");
    } else {
        usb_send_error("STN_INIT_FAIL", "check wiring");
        // On continue quand même — le PC peut retenter
    }

    usb_send_status("ok", "DiagRover ready — waiting for commands");
}

// ─────────────────────────────────────────────────────────────
// LOOP — 100% non-bloquant
// ─────────────────────────────────────────────────────────────
void loop() {
    // 1. Lire les réponses STN1110
    stn.poll();

    // 2. Lire les commandes USB PC
    if (usb_poll()) {
        handle_pc_command();
    }

    // 3. Keep-alive KWP2000 (timer interne KWPSession)
    session.poll();

    // 4. Live data cycle
    run_live_data();
}
