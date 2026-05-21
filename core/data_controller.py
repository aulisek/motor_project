"""
Data Acquisition (DAQ) Controller Module.
Provides threaded background reading of sensors (ADC, DHT22) and motor parameters.
"""
from PyQt5.QtCore import QThread, pyqtSignal
import RPi.GPIO as GPIO

# Nové importy pro senzor DHT22
import board
import adafruit_dht

import time
import csv
import datetime
import threading
import os
import logging

logger = logging.getLogger(__name__)

from hardware.ADS1256 import ADS1256, ADS1256_GAIN_E, ADS1256_DRATE_E
import core.constants as const


def _parse_rate_value(name: str) -> float:
    """Convert rate tokens like ADS1256_2d5SPS into float SPS values."""
    raw = name.split("_")[1]
    raw = raw.replace("d", ".").replace("SPS", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _format_rate_label(value: float) -> str:
    """Format a sampling rate float into a human-readable string."""
    if value >= 1000:
        return f"{value / 1000:.1f} kSPS"
    return f"{value:.1f} SPS"


ADS1256_SAMPLE_RATES = {
    name: {"code": code, "sps": _parse_rate_value(name)}
    for name, code in ADS1256_DRATE_E.items()
    if _parse_rate_value(name) <= 10.0
}

DEFAULT_ADS1256_RATE_KEY = "ADS1256_10SPS"

ADS1256_SAMPLE_RATE_LABELS = [
    (key, _format_rate_label(values["sps"])) for key, values in ADS1256_SAMPLE_RATES.items()
]

class DAQController(QThread):
    """
    A PyQt5 QThread responsible for continuous data acquisition.
    Communicates via pyqtSignal to update the GUI without blocking it.
    Handles ADS1256 ADC conversions, DHT22 readings, motor position queries,
    and CSV logging.
    """
    data_signal = pyqtSignal(float, float, float, float, float, float)  # timestamp, position, resistance, humidity, temperature, voltage

    def __init__(self, motor_controller, sample_rate=10, gui_rate=10):
        super().__init__()
        """Initialize hardware connections, shared state, and timing configs."""
        self.running = False
        self.motor_controller = motor_controller
        self.sample_rate_hz = max(1, int(sample_rate))
        self.gui_rate_hz = max(1, int(gui_rate))
        self._config_lock = threading.Lock()
        self._apply_timing_config()
        self._ads_rate_key = DEFAULT_ADS1256_RATE_KEY
        self.reference_resistance = const.DEFAULT_REFERENCE_RESISTANCE
        self.resistor_position = const.DEFAULT_RESISTOR_POSITION

        # === Init ADS1256 ===
        self.adc = ADS1256()
        if self.adc.ADS1256_init() != 0:
            raise RuntimeError("ADS1256 initialization failed.")
        self._configure_adc_rate(self._ads_rate_key)
        self.adc.ADS1256_SetMode(0)  # 0 = single-ended, 1 = differential
        self.adc_channel = const.DEFAULT_ADC_CHANNEL

        # === Init DHT22 (Nová implementace Adafruit) ===
        self.dht_pin = const.DEFAULT_DHT_PIN
        
        try:
            # Dynamický převod čísla z konstant (např. 5) na objekt (board.D5)
            dht_board_pin = getattr(board, f"D{self.dht_pin}")
            # use_pulseio=False je klíčové pro stabilitu na Raspberry Pi 5
            self.dht_instance = adafruit_dht.DHT22(dht_board_pin, use_pulseio=False)
        except AttributeError:
            logger.error(f"[DAQ] Neplatný pin pro DHT22: D{self.dht_pin}")
            self.dht_instance = None
            
        self.humidity = 0.0
        self.temperature = 0.0

        # === Init motor position ===
        self.position_lock = threading.Lock()
        self.position = 0.0
        self.position_thread = None
        self.iteration_count = 0

        self.log_file = None
        self.csv_writer = None
        self.experiment_metadata = {}
        self.current_cycle = 1

    def _apply_timing_config(self):
        """Recalculate timing intervals based on the configured sample rate."""
        self.loop_sleep = 1.0 / float(self.sample_rate_hz)
        self.dht_interval = max(1, int(self.sample_rate_hz * 2))
        self.position_interval = max(1, int(self.sample_rate_hz // 10) or 1)
        gui_divider = max(1, int(self.sample_rate_hz // self.gui_rate_hz))
        self.gui_interval = gui_divider

    def init_log_file(self, metadata=None):
        # === Create folder if it doesn't exist ===
        os.makedirs(const.CSV_OUTPUT_FOLDER, exist_ok=True)

        # === Create timestamped file name ===
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(const.CSV_OUTPUT_FOLDER, f"measurement_{timestamp_str}.csv")

        # === Open file for writing ===
        self.log_file = open(filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self._write_metadata_header(metadata or {})
        self.csv_writer.writerow(["timestamp", "position", "resistance", "humidity", "temperature", "cycle"])

        logger.info(f"[DAQ] Logging started → {filename}")

    def update_position_loop(self):
        """
        Dedicated loop to fetch motor position. Runs in its own thread to avoid
        blocking the main DAQ timing loop if the motor controller responds slowly.
        """
        while self.running:
            try:
                new_position = self.motor_controller.get_position()
                with self.position_lock:
                    self.position = new_position
            except Exception as e:
                logger.error(f"[Motor Read Error] {e}")

    def run(self):
        """Main thread execution block for Data Acquisition."""
        self.running = True
        self.start_time = time.perf_counter()
        self.position_thread = threading.Thread(target=self.update_position_loop, daemon=True)
        self.position_thread.start()

        while self.running:
            self.iteration_count += 1
            loop_start = time.perf_counter()
            timestamp = time.time()

            with self._config_lock:
                dht_interval = self.dht_interval
                position_interval = self.position_interval
                gui_interval = self.gui_interval
                loop_sleep = self.loop_sleep
                reference_res = self.reference_resistance
                res_pos = self.resistor_position
                current_cycle = self.current_cycle

            # === Read ADC ===
            adc_raw = self.adc.ADS1256_GetChannalValue(self.adc_channel)
            voltage = adc_raw * const.ADC_VOLTAGE / const.ADC_MAX_VALUE  # convert to volts
            try:
                reference = max(0.0001, float(reference_res))
                if "Top" in res_pos:
                    # Unknown is Top (High Side), Reference is Bottom (Low Side). Measuring across Reference.
                    resistance = ((const.ADC_VOLTAGE - voltage) / voltage) * reference
                else:
                    # Unknown is Bottom (Low Side), Reference is Top (High Side). Measuring across Unknown.
                    resistance = (reference * voltage) / (const.ADC_VOLTAGE - voltage)
            except (ZeroDivisionError, ValueError):
                resistance = 0.0

            # === Read motor ===
            if self.iteration_count % position_interval == 0:
                with self.position_lock:
                    position = self.position
            else:
                position = self.position

            # === Read DHT22 (Nová implementace Adafruit) ===
            if self.iteration_count % dht_interval == 0 and self.dht_instance is not None:
                try:
                    t = self.dht_instance.temperature
                    h = self.dht_instance.humidity
                    
                    if t is not None and h is not None:
                        self.temperature = t
                        self.humidity = h
                except RuntimeError:
                    # Běžný výpadek senzoru (např. kontrolní součet selhal) - ignorujeme, GUI ukáže poslední známou hodnotu
                    pass
                except Exception as e:
                    logger.error(f"[DHT22 Error] {e}")

            # === Emit GUI signal ===
            if self.iteration_count % gui_interval == 0:
                self.data_signal.emit(timestamp, position, resistance, self.humidity, self.temperature, voltage)

            # === Write to CSV ===
            with self._config_lock:
                if self.csv_writer:
                    self.csv_writer.writerow([timestamp, position, resistance, self.humidity, self.temperature, current_cycle])

            # === No need to wait for the next iteration — PyQt ensures the thread runs separately ===
            time.sleep(max(0.0, loop_sleep - (time.perf_counter() - loop_start)))

        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.csv_writer = None

    def start_logging(self):
        """Enable CSV logging (opens a new file if not already open)."""
        with self._config_lock:
            if not self.csv_writer:
                self.init_log_file(self.experiment_metadata)

    def stop_logging(self):
        """Disable CSV logging (closes the active file)."""
        with self._config_lock:
            if self.log_file:
                self.log_file.close()
                self.log_file = None
                self.csv_writer = None

    def stop(self):
        """Gracefully stop the DAQ loop, position thread, and close file handlers."""
        if not self.isRunning():
            return

        self.running = False
        self.wait()

        if self.position_thread and self.position_thread.is_alive():
            self.position_thread.join()
        self.position_thread = None

        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.csv_writer = None
            
        # DŮLEŽITÉ: Uvolnění senzoru při vypnutí, aby neblokoval pin pro další spuštění
        if getattr(self, 'dht_instance', None):
            try:
                self.dht_instance.exit()
            except Exception:
                pass

    def change_sample_rate(self, rate_hz):
        """Update the acquisition rate (Hz)."""
        with self._config_lock:
            self.sample_rate_hz = max(1, int(rate_hz))
            self._apply_timing_config()

    def _configure_adc_rate(self, rate_key: str):
        """Configure the ADS1256 sample rate based on the requested rate key."""
        if rate_key not in ADS1256_SAMPLE_RATES:
            rate_key = DEFAULT_ADS1256_RATE_KEY
            
        self.adc.ADS1256_ConfigADC(
            ADS1256_GAIN_E['ADS1256_GAIN_1'],
            ADS1256_SAMPLE_RATES[rate_key]["code"]
        )

    def set_ads1256_sample_rate(self, rate_key: str):
        """Public hook to adjust sampling speed using predefined presets."""
        if rate_key not in ADS1256_SAMPLE_RATES:
            rate_key = DEFAULT_ADS1256_RATE_KEY
        self._ads_rate_key = rate_key
        target = ADS1256_SAMPLE_RATES[rate_key]["sps"]
        self.change_sample_rate(max(1, int(round(target))))
        self._configure_adc_rate(rate_key)

    def set_experiment_metadata(self, metadata: dict):
        """Store metadata so the next logging session includes it in the header."""
        self.experiment_metadata = metadata or {}

    def set_reference_resistance(self, value: float):
        """Update the voltage divider reference resistor value dynamically."""
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return
        if numeric_value <= 0:
            return
        with self._config_lock:
            self.reference_resistance = numeric_value

    def set_resistor_position(self, position: str):
        """Set whether the reference resistor is on the Top (High Side) or Bottom (Low Side)."""
        with self._config_lock:
            self.resistor_position = position

    def set_current_cycle(self, cycle: int):
        """Updates the current cycle number for CSV logging."""
        with self._config_lock:
            self.current_cycle = cycle

    def cleanup(self):
        """Stop acquisition thread safely and release GPIO resources."""
        self.stop()
        GPIO.cleanup()

    def _write_metadata_header(self, metadata: dict):
        """Format and write human-readable experiment metadata into the CSV header."""
        if not self.log_file:
            return
        lines = []
        name = metadata.get("experiment_name")
        if name:
            lines.append(f"Experiment: {name}")
        description = metadata.get("experiment_description")
        if description:
            lines.append("Description:")
            for desc_line in description.splitlines():
                lines.append(f"  {desc_line}")
        daq_label = metadata.get("daq_rate_label")
        if daq_label:
            lines.append(f"DAQ rate: {daq_label} (key: {metadata.get('daq_rate_key', '')})")
        # ... zbytek vašeho formátování metadat zůstává beze změny ...
        repetitions = metadata.get("repetitions")
        if repetitions:
            lines.append(f"Repetitions: {repetitions}")
        accel = metadata.get("acceleration")
        if accel:
            lines.append(
                "Acceleration: "
                f"max={accel.get('max_acc')} | profile={accel.get('profile_acc')}"
            )
        decel = metadata.get("deceleration")
        if decel:
            lines.append(
                "Deceleration: "
                f"max={decel.get('max_dec')} | profile={decel.get('profile_dec')}"
            )
        velocity = metadata.get("velocity")
        if velocity is not None:
            lines.append(f"Profile velocity: {velocity}")
        ref_res = metadata.get("reference_resistance")
        if ref_res:
            lines.append(f"Reference resistor: {ref_res} Ω")
        res_pos = metadata.get("resistor_position")
        if res_pos:
            lines.append(f"Resistor Position: {res_pos}")
        loop_mode = metadata.get("loop_mode")
        if loop_mode:
            lines.append(f"Control Mode: {loop_mode}")

        positions = metadata.get("positions")
        if positions:
            lines.append("Motion steps (angle°, counts, delay ms):")
            for idx, step in enumerate(positions, start=1):
                angle = step.get("degrees")
                if isinstance(angle, (int, float)):
                    angle_display = f"{angle:.2f}"
                else:
                    angle_display = str(angle)
                counts = step.get("counts")
                delay = step.get("delay_ms")
                lines.append(
                    f"  Step {idx}: {angle_display}°, counts={counts}, delay={delay} ms"
                )

        if not lines:
            return

        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_file.write(f"# Metadata recorded at {timestamp_str}\n")
        for line in lines:
            self.log_file.write(f"# {line}\n")
        self.log_file.write("#\n")