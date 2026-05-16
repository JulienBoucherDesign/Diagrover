// ═══════════════════════════════════════════════════════════════
// DiagRover — kwp_session.cpp
// Gestionnaire de session KWP2000 fabricant LR
// ═══════════════════════════════════════════════════════════════
#include "kwp_session.h"
#include "usb_comm.h"

KWPSession* KWPSession::_instance = nullptr;

// ── Démarrage session ─────────────────────────────────────────

void KWPSession::begin_session(kwp_ready_cb_t cb) {
    _ready_cb = cb;
    _state    = KWP_SENDING_INIT;
    _instance = this;

    _stn.on_response(_on_stn_resp);
    _stn.on_timeout(_on_stn_timeout);

    // Sélectionner ATSP4 (KWP2000 fast init TD5)
    // Le fallback ATSP5 est géré par poll() si NO DATA
    _stn.send("ATSP4");
}

// ── Poll ──────────────────────────────────────────────────────

void KWPSession::poll() {
    // Keep-alive : envoyer 0x3E si session ouverte et inactif depuis >2500ms
    if (_state == KWP_SESSION_OPEN && !_stn.is_busy()) {
        if (millis() - _last_cmd > KWP_KEEPALIVE_MS) {
            _send_keepalive();
        }
    }
}

// ── Commandes utilisateur ─────────────────────────────────────

bool KWPSession::read_local_id(uint8_t lid, kwp_data_cb_t cb) {
    if (!is_open() || is_busy()) return false;
    _data_cb = cb;
    _last_cmd = millis();
    uint8_t data[] = {lid};
    return _send_kwp(0x21, data, 1);
}

bool KWPSession::io_control(uint8_t lid, uint8_t val, kwp_data_cb_t cb) {
    if (!is_open() || is_busy()) return false;
    _data_cb = cb;
    _last_cmd = millis();
    uint8_t data[] = {lid, val};
    return _send_kwp(0x30, data, 2);
}

bool KWPSession::start_routine(uint8_t lid, uint8_t param, kwp_data_cb_t cb) {
    if (!is_open() || is_busy()) return false;
    _data_cb = cb;
    _last_cmd = millis();
    uint8_t data[] = {lid, param};
    uint8_t dlen = (param == 0 && lid == 0xDD) ? 1 : 2;
    return _send_kwp(0x31, data, dlen);
}

bool KWPSession::send_raw(const uint8_t* frame, uint8_t len, kwp_data_cb_t cb) {
    if (!is_open() || is_busy()) return false;
    _data_cb = cb;
    _last_cmd = millis();
    return _stn.send_raw(frame, len);
}

// ── Constructeur trame KWP2000 ────────────────────────────────

bool KWPSession::_send_kwp(uint8_t sid, const uint8_t* data, uint8_t dlen,
                             kwp_data_cb_t cb) {
    if (cb) _data_cb = cb;

    // Frame : [LEN][SID][DATA...][CS]
    uint8_t frame[32];
    uint8_t idx = 0;
    frame[idx++] = dlen + 1;     // LEN = SID + data
    frame[idx++] = sid;
    for (uint8_t i = 0; i < dlen; i++) frame[idx++] = data[i];
    frame[idx] = _cs(frame, idx);
    idx++;

    return _stn.send_raw(frame, idx);
}

// ── Keep-alive ────────────────────────────────────────────────

void KWPSession::_send_keepalive() {
    _stn.send_raw(KWP_TESTER_PRES, sizeof(KWP_TESTER_PRES));
    _last_cmd = millis();
}

// ── Callbacks STNDriver (statiques) ──────────────────────────

void KWPSession::_on_stn_resp(const char* resp, uint16_t len) {
    if (!_instance) return;

    uint8_t bytes[64];
    uint8_t blen = _parse_hex_response(resp, bytes, sizeof(bytes));

    switch (_instance->_state) {
        case KWP_SENDING_INIT:
            _instance->_handle_init_resp(bytes, blen);
            break;
        case KWP_SENDING_START_DIAG:
            _instance->_handle_start_diag_resp(bytes, blen);
            break;
        case KWP_WAITING_SEED:
            _instance->_handle_seed_resp(bytes, blen);
            break;
        case KWP_SENDING_KEY:
            _instance->_handle_key_resp(bytes, blen);
            break;
        case KWP_SESSION_OPEN:
            _instance->_handle_data_resp(bytes, blen);
            break;
        default:
            break;
    }
}

void KWPSession::_on_stn_timeout(const char* last_cmd) {
    if (!_instance) return;
    // Si timeout pendant l'init → tenter ATSP5 (fallback LR)
    if (_instance->_state == KWP_SENDING_INIT ||
        _instance->_state == KWP_SENDING_START_DIAG) {
        _instance->_stn.send("ATSP5");
        // Retenter l'init après changement de protocole
        usb_send_status("warn", "ATSP4 timeout — fallback ATSP5");
    } else if (_instance->_state == KWP_SESSION_OPEN) {
        // Timeout en session ouverte → session probablement fermée
        usb_send_status("error", "KWP session timeout — reinit needed");
        _instance->_state = KWP_ERROR;
    }
}

