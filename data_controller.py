import pyqtgraph as pg
from pyqtgraph import PlotWidget
import nidaqmx
from PyQt5.QtCore import QThread, pyqtSignal
from nidaqmx.constants import AcquisitionType




class NIDevice:
    def get_measurement(self):
        # Dummy function to simulate electrode data collection
        import random
        return random.uniform(0, 10)  # Example value
        #Create a task object
        with nidaqmx.Task() as task:
            #Add an analog input channel (A0) to the task
            #Replace "Dev1" with your device name
            task.ai_channels.add_ai_voltage_chan("Dev1/ai1")  
            
        #Read the value from the A0 channel
            #napeti = task.read()
           # odpor = (10000*(5-napeti)/napeti)
        #return odpor

class DAQController(QThread):
    data_signal = pyqtSignal(list)  # Emit data as a list for processing in the GUI

    def __init__(self, device_name="Dev1", channel="ai0", sample_rate=1000, buffer_size=100):
        super().__init__()
        self.device_name = device_name
        self.channel = channel
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.running = False

    def run(self):
        self.running = True
        with nidaqmx.Task() as task:
            # Configure the channel and task
            task.ai_channels.add_ai_voltage_chan(f"{self.device_name}/{self.channel}")
            task.timing.cfg_samp_clk_timing(self.sample_rate, sample_mode=AcquisitionType.CONTINUOUS)

            # Read data continuously
            while self.running:
                try:
                    # Fetch `buffer_size` samples at a time
                    data = task.read(number_of_samples_per_channel=self.buffer_size)
                    self.data_signal.emit(data)
                except nidaqmx.errors.DaqError as e:
                    print(f"DAQ Error: {e}")
                    break

    def stop(self):
        self.running = False
        self.wait()

# data_processor.py
class DataProcessor:
    def __init__(self):
        self.buffer = []

    def process_data(self, data):
        # Příklad: aplikace jednoduchého filtru
        filtered_data = [x for x in data if x > 0]  # Přizpůsobte podle potřeby.
        self.buffer.extend(filtered_data)
        return filtered_data

class DataLogger(QThread):
    log_signal = pyqtSignal(list)  # Signal to accept data for logging

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.running = False
        self.data_queue = []  # Internal buffer for incoming data

    def run(self):
        self.running = True
        while self.running:
            if self.data_queue:
                # Process and log the data from the queue
                data_to_log = self.data_queue.pop(0)
                self._write_to_file(data_to_log)

    def log_data(self, data):
        """Add data to the queue and trigger logging."""
        self.data_queue.append(data)

    def stop(self):
        """Safely stop the thread."""
        self.running = False
        self.wait()

    def _write_to_file(self, data):
        """Write data to the file."""
        try:
            with open(self.filename, 'a') as file:
                file.write(','.join(map(str, data)) + '\n')
        except Exception as e:
            print(f"Error logging data: {e}")
