// ═══════════════════════════════════════════════════════════════
// DiagRover — live_data.cpp
// Dispatcher live data TD5
// ═══════════════════════════════════════════════════════════════
#include "live_data.h"

void dispatch_live_data(uint8_t lid, const uint8_t* d, uint8_t len) {
    switch (lid) {

    case LID_RPM: {
        if (len < 2) break;
        usb_send_live_int("RPM", decode_rpm(d, len), "rpm");
        break;
    }

    case LID_SPEED: {
        if (len < 1) break;
        usb_send_live_int("SPEED", decode_speed(d, len), "km/h");
        break;
    }

    case LID_BATTERY: {
        if (len < 4) break;
        usb_send_live("BATT_V1", decode_battery(d, 0), "V");
        usb_send_live("BATT_V2", decode_battery(d, 1), "V");
        break;
    }

    case LID_TEMPS: {
        if (len < 16) break;
        static const char* names[] = {
            "TEMP_COOLANT","TEMP_FUEL","TEMP_AIR","TEMP_3",
            "TEMP_4","TEMP_5","TEMP_6","TEMP_7"
        };
        for (uint8_t i = 0; i < 8 && i < len / 2; i++) {
            float t;
            if (decode_temp(d, i, t)) {
                usb_send_live(names[i], t, "C");
            }
            // Si decode_temp retourne false → capteur absent → ne pas envoyer
        }
        break;
    }

    case LID_THROTTLE: {
        if (len < 8) break;
        usb_send_live("THR_T1", decode_throttle_track(d, 0), "V");
        usb_send_live("THR_T2", decode_throttle_track(d, 1), "V");
        usb_send_live("THR_T3", decode_throttle_track(d, 2), "V");
        usb_send_live("THR_T4", decode_throttle_track(d, 3), "V");
        break;
    }

    case LID_PRESSURES: {
        if (len < 4) break;
        usb_send_live("MAP_MBAR",   decode_pressure_mbar(d, 0), "mbar");
        usb_send_live("PRESS_2",    decode_pressure_mbar(d, 1), "mbar");
        if (len >= 8) {
            usb_send_live("PRESS_3", decode_pressure_mbar(d, 2), "mbar");
            usb_send_live("PRESS_4", decode_pressure_mbar(d, 3), "mbar");
        }
        break;
    }

    case LID_AMB_PRESS: {
        if (len < 2) break;
        usb_send_live("AMB_PRESS", decode_pressure_mbar(d, 0), "mbar");
        break;
    }

    case LID_EGR_MOD: {
        if (len < 2) break;
        int16_t val = (int16_t)((d[0] << 8) | d[1]);
        usb_send_live_int("EGR_MOD", val, "");
        break;
    }

    case LID_EGR_INLET: {
        if (len < 2) break;
        int16_t val = (int16_t)((d[0] << 8) | d[1]);
        usb_send_live_int("EGR_INLET", val, "");
        break;
    }

    case LID_RPM_ERROR: {
        if (len < 2) break;
        int16_t val = (int16_t)((d[0] << 8) | d[1]);
        usb_send_live_int("RPM_ERR", val, "rpm");
        break;
    }

    case LID_POWER_BAL: {
        if (len < 10) break;
        char pid[16];
        for (uint8_t c = 0; c < 5; c++) {
            snprintf(pid, sizeof(pid), "PWR_BAL_%d", c + 1);
            usb_send_live_int(pid, decode_power_balance(d, c), "");
        }
        break;
    }

    case LID_SWITCHES: {
        if (len < 2) break;
        switches_t sw = decode_switches(d);
        // Envoyer un objet JSON compact avec tous les switches
        char buf[128];
        snprintf(buf, sizeof(buf),
            "{\"type\":\"switches\","
            "\"brake1\":%d,\"brake2\":%d,\"clutch\":%d,"
            "\"cruise_m\":%d,\"ac_req\":%d,\"transfer\":%d,"
            "\"ts\":%lu}",
            sw.brake1, sw.brake2, sw.clutch,
            sw.cruise_master, sw.ac_clutch_req, sw.transfer_ratio,
            millis());
        Serial.println(buf);
        break;
    }

    default:
        // LID inconnu → envoyer les bytes bruts pour debug
        usb_send_raw("unknown_lid", d, len);
        break;
    }
}
