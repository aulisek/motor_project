import pyqtgraph as pg
from pyqtgraph import PlotWidget
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import ADS1263
import RPi.GPIO as GPIO
import random
import time
import serial
import csv
import datetime
import threading

class DAQController(QThread):
    data_signal = pyqtSignal(float, float, float, float, float)  # timestamp, position, resistance, humidity, temperature

    def __init__(self, motor_controller, sample_rate=400, gui_rate=5):
        super().__init__()
        self.running = False
        self.sample_rate = 400
        self.gui_rate = 5
        self.motor_controller = motor_controller

        # Initialize ADS1263 ADC
        self.adc = ADS1263.ADS1263()
        if self.adc.ADS1263_init_ADC1() == -1:
            raise RuntimeError("Failed to initialize ADS1263.")
        self.adc.ADS1263_SetMode(0)  # Single-ended mode
        self.channel = 4
        self.adc.ADS1263_init_ADC1('ADS1263_400SPS')

        # DHT22 sensor config
        self.dht_pin = 17  # GPIO17
        # self.dht_sensor = Adafruit_DHT.DHT22

        self.position_lock = threading.Lock()
        self.position = 0.0
        self.position_thread = threading.Thread(target=self.update_position_loop)
        self.position_thread.daemon = True

        # Timings
        self.dht_interval = self.sample_rate * 2  # every 2 seconds
        self.position_interval = self.sample_rate // 10  # every 2 seconds
        self.gui_interval = self.sample_rate // self.gui_rate
        self.iteration_count = 0

        self.log_file = None
        self.csv_writer = None

    def init_log_file(self):
        """Create and open a CSV log file with a timestamped name."""
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"measurement_{timestamp_str}.csv"
        self.log_file = open(filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow(["timestamp", "position", "resistance", "humidity", "temperature"])  # Header row

    def update_position_loop(self):
        while self.running:
            try:
                new_position = self.motor_controller.get_position()
                with self.position_lock:
                    self.position = new_position
            except Exception as e:
                print(f"[Motor Read Error] {e}")
            time.sleep(0.03)  # 50 ms

    def run(self):
        self.running = True
        self.init_log_file()
        self.start_time = time.perf_counter()
        self.position_thread.start()

        humidity = 0.0
        temperature = 0.0
        position = 0.0

        while self.running:
            self.iteration_count += 1
            loop_start = time.perf_counter()
            timestamp = time.time()

            # Read from ADS1263
            adc_raw = self.adc.ADS1263_GetChannalValue(0)
            voltage = adc_raw * 5.116 / 0x7fffffff
            resistance = (voltage * 120000) / (5.116 - voltage)
            #resistance = voltage

            # Get motor position
           #if self.iteration_count % self.position_interval == 0:
            #tick = time.perf_counter()
                #position = self.motor_controller.get_position()
            #print(f"get_position time: {time.perf_counter() - tick:.6f}s")
            # Read shared motor position
            if self.iteration_count % self.position_interval == 0:
                with self.position_lock:
                    position = self.position
            #position = random.random()  # Simulated value

            # Read from DHT22 every 2 seconds
            if self.iteration_count % self.dht_interval == 0:
                #print(f"Reading DHT22 at {time.perf_counter() - self.start_time:.3f}s")
                # humidity, temperature = Adafruit_DHT.read_retry(self.dht_sensor, self.dht_pin)
                humidity = 0.0
                temperature = 0.0

            # Update GUI and log file
            if self.iteration_count % self.gui_interval == 0:
                self.data_signal.emit(timestamp, position, resistance, humidity, temperature)
                #print(f"Logging at {time.perf_counter() - self.start_time:.3f}s")
            # append to file
            self.csv_writer.writerow([timestamp, position, resistance, humidity, temperature])
            # Debug timing
            loop_duration = time.perf_counter() - loop_start
            #print(f"Iteration {self.iteration_count}, loop time: {loop_duration:.6f} sec")

    def stop(self):
        self.running = False
        self.position_thread.join()
        self.wait()
        if self.log_file:
            self.log_file.close()
        GPIO.cleanup()