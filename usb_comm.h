#pragma once
// ═══════════════════════════════════════════════════════════════
// DiagRover — usb_comm.h
// Communication JSON USB CDC Nano ↔ PC
// Format : une ligne JSON par message, terminée par \n
// ═══════════════════════════════════════════════════════════════
#include <Arduino.h>
#include "config.h"

// ── Envoi vers PC ─────────────────────────────────────────────

// Status générique
void usb_send_status(const char* level, const char* msg);

// Données live (un PID)
void usb_send_live(const char* pid, float value, const char* unit);
void usb_send_live_int(const char* pid, int32_t value, const char* unit);

// Acknowledge commande reçue
void usb_send_ack(const char* cmd, const char* result = "ok");

// Erreur
void usb_send_error(const char* code, const char* detail = "");

// Données brutes (hex) — pour debug et lecture mémoire
void usb_send_raw(const char* type, const uint8_t* data, uint8_t len);

// VOM mesure
void usb_send_vom(float v0, float v1, float v2, float mA);

// ── Réception depuis PC ───────────────────────────────────────

// À appeler dans loop() — non-bloquant
// Retourne true si une commande complète est disponible
bool usb_poll();

// Getter sur la dernière commande parsée (valide si usb_poll() == true)
const char* usb_get_cmd();
const char* usb_get_param(const char* key);  // valeur d'un champ JSON
int32_t     usb_get_int(const char* key, int32_t def = 0);
