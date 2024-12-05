# -*- coding: utf-8 -*-

# Author: Fabian Schober, Nanotec

from nanolib_helper import Nanolib, NanolibHelper
# from Nanolib import NanoLibAccessor
import time
import ctypes
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QWidget, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("GUI")
        self.setGeometry(100, 100, 400, 200)

        # Create widgets
        self.velocity = QSlider(Qt.Horizontal)
        self.velocity.setRange(1, 100)
        self.velocity.setValue(50)

        self.position = QSlider(Qt.Horizontal)
        self.position.setRange(0, 360)
        self.position.setValue(50)

        self.spinbox = QSpinBox()
        self.spinbox.setRange(0, 1000)
        self.spinbox.setValue(10)

        self.button = QPushButton("Start motion")
        self.status_label = QLabel("Set values and press Start.")

        # Set layouts
        main_layout = QVBoxLayout()
        slider_layout = QHBoxLayout()

        slider_layout.addWidget(QLabel("Velocity (rotations/min):"))
        slider_layout.addWidget(self.velocity)
        slider_layout.addWidget(QLabel("Desired angle (0-3600):"))
        slider_layout.addWidget(self.position)

        main_layout.addLayout(slider_layout)
        main_layout.addWidget(QLabel("Number of repetitions:"))
        main_layout.addWidget(self.spinbox)
        main_layout.addWidget(self.button)
        main_layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Connect button click to handler
        self.button.clicked.connect(self.start_process)

    def start_process(self):
        # Get current values from sliders and spinbox
        prof_velocity = self.velocity.value()
        target_position1 = self.position.value()*10
        repete = self.spinbox.value()

        # Disable all inputs
        self.velocity.setEnabled(False)
        self.position.setEnabled(False)
        self.spinbox.setEnabled(False)
        self.button.setEnabled(False)

        # Notify user
        self.status_label.setText("Processing... Please wait.")

        # Simulate a loop waiting for movement (replace with actual logic)
        QTimer.singleShot(100, lambda: self.motion(prof_velocity,target_position1,repete))
        

    def motion(self, prof_velocity,target_position1,repete):
            # Nastavení maximálního zrychlení (0x60C5) 
        nanolib_helper.write_number(device_handle, max_acceleration, Nanolib.OdIndex(0x6083, 0x00), 32)  # 0x6083 - Maximum Acceleration

        # Nastavení profile zrychlení (0x6083)
        nanolib_helper.write_number(device_handle, prof_acceleration, Nanolib.OdIndex(0x6083, 0x00), 32)  # 0x6083 - Maximum Acceleration

        # Nastavení maximálního brzdného zrychlení (0x60C6)
        nanolib_helper.write_number(device_handle, max_deceleration, Nanolib.OdIndex(0x6084, 0x00), 32)  # 0x6084 - Maximum Deceleration

        # Nastavení profile brzdného zrychlení (0x6084)
        nanolib_helper.write_number(device_handle, prof_deceleration, Nanolib.OdIndex(0x6084, 0x00), 32)  # 0x6084 - Maximum Deceleration

        # Nastavení profile rychlosti (0x6081) 
        nanolib_helper.write_number(device_handle, prof_velocity, Nanolib.OdIndex(0x6082, 0x00), 32)  # 0x6082 - Maximum Velocity

        # Nastavení koncove rychlosti (0x6082)
        nanolib_helper.write_number(device_handle, end_velocity, Nanolib.OdIndex(0x6082, 0x00), 32)  # 0x6082 - Maximum Velocity
        
        # Nastavení profilu pohybu s použitím zrychlení a brzdného zrychlení, nastaveni pozice
        nanolib_helper.write_number(device_handle, home_position, Nanolib.OdIndex(0x607A, 0x00), 32)  # 0x607A - Target Position


        # switch the state machine to "enable operation state"
        status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
        while ( (nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00)) & 0xEF) != 0x27):
            print("cekame")
            time.sleep(1)
        
        # destination reached if status_word & (1 << 10):
        
        for i in range(repete):
            # move the motor to the desired target psoition absolutely
            status_word = nanolib_helper.write_number(device_handle, 0xBF, Nanolib.OdIndex(0x6040, 0x00), 16)
            
            while(True):
                status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
                #print(bin(status_word))
                # print("p:",nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6063, 0x00)))
                #print("v:",nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x606C, 0x00)))
                if ((status_word &  0x1400) ==  0x1400):
                    break
        
            nanolib_helper.write_number(device_handle, target_position1, Nanolib.OdIndex(0x607A, 0x00), 32)  # 0x607A - Target Position

            
            change = 0xBF
            change = ~(1 << 4)
            # move the motor to the desired target psoition absolutely
            status_word = nanolib_helper.write_number(device_handle,change, Nanolib.OdIndex(0x6040, 0x00), 16)
            status_word = nanolib_helper.write_number(device_handle,0xBF, Nanolib.OdIndex(0x6040, 0x00), 16)
            while(True):
                status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
                #print(bin(status_word))
                print("position:",nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6063, 0x00)))
                #print("velocity:",nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x606C, 0x00)))
                if ((status_word &  0x1400) ==  0x1400):
                    break

            nanolib_helper.write_number(device_handle, target_position2, Nanolib.OdIndex(0x607A, 0x00), 32)  # 0x607A - Target Position

            change = 0xBF
            change = ~(1 << 4)
            # move the motor to the desired target psoition absolutely
            status_word = nanolib_helper.write_number(device_handle,change, Nanolib.OdIndex(0x6040, 0x00), 16)
            status_word = nanolib_helper.write_number(device_handle,0xBF, Nanolib.OdIndex(0x6040, 0x00), 16)

            while(True):
                status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
                #print(bin(status_word))
                #print("position:",nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6063, 0x00)))
                #print("velocity:",nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x606C, 0x00)))
                if ((status_word &  0x1400) ==  0x1400):
                    break
            i = i-1

        # stop the motor
        status_word = nanolib_helper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)


        # Enable all inputs
        self.velocity.setEnabled(True)
        self.position.setEnabled(True)
        self.spinbox.setEnabled(True)
        self.button.setEnabled(True)

        # Notify user
        self.status_label.setText("                     ")

