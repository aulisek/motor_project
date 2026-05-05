"""
Data Acquisition (DAQ) Controller Module.
Provides threaded background reading of sensors (ADC, DHT22) and motor parameters.
"""
from PyQt5.QtCore import QThread, pyqtSignal
import RPi.GPIO as GPIO
import dht22
import time
import csv
import datetime
import threading
import os


from ADS1256 import ADS1256, ADS1256_GAIN_E, ADS1256_DRATE_E


def _parse_rate_value(name: str) -> float:
    """Convert rate tokens like ADS1263_16d6SPS into float SPS values."""
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


ADS1263_SAMPLE_RATES = {
    "ADS1263_38400SPS": {"code": 0xF, "sps": 38400.0},
    "ADS1263_19200SPS": {"code": 0xE, "sps": 19200.0},
    "ADS1263_14400SPS": {"code": 0xD, "sps": 14400.0},
    "ADS1263_7200SPS": {"code": 0xC, "sps": 7200.0},
    "ADS1263_4800SPS": {"code": 0xB, "sps": 4800.0},
    "ADS1263_2400SPS": {"code": 0xA, "sps": 2400.0},
    "ADS1263_1200SPS": {"code": 0x9, "sps": 1200.0},
    "ADS1263_400SPS": {"code": 0x8, "sps": 400.0},
    "ADS1263_100SPS": {"code": 0x7, "sps": 100.0},
    "ADS1263_60SPS": {"code": 0x6, "sps": 60.0},
    "ADS1263_50SPS": {"code": 0x5, "sps": 50.0},
    "ADS1263_20SPS": {"code": 0x4, "sps": 20.0},
    "ADS1263_16d6SPS": {"code": 0x3, "sps": 16.6},
    "ADS1263_10SPS": {"code": 0x2, "sps": 10.0},
    "ADS1263_5SPS": {"code": 0x1, "sps": 5.0},
    "ADS1263_2d5SPS": {"code": 0x0, "sps": 2.5},
}

DEFAULT_ADS1263_RATE_KEY = "ADS1263_10SPS"

ADS1263_SAMPLE_RATE_LABELS = [
    (key, _format_rate_label(values["sps"])) for key, values in ADS1263_SAMPLE_RATES.items()
]

ADS1256_RATE_VALUES = {
    name: _parse_rate_value(name) for name in ADS1256_DRATE_E.keys()
}

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
        self._ads_rate_key = DEFAULT_ADS1263_RATE_KEY
        self.reference_resistance = 110000.0  # default reference resistor (Ohms)
        self.resistor_position = "Top (High Side)"

        # === Init ADS1256 ===
        self.adc = ADS1256()
        if self.adc.ADS1256_init() != 0:
            raise RuntimeError("ADS1256 initialization failed.")
        self._configure_adc_rate(self._ads_rate_key)
        self.adc.ADS1256_SetMode(0)  # 0 = single-ended, 1 = differential
        self.adc_channel = 2  # e.g., AIN0

        # === Init DHT22 ===
        self.dht_pin = 4  # GPIO17
        self.dht_instance = dht22.DHT22(pin=self.dht_pin)
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

    def _apply_timing_config(self):
        """Recalculate timing intervals based on the configured sample rate."""
        self.loop_sleep = 1.0 / float(self.sample_rate_hz)
        self.dht_interval = max(1, int(self.sample_rate_hz * 2))
        self.position_interval = max(1, int(self.sample_rate_hz // 10) or 1)
        gui_divider = max(1, int(self.sample_rate_hz // self.gui_rate_hz))
        self.gui_interval = gui_divider

    def init_log_file(self, metadata=None):
        # === Create folder if it doesn't exist ===
        os.makedirs("measurements", exist_ok=True)

        # === Create timestamped file name ===
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join("measurements", f"measurement_{timestamp_str}.csv")

        # === Open file for writing ===
        self.log_file = open(filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self._write_metadata_header(metadata or {})
        self.csv_writer.writerow(["timestamp", "position", "resistance", "humidity", "temperature"])

        print(f"[DAQ] Logging started → {filename}")

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
                print(f"[Motor Read Error] {e}")

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

            # === Read ADC ===
            adc_raw = self.adc.ADS1256_GetChannalValue(self.adc_channel)
            voltage = adc_raw * 5.084 / 0x7FFFFF  # convert to volts
            try:
                reference = max(0.0001, float(reference_res))
                if "Top" in res_pos:
                    # Unknown is Top (High Side), Reference is Bottom (Low Side). Measuring across Reference.
                    # R_unk = R_ref * (Vin - Vout) / Vout
                    resistance = ((5.084 - voltage) / voltage) * reference
                else:
                    # Unknown is Bottom (Low Side), Reference is Top (High Side). Measuring across Unknown.
                    # R_unk = R_ref * Vout / (Vin - Vout)
                    resistance = (reference * voltage) / (5.084 - voltage)
            except (ZeroDivisionError, ValueError):
                resistance = 0.0

            # === Read motor ===
            if self.iteration_count % position_interval == 0:
                with self.position_lock:
                    position = self.position
            else:
                position = self.position

            # === Read DHT22 ===
            if self.iteration_count % dht_interval == 0:
                result = self.dht_instance.read()
                if result.is_valid():
                    self.humidity = result.humidity
                    self.temperature = result.temperature

            # === Emit GUI signal ===
            if self.iteration_count % gui_interval == 0:
                self.data_signal.emit(timestamp, position, resistance, self.humidity, self.temperature, voltage)

            # === Write to CSV ===
            with self._config_lock:
                if self.csv_writer:
                    self.csv_writer.writerow([timestamp, position, resistance, self.humidity, self.temperature])

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

    def change_sample_rate(self, rate_hz):
        """
        Update the acquisition rate (Hz).
        Args:
            rate_hz (int): Desired main loop frequency.
        """
        with self._config_lock:
            self.sample_rate_hz = max(1, int(rate_hz))
            self._apply_timing_config()

    def _configure_adc_rate(self, rate_key: str):
        """
        Map the requested ADS1263 rate string to the closest ADS1256 configuration.
        Args:
            rate_key (str): The configuration key mapping (e.g., 'ADS1263_10SPS').
        """
        target = ADS1263_SAMPLE_RATES.get(rate_key, ADS1263_SAMPLE_RATES[DEFAULT_ADS1263_RATE_KEY])["sps"]
        best_ads1256 = min(ADS1256_RATE_VALUES.items(), key=lambda item: abs(item[1] - target))[0]
        self.adc.ADS1256_ConfigADC(
            ADS1256_GAIN_E['ADS1256_GAIN_1'],
            ADS1256_DRATE_E[best_ads1256]
        )

    def set_ads1263_sample_rate(self, rate_key: str):
        """
        Public hook to adjust sampling speed using predefined presets.
        Args:
            rate_key (str): Chosen preset rate key.
        """
        if rate_key not in ADS1263_SAMPLE_RATES:
            rate_key = DEFAULT_ADS1263_RATE_KEY
        self._ads_rate_key = rate_key
        target = ADS1263_SAMPLE_RATES[rate_key]["sps"]
        self.change_sample_rate(max(1, int(round(target))))
        self._configure_adc_rate(rate_key)

    def set_experiment_metadata(self, metadata: dict):
        """Store metadata so the next logging session includes it in the header."""
        self.experiment_metadata = metadata or {}

    def set_reference_resistance(self, value: float):
        """
        Update the voltage divider reference resistor value dynamically.
        Args:
            value (float): Resistance in Ohms.
        """
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
