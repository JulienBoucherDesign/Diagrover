#!/usr/bin/env python3
"""
DiagRover — main.py
Interface CLI — POC bout-en-bout
Nano 33 BLE + PC + Land Rover Discovery 2 / TD5

Usage :
    python main.py                    # auto-détect port Nano
    python main.py --port /dev/ttyACM0
    python main.py --demo             # mode démo sans véhicule (données sniffing)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import threading
from pathlib import Path
from typing import Optional

# ── Deps ──────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    from rich.prompt import Confirm, Prompt
    from rich import box
    import rich.traceback
    rich.traceback.install()
except ImportError:
    print("Installer rich : pip install rich")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from diagrover.core.serial_manager import SerialManager
from diagrover.core.session_logger import SessionLogger
from diagrover.data.dtc_database import decode_fault_bitfield, SEVERITY_LABEL, SEVERITY_COLOR, init_db

console = Console()

# ── État partagé (thread-safe via lock) ───────────────────────
_lock = threading.Lock()
_logger = SessionLogger()  # journal de session
_state = {
    "connected":   False,
    "session":     False,
    "ecu_type":    None,
    "vin":         None,
    "live": {
        "RPM":          None,
        "SPEED":        None,
        "BATT_V1":      None,
        "TEMP_COOLANT": None,
        "TEMP_FUEL":    None,
        "TEMP_AIR":     None,
        "MAP_MBAR":     None,
        "EGR_MOD":      None,
        "PWR_BAL_1":    None,
        "PWR_BAL_2":    None,
        "PWR_BAL_3":    None,
        "PWR_BAL_4":    None,
        "PWR_BAL_5":    None,
    },
    "faults":  [],
    "log":     [],
    "status":  "Déconnecté",
}


def _set(key, val):
    with _lock:
        _state[key] = val

def _get(key):
    with _lock:
        return _state[key]

def _log(msg: str):
    with _lock:
        _state["log"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if len(_state["log"]) > 20:
            _state["log"].pop(0)


# ── Callbacks SerialManager ───────────────────────────────────

def on_status(msg: dict):
    level = msg.get("level", "")
    text  = msg.get("msg", "")
    _log(f"[{level.upper()}] {text}")
    with _lock:
        _state["status"] = text
        if text == "session_open":
            _state["session"] = True
            _logger.log_auth_ok()
        elif "STN1110 ready" in text:
            _state["connected"] = True
            _logger.log_stn_ready(text)
        elif "seed" in text.lower():
            # Parser le message seed=0xXXXX key=0xXXXX
            import re
            m = re.search(r'seed=0x([0-9A-Fa-f]{4}).*key=0x([0-9A-Fa-f]{4})', text)
            if m:
                _logger.log_auth(int(m.group(1),16), int(m.group(2),16))

def on_live(msg: dict):
    pid = msg.get("pid", "")
    val = msg.get("val")
    if pid and val is not None:
        with _lock:
            if pid in _state["live"]:
                _state["live"][pid] = val
        # Snapshot log toutes les 10s
        with _lock:
            snap = dict(_state["live"])
        _logger.log_live_snapshot(snap)

def on_error(msg: dict):
    code   = msg.get("code", "ERR")
    detail = msg.get("detail", "")
    _log(f"[ERREUR] {code}: {detail}")

def on_ack(msg: dict):
    cmd = msg.get("cmd", "")
    _log(f"[ACK] {cmd}")


# ── Construction du display Rich ─────────────────────────────

def make_header() -> Panel:
    with _lock:
        conn  = _state["connected"]
        sess  = _state["session"]
        vin   = _state["vin"] or "—"
        ecu   = _state["ecu_type"] or "—"
        status = _state["status"]

    conn_dot  = "[green]●[/]" if conn  else "[red]●[/]"
    sess_dot  = "[green]●[/]" if sess  else "[yellow]○[/]"
    conn_str  = f"{conn_dot} Nano connecté" if conn else f"{conn_dot} Déconnecté"
    sess_str  = f"{sess_dot} Session KWP2000 ouverte" if sess else f"{sess_dot} Session fermée"

    txt = Text()
    txt.append("DiagRover POC", style="bold white")
    txt.append("  ·  ", style="dim")
    txt.append(conn_str + "  ")
    txt.append(sess_str + "  ")
    txt.append(f"VIN: {vin}  ECU: {ecu}", style="dim")
    return Panel(txt, height=3)

def make_live_table() -> Panel:
    tbl = Table(box=box.SIMPLE, show_header=True, expand=True)
    tbl.add_column("Paramètre",  style="cyan",  no_wrap=True, width=22)
    tbl.add_column("Valeur",     style="white", no_wrap=True, width=14)
    tbl.add_column("Unité",      style="dim",   no_wrap=True, width=8)
    tbl.add_column("Statut",     style="dim",   no_wrap=True, width=10)

    def row(name, pid, unit, warn=None, crit=None):
        with _lock:
            val = _state["live"].get(pid)
        if val is None:
            tbl.add_row(name, "[dim]—[/]", unit, "[dim]en attente[/]")
            return
        val_f = float(val)
        if crit is not None and val_f >= crit:
            status = "[red]CRITIQUE[/]"
            val_s  = f"[red bold]{val_f:.1f}[/]"
        elif warn is not None and val_f >= warn:
            status = "[yellow]ATTENTION[/]"
            val_s  = f"[yellow]{val_f:.1f}[/]"
        else:
            status = "[green]OK[/]"
            val_s  = f"{val_f:.1f}"
        tbl.add_row(name, val_s, unit, status)

    row("Régime moteur",     "RPM",          "rpm",  warn=4500, crit=6000)
    row("Vitesse",           "SPEED",        "km/h")
    row("Batterie",          "BATT_V1",      "V",    warn=14.5, crit=15.0)
    row("Temp. refroid.",    "TEMP_COOLANT", "°C",   warn=95,   crit=105)
    row("Temp. carburant",   "TEMP_FUEL",    "°C",   warn=70,   crit=80)
    row("Temp. admission",   "TEMP_AIR",     "°C",   warn=50,   crit=65)
    row("MAP / Turbo",       "MAP_MBAR",     "mbar", warn=1600, crit=2000)
    row("Modulation EGR",    "EGR_MOD",      "")

    # Power Balance
    tbl.add_row("", "", "", "")
    tbl.add_row("[dim]Power Balance[/]", "", "", "")
    with _lock:
        pb = [_state["live"].get(f"PWR_BAL_{i}") for i in range(1, 6)]
    pb_vals = []
    for v in pb:
        if v is None:
            pb_vals.append("[dim]—[/]")
        else:
            vf = float(v)
            if abs(vf) > 50:
                pb_vals.append(f"[red]{vf:+.0f}[/]")
            elif abs(vf) > 20:
                pb_vals.append(f"[yellow]{vf:+.0f}[/]")
            else:
                pb_vals.append(f"[green]{vf:+.0f}[/]")
    pb_str = "  ".join(f"Cyl{i+1}:{pb_vals[i]}" for i in range(5))
    tbl.add_row("", pb_str, "", "")

    return Panel(tbl, title="[bold]Live Data[/]", border_style="blue")

def make_fault_panel() -> Panel:
    with _lock:
        faults = list(_state["faults"])
    if not faults:
        return Panel("[dim]Aucun code défaut — lire les faults via (f)[/]",
                     title="[bold]Codes Défauts[/]", border_style="green")

    tbl = Table(box=box.SIMPLE, show_header=True, expand=True)
    tbl.add_column("Sévérité",  width=10)
    tbl.add_column("Code",      width=10)
    tbl.add_column("Description")
    for f in faults[:12]:  # max 12 lignes
        color = SEVERITY_COLOR.get(f["severity"], "white")
        tbl.add_row(
            f"[{color}]{SEVERITY_LABEL[f['severity']]}[/]",
            f"[{color}]{f['code']}[/]",
            f["desc_fr"][:55] + ("…" if len(f["desc_fr"]) > 55 else ""),
        )
    if len(faults) > 12:
        tbl.add_row("[dim]…[/]", "", f"[dim]et {len(faults)-12} codes supplémentaires[/]")

    color = "red" if any(f["severity"] == 3 for f in faults) else "yellow"
    return Panel(tbl, title=f"[bold]{len(faults)} Code(s) Défaut(s)[/]",
                 border_style=color)

def make_log_panel() -> Panel:
    with _lock:
        lines = list(_state["log"][-10:])
    txt = "\n".join(lines) if lines else "[dim]En attente...[/]"
    return Panel(txt, title="[bold]Journal[/]", border_style="dim")

def make_commands_panel() -> Panel:
    cmds = (
        "[white](i)[/] Init session    "
        "[white](l)[/] Live data ON/OFF  "
        "[white](f)[/] Lire faults    "
        "[white](c)[/] Clear faults   "
        "[white](q)[/] Quitter"
    )
    return Panel(cmds, height=3)

def build_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(make_header(),         name="header",   size=3),
        Layout(name="main",           ratio=1),
        Layout(make_commands_panel(), name="commands", size=3),
    )
    layout["main"].split_row(
        Layout(name="left",  ratio=2),
        Layout(name="right", ratio=3),
    )
    layout["main"]["left"].split_column(
        Layout(make_live_table(),  name="live",  ratio=2),
        Layout(make_log_panel(),   name="log",   ratio=1),
    )
    layout["main"]["right"].update(make_fault_panel())
    return layout


# ── Gestion clavier (non-bloquant) ───────────────────────────

def keyboard_loop(serial_mgr: SerialManager, live_running: list):
    """Thread clavier — lit les commandes utilisateur."""
    import sys, tty, termios
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        # Pas de TTY disponible (conteneur, pipe) — lecture simple ligne par ligne
        while True:
            try:
                ch = sys.stdin.read(1)
                if not ch: break
            except Exception:
                break
        return

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)

            if ch == 'q':
                serial_mgr.send({"cmd": "live_stop"})
                _log("Fermeture...")
                time.sleep(0.3)
                os._exit(0)

            elif ch == 'i':
                serial_mgr.send({"cmd": "init"})
                _log("→ init session KWP2000")

            elif ch == 'l':
                if live_running[0]:
                    serial_mgr.send({"cmd": "live_stop"})
                    live_running[0] = False
                    _log("→ Live data arrêté")
                else:
                    serial_mgr.send({"cmd": "live_start", "rate_ms": 200})
                    live_running[0] = True
                    _log("→ Live data démarré")

            elif ch == 'f':
                serial_mgr.send({"cmd": "read_pid", "lid": 0x3B})
                _log("→ Lecture codes défauts (0x3B)")

            elif ch == 'c':
                serial_mgr.send({"cmd": "routine", "lid": 0xDD, "param": 0})
                with _lock:
                    _state["faults"] = []
                _log("→ Effacement codes défauts")

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Mode démo (sans Nano) ─────────────────────────────────────

def demo_mode():
    """Injecte des données de test tirées des sniffings."""
    _set("connected", True)
    _set("session",   True)
    _set("vin",       "SALLTGM844A")
    _set("ecu_type",  "NNN")
    _set("status",    "session_open [DEMO]")
    _log("[DEMO] Simulation données sniffings Ekaitza_Itzali")

    demo_live = {
        "RPM": 0, "SPEED": 0, "BATT_V1": 14.022,
        "TEMP_COOLANT": 35.82, "TEMP_FUEL": 50.0, "TEMP_AIR": 39.32,
        "MAP_MBAR": 1000.0, "EGR_MOD": 0,
        "PWR_BAL_1": 0, "PWR_BAL_2": 0, "PWR_BAL_3": 0,
        "PWR_BAL_4": 0, "PWR_BAL_5": 0,
    }
    fault_bytes = bytes.fromhex(
        "c0c0000780870000701d000000ff00cf008f"
        "00003801008000280000000000000000"
    )

    def _inject():
        import math
        t = 0
        while True:
            t += 0.1
            with _lock:
                # Simuler un ralenti
                _state["live"]["RPM"]     = int(820 + 30 * math.sin(t))
                _state["live"]["BATT_V1"] = round(14.022 + 0.01 * math.sin(t * 2), 3)
                _state["live"]["TEMP_COOLANT"] = round(35.82 + t * 0.05, 2)
                _state["live"]["MAP_MBAR"] = round(1000 + 5 * math.sin(t * 3), 1)
            time.sleep(0.1)

    threading.Thread(target=_inject, daemon=True).start()

    # Charger les faults après 1s
    def _load_faults():
        time.sleep(1)
        faults = decode_fault_bitfield(fault_bytes)
        with _lock:
            _state["faults"] = faults
        _log(f"[DEMO] {len(faults)} codes défauts chargés depuis sniffing réel")

    threading.Thread(target=_load_faults, daemon=True).start()


# ── Main ──────────────────────────────────────────────────────

def main():
    import os
    parser = argparse.ArgumentParser(description="DiagRover — POC CLI")
    parser.add_argument("--port",  help="Port COM du Nano 33 BLE")
    parser.add_argument("--demo",  action="store_true", help="Mode démo sans véhicule")
    args = parser.parse_args()

    # Callback faults depuis les réponses live
    def on_live_with_faults(msg: dict):
        on_live(msg)
        # Détecter une réponse fault (type spécial)
        if msg.get("type") == "fault_data":
            hex_data = msg.get("hex", "")
            if len(hex_data) >= 70:  # 35 bytes = 70 hex chars
                try:
                    raw = bytes.fromhex(hex_data)
                    faults = decode_fault_bitfield(raw)
                    with _lock:
                        _state["faults"] = faults
                    _log(f"[FAULTS] {len(faults)} codes décodés")
                except Exception as e:
                    _log(f"[FAULTS] Erreur décodage: {e}")

    serial_mgr = SerialManager()
    serial_mgr.on_message("status",  on_status)
    serial_mgr.on_message("live",    on_live_with_faults)
    serial_mgr.on_message("error",   on_error)
    serial_mgr.on_message("ack",     on_ack)
    serial_mgr.on_connected(    lambda p: (_set("connected", True),  _log(f"Nano connecté sur {p}")))
    serial_mgr.on_disconnected( lambda:   (_set("connected", False), _log("Nano déconnecté !")))

    console.clear()
    console.print("\n[bold blue]DiagRover[/] — POC CLI · Land Rover Discovery 2\n")

    if args.demo:
        console.print("[yellow]Mode démo activé — données simulées depuis sniffings réels[/]\n")
        _logger.start_session(demo=True)
        _logger.log_comment("Mode démo — données issues des sniffings Ekaitza_Itzali")
        demo_mode()
    else:
        port = args.port or SerialManager.find_nano_port()
        if not port:
            console.print("[red]Nano 33 BLE non détecté.[/]")
            console.print("Ports disponibles :")
            for p in SerialManager.list_ports():
                console.print(f"  {p['device']} — {p['description']}")
            console.print("\nRelancer avec [cyan]--port /dev/ttyXXX[/] ou [cyan]--demo[/]")
            sys.exit(1)

        _logger.start_session(port=port)
        console.print(f"Connexion sur [cyan]{port}[/]...")
        if not serial_mgr.connect(port):
            console.print(f"[red]Impossible d'ouvrir {port}[/]")
            sys.exit(1)

        # Init automatique après 1s
        def _auto_init():
            time.sleep(1.5)
            serial_mgr.send({"cmd": "init"})
            _log("→ init session KWP2000 (automatique)")
        threading.Thread(target=_auto_init, daemon=True).start()

    live_running = [False]

    # Thread clavier
    try:
        kb_thread = threading.Thread(
            target=keyboard_loop,
            args=(serial_mgr, live_running),
            daemon=True
        )
        kb_thread.start()
    except Exception:
        pass  # Windows ou environnement sans tty

    # Boucle d'affichage Rich Live
    console.print("\n[dim]Appuie sur (i) pour init, (l) pour live data, (f) pour faults, (q) pour quitter[/]\n")
    time.sleep(0.5)

    try:
        with Live(build_layout(), refresh_per_second=4, screen=True) as live_display:
            while True:
                live_display.update(build_layout())
                time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        serial_mgr.disconnect()
        _logger.end_session()
        if _logger.path:
            console.print(f"\n[dim]Log sauvegardé: {_logger.path}[/]")
        console.print("[dim]DiagRover arrêté.[/]")


if __name__ == "__main__":
    main()
