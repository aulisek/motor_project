from PyQt5.QtCore import QThread, pyqtSignal
import RPi.GPIO as GPIO
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

DEFAULT_ADS1263_RATE_KEY = "ADS1263_400SPS"

ADS1263_SAMPLE_RATE_LABELS = [
    (key, _format_rate_label(values["sps"])) for key, values in ADS1263_SAMPLE_RATES.items()
]

ADS1256_RATE_VALUES = {
    name: _parse_rate_value(name) for name in ADS1256_DRATE_E.keys()
}

class DAQController(QThread):
    data_signal = pyqtSignal(float, float, float, float, float)  # timestamp, position, resistance, humidity, temperature

    def __init__(self, motor_controller, sample_rate=10, gui_rate=10):
        super().__init__()
        self.running = False
        self.motor_controller = motor_controller
        self.sample_rate_hz = max(1, int(sample_rate))
        self.gui_rate_hz = max(1, int(gui_rate))
        self._config_lock = threading.Lock()
        self._apply_timing_config()
        self._ads_rate_key = DEFAULT_ADS1263_RATE_KEY

        # === Init ADS1256 ===
        self.adc = ADS1256()
        if self.adc.ADS1256_init() != 0:
            raise RuntimeError("ADS1256 initialization failed.")
        self._configure_adc_rate(self._ads_rate_key)
        self.adc.ADS1256_SetMode(0)  # 0 = single-ended, 1 = differential
        self.adc_channel = 2  # e.g., AIN0

        # === Init DHT22 ===
        self.dht_pin = 17  # GPIO17
        self.humidity = 0.0
        self.temperature = 0.0

        # === Init motor position ===
        self.position_lock = threading.Lock()
        self.position = 0.0
        self.position_thread = None
        self.iteration_count = 0

        self.log_file = None
        self.csv_writer = None

    def _apply_timing_config(self):
        """Recalculate timing intervals based on the configured sample rate."""
        self.loop_sleep = 1.0 / float(self.sample_rate_hz)
        self.dht_interval = max(1, int(self.sample_rate_hz * 2))
        self.position_interval = max(1, int(self.sample_rate_hz // 10) or 1)
        gui_divider = max(1, int(self.sample_rate_hz // self.gui_rate_hz))
        self.gui_interval = gui_divider

    def init_log_file(self):
        # === Create folder if it doesn't exist ===
        os.makedirs("measurements", exist_ok=True)

        # === Create timestamped file name ===
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join("measurements", f"measurement_{timestamp_str}.csv")

        # === Open file for writing ===
        self.log_file = open(filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow(["timestamp", "position", "resistance", "humidity", "temperature"])

        print(f"[DAQ] Logging started → {filename}")

    def update_position_loop(self):
        while self.running:
            try:
                new_position = self.motor_controller.get_position()
                with self.position_lock:
                    self.position = new_position
            except Exception as e:
                print(f"[Motor Read Error] {e}")
            time.sleep(0.03)  # 30 ms ≈ 33 Hz

    def run(self):
        self.running = True
        self.init_log_file()
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

            # === Read ADC ===
            adc_raw = self.adc.ADS1256_GetChannalValue(self.adc_channel)
            voltage = adc_raw * 5.0 / 0x7FFFFF  # convert to volts
            try:
                resistance = (voltage * 110000) / (5.0 - voltage)  # resistance in ohms (assuming voltage divider)
                # resistance = voltage
            except ZeroDivisionError:
                resistance = 0.0

            # === Read motor ===
            if self.iteration_count % position_interval == 0:
                with self.position_lock:
                    position = self.position
            else:
                position = self.position

            # === Read DHT22 ===
            if self.iteration_count % dht_interval == 0:
                # humidity, temperature = Adafruit_DHT.read_retry(...)
                self.humidity = 0.0
                self.temperature = 0.0

            # === Emit GUI signal ===
            if self.iteration_count % gui_interval == 0:
                self.data_signal.emit(timestamp, position, resistance, self.humidity, self.temperature)

            # === Write to CSV ===
            self.csv_writer.writerow([timestamp, position, resistance, self.humidity, self.temperature])

            # === No need to wait for the next iteration — PyQt ensures the thread runs separately ===
            time.sleep(max(0.0, loop_sleep - (time.perf_counter() - loop_start)))

        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.csv_writer = None

    def stop(self):
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

        GPIO.cleanup()

    def change_sample_rate(self, rate_hz):
        """Update the acquisition rate (Hz)."""
        with self._config_lock:
            self.sample_rate_hz = max(1, int(rate_hz))
            self._apply_timing_config()

    def _configure_adc_rate(self, rate_key: str):
        """Map the requested ADS1263 rate to the closest ADS1256 configuration."""
        target = ADS1263_SAMPLE_RATES.get(rate_key, ADS1263_SAMPLE_RATES[DEFAULT_ADS1263_RATE_KEY])["sps"]
        best_ads1256 = min(ADS1256_RATE_VALUES.items(), key=lambda item: abs(item[1] - target))[0]
        self.adc.ADS1256_ConfigADC(
            ADS1256_GAIN_E['ADS1256_GAIN_1'],
            ADS1256_DRATE_E[best_ads1256]
        )

    def set_ads1263_sample_rate(self, rate_key: str):
        """Public hook to adjust sampling speed using ADS1263-style presets."""
        if rate_key not in ADS1263_SAMPLE_RATES:
            rate_key = DEFAULT_ADS1263_RATE_KEY
        self._ads_rate_key = rate_key
        target = ADS1263_SAMPLE_RATES[rate_key]["sps"]
        self.change_sample_rate(max(1, int(round(target))))
        self._configure_adc_rate(rate_key)
