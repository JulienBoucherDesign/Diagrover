// ═══════════════════════════════════════════════════════════════
// DiagRover — stn_driver.cpp
// Driver STN1110 non-bloquant
// ═══════════════════════════════════════════════════════════════
#include "stn_driver.h"

// ── Init bloquante (setup() uniquement) ──────────────────────

bool STNDriver::init_blocking() {
    // ── Étape 1 : démarrer à 9600 (STN1110 toujours à 9600 au boot) ──
    STN_SERIAL.begin(STN_BAUD_INIT);
    delay(100);

    // Vider le buffer
    while (STN_SERIAL.available()) STN_SERIAL.read();

    // Reset STN1110
    if (!_send_blocking("ATZ", 3000)) return false;
    delay(STN_RESET_DELAY);

    // ── Étape 2 : passer à 115200 ────────────────────────────
    if (!_send_blocking("STBR115200", 500)) return false;
    delay(STN_REBAUD_DELAY);

    STN_SERIAL.end();
    STN_SERIAL.begin(STN_BAUD_RUN);
    delay(100);

    // Confirmer à 115200
    if (!_send_blocking("ATZ", 2000)) return false;
    delay(500);

    // ── Étape 3 : configuration ───────────────────────────────
    struct { const char* cmd; uint32_t ms; } cfg[] = {
        {"ATE0",    200},   // no echo
        {"ATL0",    200},   // no linefeed
        {"ATH1",    200},   // headers ON — indispensable pour parser les réponses
        {"ATS0",    200},   // no spaces
        {"ATCAF1",  200},   // CAN auto format — reassemble multi-frame ISO-TP
        {"ATAL",    200},   // allow long messages
        {ATST_DIAG, 200},   // timeout 384ms (mode diagnostic par défaut)
        {"ATRV",    500},   // sanity check — tension batterie
    };

    for (auto& c : cfg) {
        if (!_send_blocking(c.cmd, c.ms + 500)) {
            // Non bloquant sur ATRV (véhicule peut ne pas être branché)
            if (strcmp(c.cmd, "ATRV") != 0) return false;
        }
        delay(c.ms);
    }

    _ready = true;
    return true;
}

// ── Envoi non-bloquant ────────────────────────────────────────

bool STNDriver::send(const char* cmd) {
    if (_waiting) return false;  // half-duplex : une seule commande à la fois

    _buf_len = 0;
    memset(_buf, 0, sizeof(_buf));
    strncpy(_last_cmd, cmd, sizeof(_last_cmd) - 1);

    STN_SERIAL.println(cmd);

    _waiting  = true;
    _sent_at  = millis();

#ifdef DEBUG_AT
    Serial.print("[AT→] "); Serial.println(cmd);
#endif
    return true;
}

bool STNDriver::send_raw(const uint8_t* bytes, uint8_t len) {
    if (_waiting) return false;

    // Construire une chaîne hex : "STPX D:02 10 A0 B2"
    // Pour les trames KWP2000 raw on utilise STPX sans header
    char cmd[128] = "STPX D:";
    char* p = cmd + 7;
    for (uint8_t i = 0; i < len; i++) {
        if (i > 0) *p++ = ' ';
        sprintf(p, "%02X", bytes[i]);
        p += 2;
    }
    *p = '\0';
    return send(cmd);
}

// ── Poll non-bloquant (loop()) ────────────────────────────────

void STNDriver::poll() {
    // Lire les bytes disponibles
    while (STN_SERIAL.available()) {
        char c = (char)STN_SERIAL.read();

        if (c == '>') {
            // Prompt '>' = réponse complète
            _process_response();
            _waiting = false;
            return;
        }

        if (c == '\r') continue;  // ignorer CR

        if (_buf_len < STN_RESP_MAX - 1) {
            _buf[_buf_len++] = c;
        }
    }

    // Vérifier timeout
    if (_waiting && (millis() - _sent_at > _timeout_ms)) {
        _buf[_buf_len] = '\0';
#ifdef DEBUG_AT
        Serial.print("[AT TIMEOUT] "); Serial.println(_last_cmd);
#endif
        if (_timeout_cb) _timeout_cb(_last_cmd);
        _waiting  = false;
        _buf_len  = 0;
    }
}

// ── Traitement réponse ────────────────────────────────────────

void STNDriver::_process_response() {
    _buf[_buf_len] = '\0';

    // Supprimer les LF et espaces de tête/queue
    char* start = _buf;
    while (*start == '\n' || *start == ' ') start++;
    char* end = start + strlen(start) - 1;
    while (end > start && (*end == '\n' || *end == ' ' || *end == '\r'))
        *end-- = '\0';

#ifdef DEBUG_AT
    Serial.print("[AT←] "); Serial.println(start);
#endif

    if (_resp_cb) _resp_cb(start, strlen(start));
    _buf_len = 0;
}

// ── Helpers bloquants (init uniquement) ──────────────────────

bool STNDriver::_send_blocking(const char* cmd, uint32_t timeout_ms) {
    while (STN_SERIAL.available()) STN_SERIAL.read();
    STN_SERIAL.println(cmd);

    uint32_t t0 = millis();
    String resp = "";

    while (millis() - t0 < timeout_ms) {
        if (STN_SERIAL.available()) {
            char c = STN_SERIAL.read();
            if (c == '>') return true;  // prompt = succès
            resp += c;
        }
    }
    return false;
}

bool STNDriver::_wait_for(const char* expected, uint32_t timeout_ms) {
    uint32_t t0 = millis();
    String resp = "";
    while (millis() - t0 < timeout_ms) {
        if (STN_SERIAL.available()) {
            char c = STN_SERIAL.read();
            if (c == '>') break;
            resp += c;
        }
    }
    return resp.indexOf(expected) >= 0;
}
