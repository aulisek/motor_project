import pyqtgraph as pg
from pyqtgraph import PlotWidget
import nidaqmx
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from nidaqmx.constants import AcquisitionType
import random
import time
import serial



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
    data_signal = pyqtSignal(float, float, float,float,float)  # timestamp, position, resistance

    def __init__(self, device_name, ai_channel, sample_rate, motor_controller):
        super().__init__()
        self.motor_controller = motor_controller
        self.device_name = "Dev2"
        self.ai_channel = "ai4"
        self.sample_rate = 5  # Hz
        self.running = False
        self.ser = serial.Serial('COM6', 9600, timeout=0.05)

    def run(self):
        """DAQ On-Demand Sampling with Precise Timing (Compensates for Processing Time)"""
        self.running = True
        #sample_interval = 1.0 / self.sample_rate  # Time between samples (seconds)
        sample_interval = 0.1
        next_sample_time = time.perf_counter()  # High-precision timer

        with nidaqmx.Task() as ai_task, open("measurement.csv", "a") as f:
            try:
                # Configure AI voltage channel (On-Demand mode)
                ai_task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.ai_channel}",
                    min_val=0, max_val=5,
                    terminal_config=nidaqmx.constants.TerminalConfiguration.RSE
                )

                while self.running:
                    start_time = time.perf_counter()  # Measure execution start time
                    line = self.ser.readline().decode().strip()
                    if line:
                        try:
                            temperature, humidity = map(float, line.split(","))
                            #print(f"Teplota: {temperature} °C, Vlhkost: {humidity} %") 
                        except ValueError:
                            #print("Connect sensor")
                            temperature, humidity = 999, 999

                    # Read data
                    timestamp = time.time()
                    voltage = ai_task.read()  # Immediate (On-Demand) read
                    position = self.motor_controller.get_position()  # Get motor position
                    #resistance = (10000 * (5 - voltage) / voltage)
                    resistor_value = 540000
                    resistance = (resistor_value * voltage)/(5-voltage)
                    #resistance = voltage

                    # Emit data to update GUI and save
                    self.data_signal.emit(timestamp, position, resistance, temperature, humidity)
                    
                    # Save data to file (appending without reopening)
                    f.write(f"{timestamp},{position},{resistance},{temperature},{humidity}\n")
                    f.flush()  # Ensures data is written immediately to prevent data loss

                    # Calculate elapsed time and adjust sleep accordingly
                    elapsed_time = time.perf_counter() - start_time
                    next_sample_time += sample_interval
                    sleep_time = max(0, next_sample_time - time.perf_counter() - elapsed_time)
                    #print(sleep_time)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    

            except nidaqmx.errors.DaqError as e:
                print(f"DAQ Error: {e}")

    def stop(self):
        """Stop DAQ acquisition"""
        self.running = False
        self.wait()  # Ensure the thread stops cleanly
'''
    def run(self):
        self.running = True
        with nidaqmx.Task() as ai_task, nidaqmx.Task() as clock_task:
            try:
                # Configure AI voltage channel
                ai_task.ai_channels.add_ai_voltage_chan(
                    f"{self.device_name}/{self.ai_channel}",
                    min_val=0, max_val=5,
                    terminal_config=nidaqmx.constants.TerminalConfiguration.RSE
                )
                
                # Configure Counter Output to generate pulse train for AI clock
                clock_task.co_channels.add_co_pulse_chan_freq(
                    counter=f"{self.device_name}/ctr0",  
                    units=nidaqmx.constants.FrequencyUnits.HZ,
                    freq=self.sample_rate,
                    duty_cycle=0.5
                )
                clock_task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.CONTINUOUS)

                # Set AI sampling clock source to counter output (ctr0)
                ai_task.timing.cfg_samp_clk_timing(
                    self.sample_rate,
                    sample_mode=AcquisitionType.CONTINUOUS,
                    samps_per_chan=1,
                    source=f"/{self.device_name}/Ctr0InternalOutput",  # Correct NI-DAQ clock source
                    active_edge=Edge.RISING
                )

                # Start tasks
                clock_task.start()
                ai_task.start()
                
                # Use an external sample clock for precise timing
                ai_task.timing.cfg_samp_clk_timing(
                #self.sample_rate,  
                50,
                sample_mode=AcquisitionType.CONTINUOUS, 
                samps_per_chan=5
                )

                #ai_task.start()

                while self.running:
                    #ai_task.wait_until_done(timeout=1.0 / self.sample_rate) 

                    timestamp = time.time()
                    voltage = ai_task.read()  # Blocking call, waits for new sample
                    position = self.motor_controller.get_position()  # Get motor position
                    resistance = (10000*(5-voltage)/voltage)
                    # Emit the data for GUI update
                    self.data_signal.emit(timestamp, position, resistance)
                    #QThread.msleep(int((1/self.sample_rate)*1000))
                    #QThread.msleep(200)

            except nidaqmx.errors.DaqError as e:
                print(f"DAQ Error: {e}")

            finally:
                #clock_task.stop()
                ai_task.stop()
    def stop(self):
        self.running = False
        self.quit()  # Gracefully exit the thread
        self.wait()  # Wait for the thread to finish

    def change_sample_rate(self, new_sample_rate):
        self.sample_rate = new_sample_rate
        '''
    