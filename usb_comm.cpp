// ═══════════════════════════════════════════════════════════════
// DiagRover — usb_comm.cpp
// Communication JSON USB CDC Nano ↔ PC
// ═══════════════════════════════════════════════════════════════
#include "usb_comm.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

// ── Buffer réception ──────────────────────────────────────────
static char  _rx_buf[USB_BUF_SIZE];
static uint16_t _rx_len = 0;
static bool  _cmd_ready  = false;

// ── JSON ultra-léger (pas de lib externe) ─────────────────────
// Suffisant pour notre protocole fixe
static char _cmd_str[32]    = "";
static char _json_buf[USB_BUF_SIZE] = "";  // copie pour parsing

// ── Envoi vers PC ─────────────────────────────────────────────

void usb_send_status(const char* level, const char* msg) {
    Serial.print(F("{\"type\":\"status\",\"level\":\""));
    Serial.print(level);
    Serial.print(F("\",\"msg\":\""));
    Serial.print(msg);
    Serial.println(F("\"}"));
}

void usb_send_live(const char* pid, float value, const char* unit) {
    char buf[96];
    // Utiliser %g pour éviter les zéros superflus
    snprintf(buf, sizeof(buf),
             "{\"type\":\"live\",\"pid\":\"%s\",\"val\":%.3f,\"unit\":\"%s\",\"ts\":%lu}",
             pid, value, unit, millis());
    Serial.println(buf);
}

void usb_send_live_int(const char* pid, int32_t value, const char* unit) {
    char buf[80];
    snprintf(buf, sizeof(buf),
             "{\"type\":\"live\",\"pid\":\"%s\",\"val\":%ld,\"unit\":\"%s\",\"ts\":%lu}",
             pid, (long)value, unit, millis());
    Serial.println(buf);
}

void usb_send_ack(const char* cmd, const char* result) {
    Serial.print(F("{\"type\":\"ack\",\"cmd\":\""));
    Serial.print(cmd);
    Serial.print(F("\",\"result\":\""));
    Serial.print(result);
    Serial.println(F("\"}"));
}

void usb_send_error(const char* code, const char* detail) {
    Serial.print(F("{\"type\":\"error\",\"code\":\""));
    Serial.print(code);
    Serial.print(F("\",\"detail\":\""));
    Serial.print(detail);
    Serial.println(F("\"}"));
}

void usb_send_raw(const char* type, const uint8_t* data, uint8_t len) {
    Serial.print(F("{\"type\":\""));
    Serial.print(type);
    Serial.print(F("\",\"hex\":\""));
    for (uint8_t i = 0; i < len; i++) {
        if (data[i] < 0x10) Serial.print('0');
        Serial.print(data[i], HEX);
    }
    Serial.print(F("\",\"len\":"));
    Serial.print(len);
    Serial.println(F("}"));
}

void usb_send_vom(float v0, float v1, float v2, float mA) {
    char buf[80];
    snprintf(buf, sizeof(buf),
             "{\"type\":\"vom\",\"v0\":%.3f,\"v1\":%.3f,\"v2\":%.3f,\"mA\":%.2f,\"ts\":%lu}",
             v0, v1, v2, mA, millis());
    Serial.println(buf);
}

// ── Réception depuis PC ───────────────────────────────────────

bool usb_poll() {
    _cmd_ready = false;

    while (Serial.available()) {
        char c = (char)Serial.read();

        if (c == '\n' || c == '\r') {
            if (_rx_len > 2) {
                _rx_buf[_rx_len] = '\0';
                // Copier pour parsing
                strncpy(_json_buf, _rx_buf, sizeof(_json_buf) - 1);
                // Extraire "cmd"
                _extract_string(_json_buf, "cmd", _cmd_str, sizeof(_cmd_str));
                _cmd_ready = true;
            }
            _rx_len = 0;
            return _cmd_ready;
        }

        if (_rx_len < USB_BUF_SIZE - 1) {
            _rx_buf[_rx_len++] = c;
        } else {
            // Buffer overflow — reset
            _rx_len = 0;
        }
    }
    return false;
}

const char* usb_get_cmd() {
    return _cmd_str;
}

// Extraction JSON minimaliste : cherche "key":"value"
const char* usb_get_param(const char* key) {
    static char out[128];
    out[0] = '\0';

    char search[40];
    snprintf(search, sizeof(search), "\"%s\":\"", key);

    char* p = strstr(_json_buf, search);
    if (!p) return nullptr;
    p += strlen(search);

    uint8_t i = 0;
    while (*p && *p != '"' && i < sizeof(out) - 1) {
        out[i++] = *p++;
    }
    out[i] = '\0';
    return out;
}

int32_t usb_get_int(const char* key, int32_t def) {
    char search[40];
    snprintf(search, sizeof(search), "\"%s\":", key);
    char* p = strstr(_json_buf, search);
    if (!p) return def;
    p += strlen(search);
    // Ignorer guillemets si présents
    if (*p == '"') p++;
    return strtol(p, nullptr, 10);
}

// ── Helper interne ────────────────────────────────────────────
void _extract_string(const char* json, const char* key,
                     char* out, uint8_t max_len) {
    out[0] = '\0';
    char search[40];
    snprintf(search, sizeof(search), "\"%s\":\"", key);
    const char* p = strstr(json, search);
    if (!p) return;
    p += strlen(search);
    uint8_t i = 0;
    while (*p && *p != '"' && i < max_len - 1) out[i++] = *p++;
    out[i] = '\0';
}
