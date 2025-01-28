import pyqtgraph as pg
from pyqtgraph import PlotWidget
import nidaqmx
from PyQt5.QtCore import QThread, pyqtSignal
from nidaqmx.constants import AcquisitionType




class NIDevice:
    def get_measurement(self):
        # Dummy function to simulate electrode data collection
        # import random
        # return random.uniform(0, 10)  # Example value
        #Create a task object
        with nidaqmx.Task() as task:
            #Add an analog input channel (A0) to the task
            #Replace "Dev1" with your device name
            task.ai_channels.add_ai_voltage_chan("Dev1/ai1")  
            
        #Read the value from the A0 channel
            voltage = task.read()
            resistance = (10000*(5-voltage)/voltage)
        return resistance

class DAQController(QThread):
    data_signal = pyqtSignal(list)  # Emit processed data as a list for GUI plotting

    def __init__(self, device_name="Dev1", channel="ai1", sample_rate=1000, buffer_size=100):
        super().__init__()
        self.device_name = device_name
        self.channel = channel
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.running = False

    def run(self):
        self.running = True
        with nidaqmx.Task() as task:
            # Configure the analog input channel and task
            task.ai_channels.add_ai_voltage_chan(f"{self.device_name}/{self.channel}")
            task.timing.cfg_samp_clk_timing(self.sample_rate, sample_mode=AcquisitionType.CONTINUOUS)

            # Continuously read data while the thread is running
            while self.running:
                try:
                    # Read raw voltage data from the device
                    voltage_data = task.read(number_of_samples_per_channel=self.buffer_size)

                    # Convert voltage to resistance using Ohm's law
                    resistance_data = [
                        (10000 * (5 - voltage) / voltage) if voltage > 0 else float('inf')
                        for voltage in voltage_data
                    ]

                    # Emit the processed resistance data
                    self.data_signal.emit(resistance_data)
                except nidaqmx.errors.DaqError as e:
                    print(f"DAQ Error: {e}")
                    break

    def stop(self):
        """Safely stop the thread."""
        self.running = False
        self.wait()