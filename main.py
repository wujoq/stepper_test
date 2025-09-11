#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sys
import signal
import csv
import math

try:
    import RPi.GPIO as GPIO
except ImportError:
    raise SystemExit("Zainstaluj RPi.GPIO: sudo apt-get install python3-rpi.gpio")

# ====== KONFIGURACJA PINÓW ======
PIN_DIR = 20   # Kierunek (DIR)
PIN_STEP = 21  # Krok (STEP)
PIN_EN = 16    # Enable (aktywny niski)

# ====== PARAMETRY MECHANIKI / KĄTA ======
# 200 kroków na pełny obrót 360°
STEPS_PER_REV = 200
DEG_PER_STEP = 360.0 / STEPS_PER_REV  # 1.8°/krok

# ====== PARAMETRY KAMERY (HD) ======
# Sensor 1/1.8" (~7.18 mm szerokości aktywnej), rozdzielczość 1920x1080
F_MM = 16.0            # ogniskowa (mm)
RES_X = 1920           # piksele w poziomie (HD)
SENSOR_WIDTH_MM = 7.18 # szerokość aktywna sensora (mm)

# ogniskowa w pikselach (fx)
FX_PX = F_MM * RES_X / SENSOR_WIDTH_MM  # ≈ 4278.55 px dla danych powyżej

# ====== PARAMETRY SYGNAŁÓW ======
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

def error_pix_to_steps(error_x_pix: float, fx_px: float = FX_PX) -> int:
    """
    theta = atan(e_pix / fx_px) [rad]
    steps = round(|theta_deg| / DEG_PER_STEP)
    Dodatni error_x => ruch CW.
    """
    if error_x_pix == 0.0:
        return 0
    theta_rad = math.atan(error_x_pix / fx_px)
    theta_deg = math.degrees(theta_rad)
    steps = int(round(abs(theta_deg) / DEG_PER_STEP))
    return steps

def move_from_error(error_x_pix: float):
    steps = error_pix_to_steps(error_x_pix, FX_PX)
    if steps == 0:
        return
    cw = (error_x_pix > 0)  # w razie odwrotu zmień na (< 0)
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
    print(f"FX_PX (fx w pikselach) = {FX_PX:.2f} px  |  {DEG_PER_STEP:.3f}°/krok")
    gpio_setup()
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    csv_file = "errors.csv"  # kolumny: frame_id, error_x (tab-separated)
    print(f"Odczytuję dane z {csv_file}...")

    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            frame_id = int(row["frame_id"])
            error_x = float(row["error_x"])
            steps = error_pix_to_steps(error_x, FX_PX)
            dir_txt = "CW" if error_x > 0 else "CCW"
            print(f"frame {frame_id}: error_x={error_x:.2f} px -> steps={steps} dir={dir_txt}")
            move_from_error(error_x)
            time.sleep(0.05)

    cleanup()
