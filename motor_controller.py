from nanolib_helper import Nanolib, NanolibHelper
import threading
import queue

class MotorController:
    def __init__(self):
        self.nanolib_helper = NanolibHelper()
        self.device_handle = self.initialize_motor()
        self.position_queue = queue.Queue()  # Thread-safe queue for position data

    def setup_nanolib(self):
        """Initialize nanolib and set logging level."""
        self.nanolib_helper.setup()
        self.nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)

    def initialize_motor(self):
        """Complete initialization sequence."""
        # Initialize nanolib and set logging level
        self.setup_nanolib()
       
        # Retrieve and select bus hardware
        bus_hardware = self.get_bus_hardware()
        bus_hw_id = bus_hardware[2]
        self.open_bus_hardware(bus_hw_id)
        device_handle = self.create_and_connect_device(bus_hw_id)
        self.stop_running_program(device_handle)
        return device_handle

    def get_bus_hardware(self):
        """Retrieve and select bus hardware."""
        bus_hardware = self.nanolib_helper.get_bus_hardware()
        if not bus_hardware:
            raise Exception("No bus hardware found.")
        return bus_hardware

    def open_bus_hardware(self, bus_hw_id):
        """Open the selected bus hardware."""
        options = self.nanolib_helper.create_bus_hardware_options(bus_hw_id)
        self.nanolib_helper.open_bus_hardware(bus_hw_id, options)

    def create_and_connect_device(self, bus_hw_id):
        """Create and connect to the device."""
        device_id = Nanolib.DeviceId(bus_hw_id, 5, "")
        device_handle = self.nanolib_helper.create_device(device_id)
        self.nanolib_helper.connect_device(device_handle)
        return device_handle

    def stop_running_program(self, device_handle):
        """Stop any running NanoJ program."""
        self.nanolib_helper.write_number(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)

    def execute_motion(self, home_position, target_position1, target_position2, repetitions):
        self.enable_voltage()
        self.switch_on()
        self.enable_operation()
        self.set_profile_position_mode()
        self.move_to_position(home_position)
        for _ in range(repetitions):
            # Starting position
            self.move_to_position(target_position1)
            # Ending position
            self.move_to_position(target_position2)
        self.stop_motor()
        return 1

    def set_motion_parameters(self, max_acceleration, prof_acceleration, max_deceleration, prof_deceleration,
                               prof_velocity, end_velocity):
        # Maximum accelaration (0x60C5) 
        self.nanolib_helper.write_number(self.device_handle, max_acceleration, Nanolib.OdIndex(0x60C5, 0x00), 32) 

        # Profile accelaration (0x6083)
        self.nanolib_helper.write_number(self.device_handle, prof_acceleration, Nanolib.OdIndex(0x6083, 0x00), 32)  

        # Max Deccelaration (0x60C6)
        self.nanolib_helper.write_number(self.device_handle, max_deceleration, Nanolib.OdIndex(0x60C6, 0x00), 32)  

        # Profile Deccelaration (0x6084)
        self.nanolib_helper.write_number(self.device_handle, prof_deceleration, Nanolib.OdIndex(0x6084, 0x00), 32)  

        # 0x6081 - Profile Velocity
        self.nanolib_helper.write_number(self.device_handle, prof_velocity, Nanolib.OdIndex(0x6081, 0x00), 32)  

        # 0x6082 - Maximum end Velocity
        self.nanolib_helper.write_number(self.device_handle, end_velocity, Nanolib.OdIndex(0x6082, 0x00), 32)  
        

    def move_to_position(self, position):
        """Start the movement and waiting until the movement is done."""
        self.nanolib_helper.write_number(self.device_handle, position, Nanolib.OdIndex(0x607A, 0x00), 32)
        self.nanolib_helper.write_number(self.device_handle, 0xBF, Nanolib.OdIndex(0x6040, 0x00), 16)
        while True:
            status_word = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6041, 0x00))
            position_value = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6064, 0x00))
            print(position_value)
            #threading.Thread(target=callback, args=(position_value, self.position_queue)).start()
            if status_word & 0x1400 == 0x1400:
                break
        self.nanolib_helper.write_number(self.device_handle,-0x11, Nanolib.OdIndex(0x6040, 0x00), 16)

    def get_position(self):
        """Get position of the motor"""
        position_value = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6064, 0x00))
        return position_value / 10

    def collect_position_data(self, position, data_queue):
        """Callback function to collect position data in queue."""
        data_queue.put(position)  # Add the position value to the queue

    def stop_motor(self):
        """Stop the movement."""
        self.nanolib_helper.write_number(self.device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)

    def enable_voltage(self):
        """Switch the state machine to 'enable voltage'."""
        self.nanolib_helper.write_number(self.device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)

    def switch_on(self):
        """Switch the state machine to 'switch on'."""
        self.nanolib_helper.write_number(self.device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)

    def enable_operation(self):
        """Switch the state machine to 'enable operation'."""
        self.nanolib_helper.write_number(self.device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)

    def set_profile_position_mode(self):
        """Set the controller to Profile Position mode."""
        self.nanolib_helper.write_number(self.device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)

    def close_connection(self, bus_hw_id):
        """Stop the movement."""
        self.nanolib_helper.disconnect_device(self.device_handle)
        self.nanolib_helper.close_bus_hardware(bus_hw_id)