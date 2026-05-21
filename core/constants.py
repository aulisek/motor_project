"""
Application-wide constants and default configuration values.
All magic numbers should be centralized here.
"""

# --- Hardware & ADC Constants ---
ADC_VOLTAGE = 5.084
ADC_MAX_VALUE = 0x7FFFFF
DEFAULT_ADC_CHANNEL = 2
DEFAULT_DHT_PIN = 4

# --- Motor & Motion Constants ---
COUNTS_PER_REV = 3600.0
DEFAULT_HOME_POSITION = 3600
DEFAULT_KINEMATICS_VALUE = 300
ABSOLUTE_ENCODER_HOME = 4294961690 # Hardcoded 0° position for absolute encoder

# --- Measurement & Circuit Constants ---
DEFAULT_REFERENCE_RESISTANCE = 110000.0
DEFAULT_RESISTOR_POSITION = "Top (High Side)"

# --- Data Logging & UI ---
CSV_OUTPUT_FOLDER = "measurements"
PLOT_BUFFER_SIZE = 500
PLOT_UPDATE_INTERVAL_MS = 50