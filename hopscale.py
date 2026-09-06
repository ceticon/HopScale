import RPi.GPIO as GPIO
import time
import statistics
import json
import os
from datetime import datetime


# ============================================================
# KONFIGURATION
# ============================================================

DATA_PIN = 21
CLOCK_PIN = 26

NUM_SAMPLES = 10
READ_INTERVAL = 0.5

CALIBRATION_FACTOR = 1063.1


# ============================================================
# FILER
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_FILE = os.path.join(BASE_DIR, "hopscale.json")
CONTROL_FILE = os.path.join(BASE_DIR, "control.json")


# ============================================================
# HOPSCALE
# ============================================================

class HopScale:

    def __init__(self):

        GPIO.setmode(GPIO.BCM)

        GPIO.setup(DATA_PIN, GPIO.IN)
        GPIO.setup(CLOCK_PIN, GPIO.OUT)

        GPIO.output(CLOCK_PIN, GPIO.LOW)

        self.tare_offset = 0.0

        print("Initierar HX711...")
        time.sleep(1.0)

        self.reset()

    # --------------------------------------------------------
    # Reset av HX711
    # --------------------------------------------------------

    def reset(self):

        GPIO.output(CLOCK_PIN, GPIO.HIGH)

        # HX711 går i power-down om SCK hålls hög > 60 µs
        time.sleep(0.005)

        GPIO.output(CLOCK_PIN, GPIO.LOW)

        time.sleep(0.1)

    # --------------------------------------------------------
    # Vänta tills HX711 har data
    # --------------------------------------------------------

    def wait_ready(self, timeout=1.0):

        start_time = time.time()

        while GPIO.input(DATA_PIN) == GPIO.HIGH:

            if time.time() - start_time > timeout:
                return False

        return True

    # --------------------------------------------------------
    # Läs ett råvärde
    # --------------------------------------------------------

    def read_raw(self):

        if not self.wait_ready():
            return None

        value = 0

        # Läs 24 bitar
        for _ in range(24):

            GPIO.output(CLOCK_PIN, GPIO.HIGH)

            value = value << 1

            GPIO.output(CLOCK_PIN, GPIO.LOW)

            if GPIO.input(DATA_PIN):
                value += 1

        # Extra puls = Channel A, gain 128
        GPIO.output(CLOCK_PIN, GPIO.HIGH)
        GPIO.output(CLOCK_PIN, GPIO.LOW)

        # Konvertera 24-bit signed integer
        if value & 0x800000:
            value -= 0x1000000

        return value

    # --------------------------------------------------------
    # Läs flera råvärden och filtrera
    # --------------------------------------------------------

    def read_filtered_raw(self):

        samples = []

        for _ in range(NUM_SAMPLES):

            value = self.read_raw()

            if value is not None:
                samples.append(value)

        if len(samples) < 5:
            return None

        samples.sort()

        # Ta bort lägsta och högsta värdet
        samples = samples[1:-1]

        return statistics.mean(samples)

    # --------------------------------------------------------
    # Tarera vågen
    # --------------------------------------------------------

    def tare(self):

        print("Tarerar vågen...")

        tare_samples = []

        for _ in range(10):

            value = self.read_filtered_raw()

            if value is not None:
                tare_samples.append(value)

        if len(tare_samples) == 0:

            print("Tarering misslyckades.")
            return False

        self.tare_offset = statistics.mean(tare_samples)

        print(f"Tare offset: {self.tare_offset:.1f}")
        print("Tarering klar.")

        return True

    # --------------------------------------------------------
    # Läs vikt i gram
    # --------------------------------------------------------

    def get_weight(self):

        raw_value = self.read_filtered_raw()

        if raw_value is None:
            return None, None, None

        difference = raw_value - self.tare_offset

        weight = difference / CALIBRATION_FACTOR

        # Små variationer runt noll sätts till 0
        if abs(weight) < 0.2:
            weight = 0.0

        return raw_value, difference, round(weight, 1)

    # --------------------------------------------------------
    # Skriv hopscale.json
    # --------------------------------------------------------

    def write_json(self, weight):

        data = {
            "weight_g": weight,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        try:

            with open(JSON_FILE, "w") as file:
                json.dump(data, file, indent=4)

        except Exception as error:

            print(f"Fel vid skrivning av hopscale.json: {error}")

    # --------------------------------------------------------
    # Kontrollera control.json
    # --------------------------------------------------------

    def check_control(self):

        try:

            if not os.path.exists(CONTROL_FILE):
                return

            with open(CONTROL_FILE, "r") as file:
                data = json.load(file)

            if data.get("tare", False):

                print()
                print(">>> TARE-KOMMANDO MOTTAGET <<<")
                print("Tarering begärd från webbsidan...")

                success = self.tare()

                if success:

                    data["tare"] = False

                    with open(CONTROL_FILE, "w") as file:
                        json.dump(data, file, indent=4)

                    print("Webbtarering klar.")
                    print("control.json återställd till tare=false")
                    print()

        except Exception as error:

            print(f"Fel vid läsning av control.json: {error}")

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    def cleanup(self):

        GPIO.cleanup()


# ============================================================
# HUVUDPROGRAM
# ============================================================

if __name__ == "__main__":

    scale = None

    try:

        print()
        print("==============================")
        print("          HopScale")
        print("==============================")
        print()

        scale = HopScale()

        print("Väntar på stabilisering...")
        time.sleep(2.0)

        print()
        print("Se till att vågen är TOM.")
        print()

        if not scale.tare():
            raise RuntimeError("Kunde inte tarera vågen.")

        print()
        print("HopScale är redo.")
        print("Tryck Ctrl+C för att avsluta.")
        print()

        while True:

            # Kontrollera om webbsidan begärt tarering
            scale.check_control()

            # Läs aktuell vikt
            raw, diff, weight = scale.get_weight()

            if raw is not None:

                print(
                    f"Raw: {raw:12.1f}   "
                    f"Diff: {diff:10.1f}   "
                    f"Vikt: {weight:7.1f} g"
                )

                # Uppdatera hopscale.json
                scale.write_json(weight)

            else:

                print("Ingen giltig mätning från HX711")

            time.sleep(READ_INTERVAL)

    except KeyboardInterrupt:

        print()
        print("Avslutar HopScale...")

    except Exception as error:

        print()
        print(f"Fel: {error}")

    finally:

        if scale is not None:
            scale.cleanup()

        print("GPIO städat.")