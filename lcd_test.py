from RPLCD.i2c import CharLCD
import time


LCD_ADDRESS = 0x27


lcd = CharLCD(
    i2c_expander="PCF8574",
    address=LCD_ADDRESS,
    port=1,
    cols=20,
    rows=4,
    charmap="A00",
    auto_linebreaks=True
)

try:

    lcd.clear()

    lcd.write_string("HopScale")
    lcd.crlf()

    lcd.write_string("LCD test")
    lcd.crlf()

    lcd.write_string("I2C: 0x27")
    lcd.crlf()

    lcd.write_string("Ready!")

    time.sleep(10)

finally:

    lcd.clear()
    lcd.close(clear=True)
