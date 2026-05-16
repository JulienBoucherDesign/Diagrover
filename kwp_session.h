#pragma once
// ═══════════════════════════════════════════════════════════════
// DiagRover — kwp_session.h
// Gestionnaire de session KWP2000 fabricant LR
// Séquence validée sur sniffings Ekaitza_Itzali (6 fichiers)
// ═══════════════════════════════════════════════════════════════
#include <Arduino.h>
#include "config.h"
#include "stn_driver.h"
#include "td5keygen.h"

// ── Trames KWP2000 pré-calculées (checksums validés) ─────────
// Format [LEN][SID][DATA...][CS] — CS = sum(tous octets) & 0xFF

// Init frame (header 3 octets) : 81 13 F7 81 0C
static const uint8_t KWP_INIT_FRAME[]    = {0x81, 0x13, 0xF7, 0x81, 0x0C};

// StartDiagSession(0xA0) : 02 10 A0 B2
static const uint8_t KWP_START_DIAG[]   = {0x02, 0x10, 0xA0, 0xB2};

// SecurityAccess RequestSeed : 02 27 01 2A
static const uint8_t KWP_SEED_REQ[]     = {0x02, 0x27, 0x01, 0x2A};

// TesterPresent (keep-alive) : 02 3E 01 41
static const uint8_t KWP_TESTER_PRES[]  = {0x02, 0x3E, 0x01, 0x41};

// Réponse attendue AUTH OK : 02 67 02 6B
static const uint8_t KWP_AUTH_OK[]      = {0x02, 0x67, 0x02, 0x6B};

typedef enum {
    KWP_IDLE = 0,
    KWP_SENDING_INIT,
    KWP_SENDING_START_DIAG,
    KWP_SENDING_SEED_REQ,
    KWP_WAITING_SEED,
    KWP_SENDING_KEY,
    KWP_SESSION_OPEN,
    KWP_ERROR
} kwp_state_t;

typedef void (*kwp_ready_cb_t)(bool success, const char* msg);
typedef void (*kwp_data_cb_t)(const uint8_t* resp, uint8_t len);

class KWPSession {
public:
    explicit KWPSession(STNDriver& stn) : _stn(stn) {}

    // Lance la séquence d'ouverture de session (non-bloquant)
    void begin_session(kwp_ready_cb_t cb = nullptr);

    // À appeler dans loop()
    void poll();

    // Envoie une commande ReadDataLocalID (SID 0x21)
    // lid = Local ID, cb = callback quand réponse reçue
    bool read_local_id(uint8_t lid, kwp_data_cb_t cb = nullptr);

    // Envoie une actuation IOControl (SID 0x30)
    bool io_control(uint8_t lid, uint8_t val = 0xFF, kwp_data_cb_t cb = nullptr);

    // Routine (SID 0x31)
    bool start_routine(uint8_t lid, uint8_t param = 0, kwp_data_cb_t cb = nullptr);

    // Envoie une trame raw KWP2000 (checksums déjà calculés)
    bool send_raw(const uint8_t* frame, uint8_t len, kwp_data_cb_t cb = nullptr);

    // État
    bool is_open() const { return _state == KWP_SESSION_OPEN; }
    bool is_busy() const { return _stn.is_busy(); }
    kwp_state_t state() const { return _state; }

private:
    STNDriver&    _stn;
    kwp_state_t   _state     = KWP_IDLE;
    uint32_t      _last_cmd  = 0;   // timestamp dernière commande (keep-alive)
    kwp_ready_cb_t _ready_cb = nullptr;
    kwp_data_cb_t  _data_cb  = nullptr;

    // Calcule le checksum KWP2000
    static uint8_t _cs(const uint8_t* d, uint8_t len) {
        uint8_t s = 0;
        for (uint8_t i = 0; i < len; i++) s += d[i];
        return s & 0xFF;
    }

    // Construit et envoie une trame KWP2000 (ajoute LEN et CS)
    bool _send_kwp(uint8_t sid, const uint8_t* data, uint8_t data_len,
                   kwp_data_cb_t cb = nullptr);

    // Parser une réponse STN1110 en bytes bruts
    static uint8_t _parse_hex_response(const char* resp,
                                        uint8_t* out, uint8_t max_len);

    // Callback statique pour STNDriver
    static void _on_stn_resp(const char* resp, uint16_t len);
    static void _on_stn_timeout(const char* last_cmd);
    static KWPSession* _instance;  // singleton pour les callbacks statiques

    // Gestion des réponses de la machine d'états
    void _handle_init_resp(const uint8_t* b, uint8_t len);
    void _handle_start_diag_resp(const uint8_t* b, uint8_t len);
    void _handle_seed_resp(const uint8_t* b, uint8_t len);
    void _handle_key_resp(const uint8_t* b, uint8_t len);
    void _handle_data_resp(const uint8_t* b, uint8_t len);

    void _send_keepalive();
    void _set_error(const char* msg);
};
