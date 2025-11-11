from PyQt5.QtCore import QThread, pyqtSignal
import RPi.GPIO as GPIO
import time
import csv
import datetime
import threading
import os


from ADS1256 import ADS1256, ADS1256_GAIN_E, ADS1256_DRATE_E

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

        # === Init ADS1256 ===
        self.adc = ADS1256()
        if self.adc.ADS1256_init() != 0:
            raise RuntimeError("ADS1256 initialization failed.")
        self.adc.ADS1256_ConfigADC(
            ADS1256_GAIN_E['ADS1256_GAIN_1'],
            ADS1256_DRATE_E['ADS1256_10SPS']  # or another value as needed
        )
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
