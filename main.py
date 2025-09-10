import time
import random
import math
import RPi.GPIO as GPIO

# === KONFIGURACJA PINÓW (BCM) ===
STEP_PIN = 23   # Pin dla STEP
DIR_PIN = 24    # Pin dla DIR
EN_PIN = 25     # Pin dla EN (wyłączanie sterownika)

# Parametry silnika
MAX_STEP_FREQ_HZ = 4000.0  # Maksymalna częstotliwość kroków (dostosuj do silnika)

# Inicjalizacja GPIO (na wypadek, gdybyśmy chcieli korzystać z GPIO do testów)
GPIO.setmode(GPIO.BCM)
GPIO.setup(STEP_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(EN_PIN, GPIO.OUT, initial=GPIO.HIGH)  # Włącz sterownik (EN active-low)

# Funkcja do ustawienia kierunku
def set_direction(error: float):
    """Ustawia kierunek w zależności od wartości errora.
       Dodatnia – prawo, ujemna – lewo."""
    if error > 0:
        GPIO.output(DIR_PIN, GPIO.LOW)  # Prawo
    elif error < 0:
        GPIO.output(DIR_PIN, GPIO.HIGH)  # Lewo

# Funkcja do generowania kroków
def step_motor(frequency_hz: float):
    """Generuje impulsy kroków z określoną częstotliwością."""
    half_period = 0.5 / abs(frequency_hz)  # Okres impulsu (zbocze narastające/opadające)
    GPIO.output(STEP_PIN, GPIO.HIGH)
    time.sleep(half_period)
    GPIO.output(STEP_PIN, GPIO.LOW)
    time.sleep(half_period)

# Funkcja generująca losowe sygnały "error"
def simulate_error():
    """Symulacja wartości errora (zmieniającego się w czasie)."""
    # Sygnał będzie losowo zmieniał się w zakresie od -1.0 do 1.0
    error = random.uniform(-1.0, 1.0)
    return error

# Funkcja główna sterująca
def control_motor():
    """Steruje silnikiem na podstawie błędu (error)."""
    while True:
        # Symulacja wartości error
        error = simulate_error()

        # Ustawienie kierunku
        set_direction(error)

        # Liczba kroków na sekundę (częstotliwość)
        frequency_hz = abs(error)  # Wartość bezwzględna z errora, odpowiada częstotliwości
        frequency_hz = min(frequency_hz, MAX_STEP_FREQ_HZ)  # Ograniczenie prędkości

        # Generowanie kroków
        step_motor(frequency_hz)

        # Telemetria: informowanie o bieżącym sygnale
        print(f"Error: {error:.3f} -> {'Prawo' if error > 0 else 'Lewo'}, częstotliwość: {frequency_hz:.2f} Hz")
        
        # Przerwa na chwilę (symulacja co 0.1 sekundy)
        time.sleep(0.1)

# ================== Testowanie ==================
if __name__ == "__main__":
    try:
        print("Rozpoczynam symulację sterowania silnikiem...")
        control_motor()
    except KeyboardInterrupt:
        print("\nZatrzymanie symulacji.")
    finally:
        GPIO.cleanup()  # Zwolnienie GPIO po zakończeniu
