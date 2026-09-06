import RPi.GPIO as GPIO
import time
import statistics
import json
import os

from datetime import datetime
from RPLCD.i2c import CharLCD
from gpiozero import Button


# ============================================================
# KONFIGURATION
# ============================================================

DATA_PIN = 21
CLOCK_PIN = 26

TARE_BUTTON_PIN = 17

NUM_SAMPLES = 10
READ_INTERVAL = 0.5

CALIBRATION_FACTOR = 1063.1

LCD_ADDRESS = 0x27
LCD_OFF_DELAY = 5.0

# LCD släcks när vikten varit under denna nivå
LCD_WEIGHT_LIMIT = 1.0


# ============================================================
# FILER
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_FILE = os.path.join(BASE_DIR, "hopscale.json")
CONTROL_FILE = os.path.join(BASE_DIR, "control.json")


# ============================================================
# LCD
# ============================================================

lcd = CharLCD(
    i2c_expander="PCF8574",
    address=LCD_ADDRESS,
    port=1,
    cols=20,
    rows=4,
    charmap="A00",
    auto_linebreaks=False
)


# ============================================================
# HOPSCALE
# ============================================================

class HopScale:

    def __init__(self):

        # ----------------------------------------------------
        # GPIO för HX711
        # ----------------------------------------------------

        GPIO.setmode(GPIO.BCM)

        GPIO.setup(DATA_PIN, GPIO.IN)
        GPIO.setup(CLOCK_PIN, GPIO.OUT)

        GPIO.output(CLOCK_PIN, GPIO.LOW)

        # ----------------------------------------------------
        # TARE-knapp
        # ----------------------------------------------------

        # Knappen sitter mellan GPIO17 och GND.
        # Intern pull-up används.
        self.tare_button = Button(
            TARE_BUTTON_PIN,
            pull_up=True,
            bounce_time=0.1
        )

        # För att upptäcka ett nytt knapptryck
        self.tare_button_was_pressed = False

        # ----------------------------------------------------
        # Interna värden
        # ----------------------------------------------------

        self.tare_offset = 0.0

        # Tidpunkt när vikten gick under LCD_WEIGHT_LIMIT
        self.lcd_below_limit_since = None

        # ----------------------------------------------------
        # Start
        # ----------------------------------------------------

        print("Initierar HX711...")

        lcd.backlight_enabled = True

        self.lcd_message(
            "      HopScale",
            "",
            "     Starting...",
            ""
        )

        time.sleep(1.0)

        self.reset()

    # ========================================================
    # LCD
    # ========================================================

    def lcd_message(
        self,
        line1="",
        line2="",
        line3="",
        line4=""
    ):

        try:

            lines = [
                line1,
                line2,
                line3,
                line4
            ]

            for row, text in enumerate(lines):

                lcd.cursor_pos = (row, 0)

                # Skriv exakt 20 tecken så gammal text
                # skrivs över.
                lcd.write_string(
                    str(text)[:20].ljust(20)
                )

        except Exception as error:

            print(f"LCD-fel: {error}")

    # ========================================================
    # RESET HX711
    # ========================================================

    def reset(self):

        GPIO.output(
            CLOCK_PIN,
            GPIO.HIGH
        )

        # HX711 går i power-down om SCK hålls hög > 60 us
        time.sleep(0.005)

        GPIO.output(
            CLOCK_PIN,
            GPIO.LOW
        )

        time.sleep(0.1)

    # ========================================================
    # VÄNTA PÅ HX711
    # ========================================================

    def wait_ready(
        self,
        timeout=1.0
    ):

        start_time = time.time()

        while GPIO.input(DATA_PIN) == GPIO.HIGH:

            if (
                time.time() - start_time
                > timeout
            ):
                return False

        return True

    # ========================================================
    # LÄS ETT RÅVÄRDE
    # ========================================================

    def read_raw(self):

        if not self.wait_ready():
            return None

        value = 0

        # Läs 24 bitar
        for _ in range(24):

            GPIO.output(
                CLOCK_PIN,
                GPIO.HIGH
            )

            value = value << 1

            GPIO.output(
                CLOCK_PIN,
                GPIO.LOW
            )

            if GPIO.input(DATA_PIN):
                value += 1

        # Extra puls:
        # Channel A, gain 128
        GPIO.output(
            CLOCK_PIN,
            GPIO.HIGH
        )

        GPIO.output(
            CLOCK_PIN,
            GPIO.LOW
        )

        # Konvertera 24-bit signed integer
        if value & 0x800000:
            value -= 0x1000000

        return value

    # ========================================================
    # FILTRERA RÅVÄRDEN
    # ========================================================

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

    # ========================================================
    # TARERA
    # ========================================================

    def tare(self):

        print("Tarerar vågen...")

        # Tänd displayen vid tarering
        lcd.backlight_enabled = True

        # Nollställ LCD-timern
        self.lcd_below_limit_since = None

        self.lcd_message(
            "      HopScale",
            "",
            "     TARING...",
            "    Please wait"
        )

        tare_samples = []

        for _ in range(10):

            value = self.read_filtered_raw()

            if value is not None:
                tare_samples.append(value)

        if len(tare_samples) == 0:

            print("Tarering misslyckades.")

            self.lcd_message(
                "      HopScale",
                "",
                "    TARE ERROR",
                ""
            )

            return False

        self.tare_offset = statistics.mean(
            tare_samples
        )

        print(
            f"Tare offset: "
            f"{self.tare_offset:.1f}"
        )

        print("Tarering klar.")

        self.lcd_message(
            "      HopScale",
            "",
            "   Tare complete",
            ""
        )

        time.sleep(0.5)

        return True

    # ========================================================
    # LÄS VIKT
    # ========================================================

    def get_weight(self):

        raw_value = self.read_filtered_raw()

        if raw_value is None:
            return None, None, None

        difference = (
            raw_value
            - self.tare_offset
        )

        weight = (
            difference
            / CALIBRATION_FACTOR
        )

        # Små variationer runt noll sätts till 0
        if abs(weight) < 0.2:
            weight = 0.0

        return (
            raw_value,
            difference,
            round(weight, 1)
        )

    # ========================================================
    # FYSISK TARE-KNAPP
    # ========================================================

    def check_tare_button(self):

        # Knappen är nedtryckt
        if self.tare_button.is_pressed:

            # Bara reagera på själva övergången
            # från inte tryckt -> tryckt
            if not self.tare_button_was_pressed:

                self.tare_button_was_pressed = True

                print()
                print(
                    ">>> TARE-KNAPP TRYCKT <<<"
                )
                print(
                    "Tarering begärd från "
                    "fysisk knapp..."
                )

                success = self.tare()

                if success:

                    print(
                        "Knapp-tarering klar."
                    )
                    print()

        else:

            # Knappen har släppts och kan
            # registreras igen nästa gång.
            self.tare_button_was_pressed = False

    # ========================================================
    # UPPDATERA LCD
    # ========================================================

    def update_lcd_weight(
        self,
        weight
    ):

        # ----------------------------------------------------
        # LCD-belysning
        # ----------------------------------------------------

        if weight >= LCD_WEIGHT_LIMIT:

            lcd.backlight_enabled = True

            self.lcd_below_limit_since = None

        else:

            # Starta släck-timern
            if (
                self.lcd_below_limit_since
                is None
            ):

                self.lcd_below_limit_since = (
                    time.monotonic()
                )

            elapsed = (
                time.monotonic()
                - self.lcd_below_limit_since
            )

            if elapsed >= LCD_OFF_DELAY:

                lcd.backlight_enabled = False

        # ----------------------------------------------------
        # LCD-text
        # ----------------------------------------------------

        weight_text = (
            f"{weight:.1f} g"
        )

        self.lcd_message(
            "      HopScale",
            "",
            f"Weight: {weight_text}",
            "       READY"
        )

    # ========================================================
    # SKRIV HOPSCALE.JSON
    # ========================================================

    def write_json(
        self,
        weight
    ):

        data = {
            "weight_g": weight,
            "timestamp":
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
        }

        try:

            with open(
                JSON_FILE,
                "w"
            ) as file:

                json.dump(
                    data,
                    file,
                    indent=4
                )

        except Exception as error:

            print(
                "Fel vid skrivning av "
                f"hopscale.json: {error}"
            )

    # ========================================================
    # WEBB-TARE VIA CONTROL.JSON
    # ========================================================

    def check_control(self):

        try:

            if not os.path.exists(
                CONTROL_FILE
            ):
                return

            with open(
                CONTROL_FILE,
                "r"
            ) as file:

                data = json.load(file)

            if data.get(
                "tare",
                False
            ):

                print()
                print(
                    ">>> TARE-KOMMANDO "
                    "MOTTAGET <<<"
                )

                print(
                    "Tarering begärd från "
                    "webbsidan..."
                )

                success = self.tare()

                if success:

                    data["tare"] = False

                    with open(
                        CONTROL_FILE,
                        "w"
                    ) as file:

                        json.dump(
                            data,
                            file,
                            indent=4
                        )

                    print(
                        "Webbtarering klar."
                    )

                    print(
                        "control.json "
                        "återställd till "
                        "tare=false"
                    )

                    print()

        except Exception as error:

            print(
                "Fel vid läsning av "
                f"control.json: {error}"
            )

    # ========================================================
    # CLEANUP
    # ========================================================

    def cleanup(self):

        # Stäng gpiozero-knappen
        try:
            self.tare_button.close()
        except Exception:
            pass

        # Släck och stäng LCD
        try:

            lcd.backlight_enabled = False
            lcd.clear()
            lcd.close(clear=True)

        except Exception:

            pass

        # Städa HX711 GPIO
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

        print(
            "Väntar på stabilisering..."
        )

        scale.lcd_message(
            "      HopScale",
            "",
            "   Stabilizing...",
            ""
        )

        time.sleep(2.0)

        print()
        print(
            "Se till att vågen är TOM."
        )
        print()

        if not scale.tare():

            raise RuntimeError(
                "Kunde inte tarera vågen."
            )

        print()
        print("HopScale är redo.")
        print(
            "Tryck Ctrl+C för att avsluta."
        )
        print()

        # ====================================================
        # HUVUDLOOP
        # ====================================================

        while True:

            # -----------------------------------------------
            # Fysisk TARE-knapp
            # -----------------------------------------------

            scale.check_tare_button()

            # -----------------------------------------------
            # Webbtarering
            # -----------------------------------------------

            scale.check_control()

            # -----------------------------------------------
            # Läs vikt
            # -----------------------------------------------

            raw, diff, weight = (
                scale.get_weight()
            )

            if raw is not None:

                print(
                    f"Raw: {raw:12.1f}   "
                    f"Diff: {diff:10.1f}   "
                    f"Vikt: {weight:7.1f} g"
                )

                # JSON
                scale.write_json(
                    weight
                )

                # LCD
                scale.update_lcd_weight(
                    weight
                )

            else:

                print(
                    "Ingen giltig mätning "
                    "från HX711"
                )

                lcd.backlight_enabled = True

                scale.lcd_below_limit_since = None

                scale.lcd_message(
                    "      HopScale",
                    "",
                    "    HX711 ERROR",
                    ""
                )

            time.sleep(
                READ_INTERVAL
            )

    except KeyboardInterrupt:

        print()
        print(
            "Avslutar HopScale..."
        )

    except Exception as error:

        print()
        print(
            f"Fel: {error}"
        )

    finally:

        if scale is not None:

            scale.cleanup()

        else:

            GPIO.cleanup()

        print(
            "GPIO städat."
        )