def object_dictionary_access_examples(nanolib_helper, device_handle):
    print('\nOD Example\n')

    print('Motor Stop (0x6040-0)')
    status_word = nanolib_helper.write_number(device_handle, -200, Nanolib.OdIndex(0x60FF, 0x00), 32)
    
    print("Reading subindex 0 of index 0x6040")
    status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x60FF, 0x00))
    print('Result: {}\n'.format(status_word))

    print('\nRead Nanotec home page string')
    home_page = nanolib_helper.read_string(device_handle, Nanolib.OdIndex(0x6505, 0x00))
    print('The home page of Nanotec Electronic GmbH & Co. KG is: {}'.format(home_page))

    print('\nRead device error stack')
    error_stack = nanolib_helper.read_array(device_handle, Nanolib.OdIndex(0x1003, 0x00))
    print('The error stack has {} elements\n'.format(error_stack[0]))

def setup_nanolib():
    """Initialize nanolib and set logging level."""
    nanolib_helper.setup()
    nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)

def get_bus_hardware():
    """Retrieve and select bus hardware."""
    bus_hardware_ids = nanolib_helper.get_bus_hardware()
    if not bus_hardware_ids:
        raise Exception('No bus hardware found.')

    print('\nAvailable bus hardware:\n')
    for i, bus_hardware_id in enumerate(bus_hardware_ids):
        print(f"{i}. {bus_hardware_id.getName()} with protocol: {bus_hardware_id.getProtocol()}")

    # Hardcoded line number
    line_num = 2
    print(f'\nDevice line was set to {line_num} in the code.')

    if line_num < 0 or line_num >= len(bus_hardware_ids):
        raise Exception('Invalid selection!')

    return bus_hardware_ids[line_num]

def open_bus_hardware(bus_hw_id):
    """Open the selected bus hardware."""
    bus_hw_options = nanolib_helper.create_bus_hardware_options(bus_hw_id)
    nanolib_helper.open_bus_hardware(bus_hw_id, bus_hw_options)

def create_and_connect_device(bus_hw_id):
    """Create and connect to the device."""
    device_id = Nanolib.DeviceId(bus_hw_id, 5, "")
    device_handle = nanolib_helper.create_device(device_id)
    nanolib_helper.connect_device(device_handle)
    return device_handle

def stop_nanoj_program(device_handle):
    """Stop any running NanoJ program."""
    nanolib_helper.write_number(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)

def initialize_system():
    """Complete initialization sequence."""
    setup_nanolib()
    bus_hw_id = get_bus_hardware()
    open_bus_hardware(bus_hw_id)
    device_handle = create_and_connect_device(bus_hw_id)
    stop_nanoj_program(device_handle)
    return device_handle

def enable_voltage(device_handle):
    """Switch the state machine to 'enable voltage'."""
    nanolib_helper.write_number(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)

def switch_on(device_handle):
    """Switch the state machine to 'switch on'."""
    nanolib_helper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)

def enable_operation(device_handle):
    """Switch the state machine to 'enable operation'."""
    nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)

def set_profile_position_mode(device_handle):
    """Set the controller to Profile Position mode."""
    nanolib_helper.write_number(device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)

def close_connection(device_handle, bus_hw_id):
    """Close the connection with motor"""
    nanolib_helper.disconnect_device(device_handle)
    nanolib_helper.close_bus_hardware(bus_hw_id)

if __name__ == '__main__':
    nanolib_helper = NanolibHelper()
    device_handle = initialize_system()
    print("System initialized successfully. Ready for further operations.")
    
    # Nastaveni parametru od uzivatele
    max_acceleration = 40 
    prof_acceleration = 40  
    max_deceleration = 40 
    prof_deceleration = 40 
    #prof_velocity = 100
    end_velocity = 0 
    home_position = 0  # Pocatecni pozice
    #target_position1 = 3600  # Cílová pozice 1
    target_position2 = 0  # Cílová pozice 2 
    #repete = 2 # number of repetition

    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
    
    enable_voltage(device_handle)
    switch_on(device_handle)
    enable_operation(device_handle)
    switch_on(device_handle)  # Repeat if required
    set_profile_position_mode(device_handle)


    
