#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sys
import signal
import json
import socket
import argparse

try:
    import RPi.GPIO as GPIO
except ImportError:
    raise SystemExit("Zainstaluj RPi.GPIO: sudo apt-get install python3-rpi.gpio")

# ====== KONFIGURACJA PINÓW ======
PIN_DIR    = 20   # Kierunek (DIR)
PIN_STEP   = 21   # Krok (STEP)
PIN_EN     = 16   # Enable (aktywny niski)

# ====== PARAMETRY RUCHU ======
KP = 0.2             # ile kroków na 1 px błędu
MAX_STEPS = 50       # maksymalna liczba kroków na wiadomość
STEP_PULSE_S = 0.001
SETUP_DELAY_S = 0.0005
IDLE_DISABLE_AFTER_S = 0.2

# ====== INICJALIZACJA GPIO ======
def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PIN_DIR, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PIN_STEP, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PIN_EN, GPIO.OUT, initial=GPIO.HIGH)  # HIGH = wyłączony

def enable_driver(enable: bool):
    GPIO.output(PIN_EN, GPIO.LOW if enable else GPIO.HIGH)

def set_direction(cw: bool):
    GPIO.output(PIN_DIR, GPIO.HIGH if cw else GPIO.LOW)
    time.sleep(SETUP_DELAY_S)

def step_once():
    GPIO.output(PIN_STEP, GPIO.HIGH)
    time.sleep(STEP_PULSE_S)
    GPIO.output(PIN_STEP, GPIO.LOW)
    time.sleep(STEP_PULSE_S)

def move_steps(steps: int, cw: bool):
    if steps <= 0:
        return
    enable_driver(True)
    set_direction(cw)
    for _ in range(steps):
        step_once()
    time.sleep(IDLE_DISABLE_AFTER_S)
    enable_driver(False)

def error_to_steps(error_x: float, kp: float = KP, max_steps: int = MAX_STEPS) -> int:
    est = int(round(abs(error_x) * kp))
    if est > max_steps:
        est = max_steps
    if est < 0:
        est = 0
    return est

def move_from_error(error_x: float, kp: float = KP):
    steps = error_to_steps(error_x, kp=kp, max_steps=MAX_STEPS)
    if steps == 0:
        return
    cw = (error_x > 0)  # prawo = dodatnie X
    move_steps(steps, cw)

# ====== ZAMYKANIE ======
def cleanup(*_):
    try:
        enable_driver(False)
    except Exception:
        pass
    GPIO.cleanup()
    sys.exit(0)

# ====== KLIENT TCP (JSONL) ======
def run_network_client(host: str, port: int, reconnect_delay: float):
    """
    Łączy się z serwerem na laptopie i w pętli odbiera linie JSON.
    Każda linia powinna zawierać 'error_x'. Po odebraniu natychmiast wywołuje move_from_error().
    """
    while True:
        try:
            print(f"[CLIENT] łączenie z {host}:{port} ...")
            with socket.create_connection((host, port), timeout=10) as s:
                s.settimeout(30)
                print(f"[CLIENT] połączono z {host}:{port}")
                buf = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        raise ConnectionError("Serwer zamknął połączenie")
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line.decode("utf-8"))
                        except json.JSONDecodeError:
                            print("[CLIENT] Błędny JSON:", line[:120])
                            continue

                        if "error_x" in msg:
                            error_x = float(msg["error_x"])
                            # NATYCHMIASTOWE STEROWANIE
                            move_from_error(error_x)
                        else:
                            # np. {"status":"connected"}
                            pass
        except (OSError, ConnectionError, socket.timeout) as e:
            print(f"[CLIENT] problem z połączeniem: {e}. Ponawiam za {reconnect_delay}s...")
            time.sleep(reconnect_delay)

# ====== OPCJONALNY TRYB CSV (jeśli chcesz testować offline) ======
def run_csv_mode(csv_path: str, delimiter: str = "\t", sleep_s: float = 0.05):
    import csv
    print(f"[CSV] odczyt z {csv_path}")
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            error_x = float(row["error_x"])
            move_from_error(error_x)
            time.sleep(sleep_s)

# ====== MAIN ======
if __name__ == "__main__":
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    gpio_setup()

    ap = argparse.ArgumentParser(description="RPi klient TCP sterujący silnikiem na podstawie error_x.")
    ap.add_argument("--host", help="Adres IP laptopa (serwera). Jeśli podasz, działa tryb sieciowy.")
    ap.add_argument("--port", type=int, default=5005, help="Port serwera (domyślnie 5005).")
    ap.add_argument("--reconnect", type=float, default=1.5, help="Opóźnienie ponownego łączenia (s).")
    ap.add_argument("--csv", help="Opcjonalnie: ścieżka do pliku CSV dla trybu offline.")
    ap.add_argument("--csv-delim", default="\t", help="Separator w CSV (domyślnie tab).")
    ap.add_argument("--csv-sleep", type=float, default=0.05, help="Odstęp między wierszami CSV (s).")
    args = ap.parse_args()

    if args.host:
        # Tryb sieciowy — odbiór w czasie rzeczywistym i sterowanie
        run_network_client(args.host, args.port, args.reconnect)
    elif args.csv:
        # Tryb offline (CSV)
        run_csv_mode(args.csv, delimiter=args.csv_delim, sleep_s=args.csv_sleep)
        cleanup()
    else:
        print("Podaj --host <IP_laptopa> (tryb sieciowy) lub --csv <plik> (tryb offline).")
        cleanup()
