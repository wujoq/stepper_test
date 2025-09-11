#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sys
import signal
import csv

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
MAX_STEPS = 50       # maksymalna liczba kroków
STEP_PULSE_S = 0.001
SETUP_DELAY_S = 0.0005
IDLE_DISABLE_AFTER_S = 0.2

# ====== INICJALIZACJA ======
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
    cw = (error_x > 0)
    move_steps(steps, cw)

def cleanup(*_):
    try:
        enable_driver(False)
    except Exception:
        pass
    GPIO.cleanup()
    sys.exit(0)

# ====== GŁÓWNA CZĘŚĆ ======
if __name__ == "__main__":
    gpio_setup()
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Nazwa pliku CSV z symulacją danych
    csv_file = "errors.csv"

    print(f"Odczytuję dane z {csv_file}...")
    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")  # bo podałeś tabelę z tabami
        for row in reader:
            frame_id = int(row["frame_id"])
            error_x = float(row["error_x"])
            print(f"frame {frame_id}: error_x={error_x}")
            move_from_error(error_x)
            time.sleep(0.05)  # odstęp między klatkami

    cleanup()
