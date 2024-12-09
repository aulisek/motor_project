import pyqtgraph as pg
from pyqtgraph import PlotWidget
import nidaqmx


class NIDevice:
    def get_measurement(self):
        # Dummy function to simulate electrode data collection
        #import random
        #return random.uniform(0, 10)  # Example value
        #Create a task object
        with nidaqmx.Task() as task:
            #Add an analog input channel (A0) to the task
            #Replace "Dev1" with your device name
            task.ai_channels.add_ai_voltage_chan("Dev1/ai0")  
            
        #Read the value from the A0 channel
            value = task.read()
        return value