// ── Machine d'états — réponses ────────────────────────────────

void KWPSession::_handle_init_resp(const uint8_t* b, uint8_t len) {
    // Réponse attendue : 03 C1 57 8F AA (StartComm resp, KW1=0x57 KW2=0x8F)
    if (len >= 3 && b[1] == 0xC1) {
        _state = KWP_SENDING_START_DIAG;
        _stn.send_raw(KWP_START_DIAG, sizeof(KWP_START_DIAG));
    } else {
        // Essayer avec l'init frame
        _stn.send_raw(KWP_INIT_FRAME, sizeof(KWP_INIT_FRAME));
    }
}

void KWPSession::_handle_start_diag_resp(const uint8_t* b, uint8_t len) {
    // Réponse attendue : 01 50 51 (Session OK)
    if (len >= 2 && b[1] == 0x50) {
        _state = KWP_WAITING_SEED;
        _stn.send_raw(KWP_SEED_REQ, sizeof(KWP_SEED_REQ));
        usb_send_status("info", "KWP session started — requesting seed");
    } else {
        _set_error("StartDiagSession failed");
    }
}

void KWPSession::_handle_seed_resp(const uint8_t* b, uint8_t len) {
    // Réponse attendue : 04 67 01 [SH] [SL] [CS]
    if (len >= 5 && b[1] == 0x67 && b[2] == 0x01) {
        uint8_t seed_h = b[3];
        uint8_t seed_l = b[4];

        // Calculer et envoyer la clé
        uint8_t key_frame[6];
        td5_key_frame(seed_h, seed_l, key_frame);

        _state = KWP_SENDING_KEY;
        _stn.send_raw(key_frame, 6);

        // Log pour debug
        char msg[64];
        snprintf(msg, sizeof(msg), "seed=0x%02X%02X key=0x%02X%02X",
                 seed_h, seed_l, key_frame[3], key_frame[4]);
        usb_send_status("info", msg);
    } else {
        _set_error("SecurityAccess seed invalid");
    }
}

void KWPSession::_handle_key_resp(const uint8_t* b, uint8_t len) {
    // Réponse attendue : 02 67 02 6B (AUTH OK)
    if (len >= 3 && b[1] == 0x67 && b[2] == 0x02) {
        _state    = KWP_SESSION_OPEN;
        _last_cmd = millis();

        usb_send_status("ok", "KWP session authenticated");
        if (_ready_cb) _ready_cb(true, "session_open");
    } else if (len >= 3 && b[1] == 0x7F) {
        // NRC 0x35 = InvalidKey
        _set_error("SecurityAccess key rejected — NRC");
    } else {
        _set_error("SecurityAccess unexpected response");
    }
}

void KWPSession::_handle_data_resp(const uint8_t* b, uint8_t len) {
    // Réponses en session ouverte (live data, actuations, keep-alive...)
    _last_cmd = millis();

    // Ignorer les réponses TesterPresent (keep-alive silencieux)
    if (len >= 2 && b[1] == 0x7E) return;

    // Réponse négative (NRC)
    if (len >= 3 && b[1] == 0x7F) {
        uint8_t rejected_sid = b[2];
        uint8_t nrc_code     = b[3];
        // 0x7F 0x1A 0x10 = ReadECUID rejeté (GeneralReject)
        // Observé dans Settings.log — l'ECU rejette parfois 0x1A selon son état.
        // Traiter comme non-fatal et signaler au PC.
        char msg[48];
        snprintf(msg, sizeof(msg), "NRC sid=0x%02X nrc=0x%02X",
                 rejected_sid, nrc_code);
        // Transmettre au PC pour décision (retry ou continuer)
        usb_send_error("NRC", msg);
        // Ne pas fermer la session — l'ECU est toujours actif
        if (_data_cb) {
            _data_cb(nullptr, 0);  // signaler échec au callback appelant
            _data_cb = nullptr;
        }
        return;
    }

    // Transmettre les données au callback
    if (_data_cb) {
        _data_cb(b, len);
        _data_cb = nullptr;  // one-shot
    }
}

// ── Parser les réponses hex STN1110 ──────────────────────────

uint8_t KWPSession::_parse_hex_response(const char* resp,
                                          uint8_t* out, uint8_t max_len) {
    uint8_t count = 0;
    const char* p = resp;

    while (*p && count < max_len) {
        // Ignorer les séparateurs
        while (*p == ' ' || *p == '\n' || *p == '\r') p++;
        if (!*p) break;

        // Lire 2 caractères hex
        char hex[3] = {0};
        if (!isxdigit(p[0]) || !isxdigit(p[1])) { p++; continue; }
        hex[0] = p[0]; hex[1] = p[1];
        out[count++] = (uint8_t)strtol(hex, nullptr, 16);
        p += 2;
    }
    return count;
}

void KWPSession::_set_error(const char* msg) {
    _state = KWP_ERROR;
    usb_send_status("error", msg);
    if (_ready_cb) _ready_cb(false, msg);
}
