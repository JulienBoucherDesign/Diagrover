#pragma once
// ═══════════════════════════════════════════════════════════════
// DiagRover — stn_driver.h
// Driver STN1110 non-bloquant
// ═══════════════════════════════════════════════════════════════
#include <Arduino.h>
#include "config.h"

// Taille max d'une réponse STN1110 (trame KWP2000 étendue)
#define STN_RESP_MAX  128

// Callback appelé quand une réponse complète est reçue
typedef void (*stn_resp_cb_t)(const char* resp, uint16_t len);
// Callback appelé en cas de timeout
typedef void (*stn_timeout_cb_t)(const char* last_cmd);

class STNDriver {
public:
    void begin();

    // Envoie une commande AT ou trame STPX
    // Retourne false si une commande est déjà en cours (half-duplex)
    bool send(const char* cmd);
    bool send(const String& cmd) { return send(cmd.c_str()); }

    // Envoie une trame raw KWP2000 via STPX
    // bytes = tableau d'octets, len = longueur
    bool send_raw(const uint8_t* bytes, uint8_t len);

    // À appeler dans loop() — lit les bytes disponibles sans bloquer
    void poll();

    // Enregistre les callbacks
    void on_response(stn_resp_cb_t cb) { _resp_cb = cb; }
    void on_timeout(stn_timeout_cb_t cb) { _timeout_cb = cb; }

    // État
    bool is_busy() const { return _waiting; }
    bool is_ready() const { return _ready; }

    // Séquence d'initialisation complète STN1110
    // Bloquante au démarrage uniquement (appelée une fois dans setup())
    bool init_blocking();

private:
    char     _buf[STN_RESP_MAX];
    uint16_t _buf_len  = 0;
    bool     _waiting  = false;
    bool     _ready    = false;
    uint32_t _sent_at  = 0;
    uint32_t _timeout_ms = 2000;
    char     _last_cmd[64];

    stn_resp_cb_t    _resp_cb    = nullptr;
    stn_timeout_cb_t _timeout_cb = nullptr;

    void _process_response();
    bool _send_blocking(const char* cmd, uint32_t timeout_ms = 3000);
    bool _wait_for(const char* expected, uint32_t timeout_ms = 3000);
};
