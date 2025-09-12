#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time, sys, signal, json, socket, argparse, threading
try:
    import RPi.GPIO as GPIO
except ImportError:
    raise SystemExit("Zainstaluj RPi.GPIO: sudo apt-get install python3-rpi.gpio")

# ====== PINY ======
PIN_DIR  = 20
PIN_STEP = 21
PIN_EN   = 16

# ====== PARAMETRY STEROWANIA ======
DEADBAND_PX    = 3.0       # martwa strefa (px)
KP_STEPS_PER_PX= 0.05      # Kp: ile "kroków/sek" na 1 px błędu (reguluje prędkość)
STEP_PULSE_S   = 0.0006    # pół-okres impulsu (HIGH i LOW) => ~833 Hz max
KEEP_ENABLED_S = 0.15      # ile czasu trzymamy EN po ostatnim kroku

latest_error_x = 0.0
last_update_ts = 0.0
run_flag       = True
lock           = threading.Lock()

def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PIN_DIR,  GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PIN_STEP, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PIN_EN,   GPIO.OUT, initial=GPIO.HIGH)  # HIGH = wyłączony

def enable_driver(enable: bool):
    GPIO.output(PIN_EN, GPIO.LOW if enable else GPIO.HIGH)

def set_direction(cw: bool):
    GPIO.output(PIN_DIR, GPIO.HIGH if cw else GPIO.LOW)

def step_once():
    GPIO.output(PIN_STEP, GPIO.HIGH)
    time.sleep(STEP_PULSE_S)
    GPIO.output(PIN_STEP, GPIO.LOW)
    time.sleep(STEP_PULSE_S)

def motor_loop():
    """
    Pętla generująca kroki wg "latest-only":
    - wyznacza docelową częstotliwość kroków: freq ≈ |error_x| * KP_STEPS_PER_PX [steps/s]
    - realizuje ją metodą akumulatora fazy (DDS-like), krok po kroku,
    - reaguje natychmiast na zmianę błędu (sprawdzane przed każdym krokiem),
    - trzyma driver włączony jeszcze KEEP_ENABLED_S po ostatnim kroku (bez 0.2 s blokad).
    """
    global latest_error_x
    phase = 0.0
    last_step_time = 0.0
    driver_on_until = 0.0

    while run_flag:
        with lock:
            e = latest_error_x
            now = time.time()

        if abs(e) <= DEADBAND_PX:
            # brak błędu -> rozładuj fazę i ew. wyłącz driver po chwili
            phase = 0.0
            if now > driver_on_until:
                enable_driver(False)
            time.sleep(0.001)
            continue

        # błąd -> kierunek i "częstotliwość" kroków
        cw = (e > 0)
        set_direction(cw)
        freq = abs(e) * KP_STEPS_PER_PX  # steps per second
        if freq < 1.0:                   # nie schodź zbyt nisko – utrzymaj responsywność
            freq = 1.0

        # przelicznik na kroki: dodajemy porcję fazy na iterację
        # wybierz krok czasowy pętli ~0.5 ms dla dużej responsywności
        dt = 0.0005
        phase += freq * dt              # gdy phase >= 1.0 -> wykonaj krok
        enable_driver(True)
        driver_on_until = now + KEEP_ENABLED_S

        if phase >= 1.0:
            step_once()
            phase -= 1.0
            last_step_time = now
        else:
            time.sleep(dt)

def cleanup(*_):
    global run_flag
    run_flag = False
    try:
        enable_driver(False)
    except Exception:
        pass
    GPIO.cleanup()
    sys.exit(0)

def run_network_client(host: str, port: int, reconnect_delay: float):
    global latest_error_x, last_update_ts
    while run_flag:
        try:
            print(f"[CLIENT] łączenie z {host}:{port} ...")
            s = socket.create_connection((host, port), timeout=5)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(5)
            print(f"[CLIENT] połączono")
            buf = b""
            with s:
                while run_flag:
                    chunk = s.recv(4096)
                    if not chunk:
                        raise ConnectionError("Serwer zamknął połączenie")
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            msg = json.loads(line.decode("utf-8"))
                        except json.JSONDecodeError:
                            continue
                        if "error_x" in msg:
                            with lock:
                                latest_error_x = float(msg["error_x"])
                                last_update_ts = time.time()
        except (OSError, ConnectionError, socket.timeout) as e:
            print(f"[CLIENT] reconnect za {reconnect_delay}s... ({e})")
            time.sleep(reconnect_delay)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    gpio_setup()

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--reconnect", type=float, default=0.5)
    args = ap.parse_args()

    # uruchom pętlę silnika
    t_motor = threading.Thread(target=motor_loop, daemon=True)
    t_motor.start()

    # uruchom klienta sieciowego
    run_network_client(args.host, args.port, args.reconnect)
