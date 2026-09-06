# HopScale 🌿⚖️

HopScale is a Raspberry Pi based digital scale designed for accurately weighing hops during homebrewing.

The project uses a **1 kg load cell** connected through an **HX711 24-bit ADC** to a Raspberry Pi. Weight measurements are filtered and calibrated in Python and displayed both on a local **20×4 LCD** and through a Flask-based web interface.

The scale displays weight with a resolution of **0.1 g**, making it well suited for measuring hop additions during brewing.

## Web Interface

The HopScale web interface displays the measured weight in real time and provides a remote **TARE** function.

![HopScale Web Interface](docs/images/hopscale_web.png)

The interface can be opened from computers, tablets, or mobile phones connected to the same network as the Raspberry Pi.

## Features

* 1 kg load cell
* HX711 24-bit ADC
* Direct HX711 communication using RPi.GPIO
* 0.1 g displayed resolution
* Multiple-sample averaging
* Minimum and maximum sample rejection
* Automatic tare at startup
* Physical TARE button
* Remote TARE from the web interface
* 20×4 LCD display
* Automatic LCD backlight control
* JSON status output
* Flask web server
* Live weight updates using JavaScript
* Responsive web interface for desktop and mobile devices

## Hardware

The current hardware consists of:

* Raspberry Pi
* HX711 load cell amplifier / ADC
* 1 kg load cell
* 2004A 20×4 character LCD with I²C interface
* Momentary push button for TARE

## GPIO Connections

### HX711

| HX711 | Raspberry Pi             |
| ----- | ------------------------ |
| DT    | GPIO 21                  |
| SCK   | GPIO 26                  |
| VCC   | Appropriate HX711 supply |
| GND   | GND                      |

### TARE Button

The physical TARE button is connected between:

| Button     | Raspberry Pi |
| ---------- | ------------ |
| Terminal 1 | GPIO 17      |
| Terminal 2 | GND          |

The software uses the Raspberry Pi internal pull-up resistor through `gpiozero`.

No external pull-up resistor is required.

### LCD 2004A

The LCD uses an I²C backpack at address:

```text
0x27
```

Connections:

| LCD I²C | Raspberry Pi |
| ------- | ------------ |
| SDA     | GPIO 2       |
| SCL     | GPIO 3       |
| GND     | GND          |
| VCC     | LCD supply   |

The I²C address can be checked with:

```bash
i2cdetect -y 1
```

A typical result for the current display is:

```text
27
```

## LCD Display

During normal operation, the LCD displays the current weight:

```text
      HopScale

Weight: 44.8 g
       READY
```

During tare:

```text
      HopScale

     TARING...
    Please wait
```

The LCD backlight automatically turns on when the measured weight reaches **1.0 g or more**.

When the weight falls below 1.0 g, a timer starts. If the weight remains below the limit for **5 seconds**, the backlight is switched off.

The delay is configured in `hopscale.py`:

```python
LCD_OFF_DELAY = 5.0
```

The backlight is automatically switched on during a tare operation.

## TARE Functions

HopScale can be tared in three ways.

### Automatic Startup Tare

When `hopscale.py` starts, the scale automatically performs a tare operation.

The weighing platform should therefore be empty during startup.

### Physical TARE Button

Pressing the button connected between **GPIO17 and GND** performs a new tare operation.

This allows HopScale to be used without opening the web interface.

### Web TARE

The web interface includes a **TARE** button.

When pressed:

1. JavaScript sends a POST request to Flask.
2. Flask writes a tare request to `control.json`.
3. `hopscale.py` detects the request.
4. A new tare offset is calculated.
5. `control.json` is reset to `false`.
6. The displayed weight returns to approximately `0.0 g`.

Example:

```json
{
    "tare": false
}
```

Both the physical button and web interface use the same tare function in `hopscale.py`.

## Calibration

HopScale is currently calibrated using ten Swedish 1-krona coins from 1973.

Each coin weighs approximately 7 g, giving a total reference weight of:

```text
10 × 7 g = 70 g
```

The current calibration factor is:

```python
CALIBRATION_FACTOR = 1063.1
```

Calibration tests produced approximately:

