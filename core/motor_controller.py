from core.nanolib_helper import Nanolib, NanolibHelper
import threading
import logging
import core.constants as const

logger = logging.getLogger(__name__)

class MotorController:
    """
    Controller class for handling interactions with the Nanotec motor.
    Wraps the Nanolib wrapper functions to execute specific motor commands
    like initialization, movement, setting home position, and retrieving position.
    """

    def __init__(self):
        self.nanolib_helper = NanolibHelper()
        self._stop_event = threading.Event()
        self.initialized = False
        
        # The physical absolute encoder position that represents 0 degrees
        self.current_absolute_home = const.ABSOLUTE_ENCODER_HOME
        self._needs_auto_home = False  # Disables auto-calibration at startup since we know the absolute position
        # Setup nanolib
        self.nanolib_helper.setup()
        self.nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)

    def set_current_position_as_home(self):
        """Sets the current physical position as the absolute default home (0 degrees)."""
        if not self.initialized:
            raise Exception("Motor is not initialized.")
        try:
            actual_pos = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6064, 0x00))
            self.current_absolute_home = actual_pos
            logger.info(f"New home set. Absolute home in memory: {self.current_absolute_home}")
        except Exception as e:
            logger.error(f"Failed to set current position as home: {e}")
            raise

    def select_bus_hardware(self):
        """Retrieve and select bus hardware."""
        bus_hardware = self.get_bus_hardware()
        hardware_items = [
            f"{i}. {hw.getName()} (Protocol: {hw.getProtocol()})"
            for i, hw in enumerate(bus_hardware)
        ]
        return bus_hardware, hardware_items
    
    def initialize_motor(self, hardware_index):
        """
        Complete initialization sequence.
        
        Args:
            hardware_index (int): Index of the selected bus hardware.
            
        Raises:
            ValueError: If the hardware index is out of range.
        """
       
        # Retrieve and select bus hardware
        bus_hardware = self.get_bus_hardware()
        if hardware_index < 0 or hardware_index >= len(bus_hardware):
            raise ValueError("Invalid hardware index.")
        
        self.selected_hardware = bus_hardware[hardware_index]
        self.open_bus_hardware(self.selected_hardware)
        device_handle = self.create_and_connect_device(self.selected_hardware)
        self.stop_running_program(device_handle)

        self.device_handle = device_handle
        self.initialized = True
        # Baud rate setting
        self.nanolib_helper.write_number(self.device_handle, 256000, Nanolib.OdIndex(0x202A, 0x00), 32)
        
        # If the application starts for the first time (no offset), it calibrates automatically
        if self._needs_auto_home:
            logger.info("No saved offset found. Auto-calibrating current position as Home (0°).")
            try:
                self.set_current_position_as_home()
            except Exception as e:
                logger.error(f"Failed to auto-calibrate home position: {e}")
        

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

    def execute_motion(self, home_position, positions, delays, repetitions, progress_callback=None):
        """
        Executes a sequence of motion commands.
        
        Args:
            home_position: Home position setting.
            positions (list): A list of target positions.
            delays (list): Delays in ms to apply after each corresponding position movement.
            repetitions (int): Number of times the sequence is repeated.
            progress_callback (callable, optional): Callback to update progress.
            
        Returns:
            int: 0 if aborted, 1 if completed successfully.
        """
        self._stop_event.clear()
        self.enable_voltage()
        self.switch_on()
        self.enable_operation()
        self.set_profile_position_mode()
        self.move_to_position(home_position)
        self.nanolib_helper.write_number(self.device_handle, 0, Nanolib.OdIndex(0x6068, 0x00), 16)

        aborted = False

        for cycle_idx in range(repetitions):
            if self._stop_event.is_set():
                aborted = True
                break

            for i, position in enumerate(positions):
                if self._stop_event.is_set():
                    aborted = True
                    break

                if not self.move_to_position(position):
                    aborted = True
                    break

                delay = delays[i] if i < len(delays) else 0
                if delay > 0 and self._stop_event.wait(delay / 1000):
                    aborted = True
                    break

            if aborted:
                break
            if progress_callback is not None:
                try:
                    progress_callback(cycle_idx + 1)
                except Exception:
                    pass

        self.stop_motor()
        return 0 if aborted else 1

    def set_motion_parameters(self, max_acceleration, prof_acceleration, max_deceleration, prof_deceleration,
                               prof_velocity, end_velocity):
        """Set motor kinematic parameters (acceleration, velocity, etc.)."""
        # Maximum acceleration (0x60C5) 
        self.nanolib_helper.write_number(self.device_handle, max_acceleration, Nanolib.OdIndex(0x60C5, 0x00), 32) 

        # Profile acceleration (0x6083)
        self.nanolib_helper.write_number(self.device_handle, prof_acceleration, Nanolib.OdIndex(0x6083, 0x00), 32)  

        # Max Deceleration (0x60C6)
        self.nanolib_helper.write_number(self.device_handle, max_deceleration, Nanolib.OdIndex(0x60C6, 0x00), 32)  

        # Profile Deceleration (0x6084)
        self.nanolib_helper.write_number(self.device_handle, prof_deceleration, Nanolib.OdIndex(0x6084, 0x00), 32)  

        # 0x6081 - Profile Velocity
        self.nanolib_helper.write_number(self.device_handle, prof_velocity, Nanolib.OdIndex(0x6081, 0x00), 32)  

        # 0x6082 - Maximum end Velocity
        self.nanolib_helper.write_number(self.device_handle, end_velocity, Nanolib.OdIndex(0x6082, 0x00), 32)  
        # Current limit (0x6073)
        self.nanolib_helper.write_number(self.device_handle, 50, Nanolib.OdIndex(0x6073, 0x00), 16) 
          
    def set_closed_loop(self, enable: bool):
        """Enable (True) or disable (False) closed loop control via Object 0x3202."""
        try:
            # 0x3202:00 Closed Loop Configuration. Bit 0: 1=Closed Loop, 0=Open Loop.
            value = 1 if enable else 0
            self.nanolib_helper.write_number(self.device_handle, value, Nanolib.OdIndex(0x3202, 0x00), 32)
        except Exception as e:
            logger.warning(f"Could not set closed loop mode: {e}")

    def move_to_position(self, position):
        """Start the movement and waiting until the movement is done."""
        # Map internal 'position' (counts, where 3600 = 0 deg) directly to absolute physical home
        target_position = int(position - const.DEFAULT_HOME_POSITION + self.current_absolute_home)
        self.nanolib_helper.write_number(self.device_handle, target_position, Nanolib.OdIndex(0x607A, 0x00), 32)
        self.nanolib_helper.write_number(self.device_handle, 0xBF, Nanolib.OdIndex(0x6040, 0x00), 16)
        while True:
            if self._stop_event.is_set():
                self.stop_motor()
                return False
            status_word = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6041, 0x00))

            if status_word & 0x1400 == 0x1400:
                break
        self.nanolib_helper.write_number(self.device_handle,-0x11, Nanolib.OdIndex(0x6040, 0x00), 16)
        return True

    def get_position(self):
        """Get position of the motor"""
        position_value = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6064, 0x00))
        # Calculate angle exactly from the absolute home anchor
        return (self.current_absolute_home - position_value) / 10.0

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
        """Close the connection to the bus hardware."""
        self.nanolib_helper.disconnect_device(self.device_handle)
        self.nanolib_helper.close_bus_hardware(bus_hw_id)
    
    def go_to_home_position(self):
        """Move the motor to the absolute default home position (without changing the reference)."""
        def _move_task():
            self._stop_event.clear()
            logger.info(f"Moving to absolute home position: {const.DEFAULT_HOME_POSITION}")
            self.enable_voltage()
            self.switch_on()
            self.enable_operation()
            self.set_profile_position_mode()
            
            self.move_to_position(const.DEFAULT_HOME_POSITION)
            self.stop_motor()
            
            new_position = self.get_position()
            logger.info(f"Motor reached home position. Actual: {new_position}")
            
        threading.Thread(target=_move_task, daemon=True).start()

    def stop_movement(self):
        """Stop the movement."""
        self._stop_event.set()
        self.nanolib_helper.write_number(self.device_handle, 2, Nanolib.OdIndex(0x2291, 0x04), 8)

    def set_position_window(self, position):
        """Specifies a range symmetrical to the target position within which that target is considered having been met"""
        self.nanolib_helper.write_number(self.device_handle, position, Nanolib.OdIndex(0x6067, 0x00), 32)
    
    def set_position_time(self, time_ms):
        """The current position must be within the "Position Window" (6067h) for this time in milliseconds for the target
position to be considered having been met"""
        self.nanolib_helper.write_number(self.device_handle, time_ms, Nanolib.OdIndex(0x6068, 0x00), 32)

    def is_initialized(self):
        """Check if the motor controller is initialized."""
        return self.initialized