| Reference weight | HopScale |
| ---------------: | -------: |
|              7 g |    7.1 g |
|             35 g |   35.1 g |
|             70 g |   70.0 g |

## Measurement Filtering

To improve stability, HopScale takes multiple HX711 measurements for every displayed weight.

The measurement process is:

1. Read 10 raw HX711 samples.
2. Sort the samples.
3. Remove the lowest sample.
4. Remove the highest sample.
5. Calculate the mean of the remaining samples.
6. Subtract the tare offset.
7. Apply the calibration factor.
8. Display the result in grams.

Small variations close to zero are automatically displayed as `0.0 g`.

## Project Structure

```text
HopScale/
├── docs/
│   └── images/
│       └── hopscale_web.png
├── web/
│   ├── app.py
│   ├── static/
│   │   ├── script.js
│   │   └── style.css
│   └── templates/
│       └── index.html
├── .gitignore
├── control.json
├── hopscale.json
├── hopscale.py
├── requirements.txt
└── README.md
```

## Software Architecture

```text
                         ┌── 20x4 LCD
                         │
1 kg Load Cell           │
      │                  │
      ▼                  │
    HX711                │
      │                  │
      ▼                  │
 hopscale.py ─────────────┘
      │
      ├──────────► hopscale.json
      │                  │
      │                  ▼
      │               Flask
      │                  │
      │                  ▼
      │            Web Interface
      │                  │
      │               TARE
      │                  │
      ◄── control.json ◄─┘
      ▲
      │
GPIO17 TARE Button
```

`hopscale.py` handles:

* HX711 communication
* Measurement filtering
* Weight calculation
* Calibration
* Tare operations
* Physical TARE button
* LCD display
* LCD backlight control
* JSON status updates
* Web control commands

Flask provides the connection between `hopscale.py` and the browser.

## JSON Status

The current weight is continuously written to:

```text
hopscale.json
```

Example:

```json
{
    "weight_g": 70.0,
    "timestamp": "2026-09-06 09:27:15"
}
```

The Flask server exposes this through:

```text
/api/status
```

JavaScript periodically reads this endpoint and updates the displayed weight without reloading the page.

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd HopScale
```

Create a virtual environment:

```bash
python3 -m venv myenv
```

Activate it:

```bash
source myenv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

I²C must be enabled on the Raspberry Pi for the LCD.

It can be enabled using:

```bash
sudo raspi-config
```

Then select the I²C interface under the interface options.

The LCD can be detected using:

```bash
sudo apt install i2c-tools
i2cdetect -y 1
```

## Running HopScale

HopScale consists of two main processes.

### 1. Start the Scale

From the project directory:

```bash
source myenv/bin/activate
python hopscale.py
```

Make sure the weighing platform is empty during startup because HopScale automatically performs a tare.

### 2. Start the Web Server

Open another terminal:

```bash
cd web
python app.py
```

The Flask server listens on port:

```text
5000
```

Open a browser and navigate to the Raspberry Pi IP address followed by port 5000.

For example:

```text
http://192.168.1.100:5000
```

Replace the example address with the actual IP address of the Raspberry Pi.

## Python Dependencies

The project uses several Python packages including:

* Flask
* RPi.GPIO
* gpiozero
* RPLCD
* smbus2

The complete working environment is stored in:

```text
requirements.txt
```

After adding or updating dependencies, it can be regenerated with:

```bash
pip freeze > requirements.txt
```

## Notes

HopScale is designed primarily for weighing hops during homebrewing.

Displayed resolution is 0.1 g. Actual accuracy depends on the load cell, HX711 module, mechanical construction, electrical noise, temperature, and calibration.

The current 1 kg load cell and HX711 combination has shown good linearity in tests between 7 g and 70 g.

## Future Ideas

Possible future improvements include:

* Calibration from the web interface
* Configurable calibration factor
* Stability indicator
* Automatic startup using systemd
* Brewing recipe integration
* Hop addition presets
* Additional hardware documentation
* Wiring diagram / Fritzing drawing
* Enclosure design

## License

This project is intended for personal and educational use. Add a license file if you plan to distribute or reuse the project under a specific open-source license.
