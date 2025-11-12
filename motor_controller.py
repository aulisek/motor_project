from nanolib_helper import Nanolib, NanolibHelper
import time
import threading

class MotorController:
    def __init__(self):
        self.nanolib_helper = NanolibHelper()
        self._stop_event = threading.Event()
        self.initialized = False
        #setup nanolib
        self.nanolib_helper.setup()
        self.nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)

    def select_bus_hardware(self):
        """Retrieve and select bus hardware."""
        bus_hardware = self.get_bus_hardware()
        hardware_items = [
            f"{i}. {hw.getName()} (Protocol: {hw.getProtocol()})"
            for i, hw in enumerate(bus_hardware)
        ]
        return bus_hardware, hardware_items
    
    def initialize_motor(self, hardware_index):
        """Complete initialization sequence."""
       
        # Retrieve and select bus hardware
        bus_hardware = self.get_bus_hardware()
        '''
        bus_hw_id = bus_hardware[3]
        self.open_bus_hardware(bus_hw_id)
        device_handle = self.create_and_connect_device(bus_hw_id)
        self.stop_running_program(device_handle)
        '''
        if hardware_index < 0 or hardware_index >= len(bus_hardware):
            raise ValueError("Invalid hardware index.")
        
        self.selected_hardware = bus_hardware[hardware_index]
        self.open_bus_hardware(self.selected_hardware)
        device_handle = self.create_and_connect_device(self.selected_hardware)
        self.stop_running_program(device_handle)

        self.device_handle = device_handle
        self.initialized = True
        # baud rate setting
        self.nanolib_helper.write_number(self.device_handle, 256000, Nanolib.OdIndex(0x202A, 0x00), 32)
        #self.nanolib_helper.write_number(self.device_handle, 0, Nanolib.OdIndex(0x3502, 0x00), 32)
        #self.nanolib_helper.write_number(self.device_handle, 60640020, Nanolib.OdIndex(0x3502, 0x03), 32)
        

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
        # counter clockwise
          

    def move_to_position(self, position):
        """Start the movement and waiting until the movement is done."""
        self.nanolib_helper.write_number(self.device_handle, position, Nanolib.OdIndex(0x607A, 0x00), 32)
        self.nanolib_helper.write_number(self.device_handle, 0xBF, Nanolib.OdIndex(0x6040, 0x00), 16)
        while True:
            if self._stop_event.is_set():
                self.stop_motor()
                return False
            status_word = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6041, 0x00))
            #torque_value = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6077, 0x00))
            #position_value = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6064, 0x00))
            #print(position_value, torque_value)

            if status_word & 0x1400 == 0x1400:
                break
        self.nanolib_helper.write_number(self.device_handle,-0x11, Nanolib.OdIndex(0x6040, 0x00), 16)
        return True

    def get_position(self):
        """Get position of the motor"""
        position_value = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x6064, 0x00))
        #position_value = 10
        return position_value /10

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
    
    def set_home_position(self):
        """Set the current position as the home position without moving the motor."""
        # 1. Uložení aktuálního režimu řízení
        self.nanolib_helper.write_number(self.device_handle, 6, Nanolib.OdIndex(0x6060, 0x00), 8)
        
        # 3. Získání aktuální pozice
        current_position = self.get_position()*10
        print(f"Current Position before homing: {current_position}")

        # 4. Výpočet a zápis offsetu
        desired_home_position = 3600  # Chceme, aby aktuální pozice odpovídala 3600
        home_offset = 3600
        self.nanolib_helper.write_number(self.device_handle, home_offset, Nanolib.OdIndex(0x607C, 0x00), 32)
        print(f"Home offset set to: {home_offset}")
        self.nanolib_helper.write_number(self.device_handle, 0b10000, Nanolib.OdIndex(0x6040, 0x00), 16)
        # 5. Ověření zápisu offsetu
        read_offset = self.nanolib_helper.read_number(self.device_handle, Nanolib.OdIndex(0x607C, 0x00))
        print(f"Verified home offset: {read_offset}")
        self.nanolib_helper.write_number(self.device_handle, 15, Nanolib.OdIndex(0x6040, 0x00), 16)  # Enable operation
        # 6. Přepnutí zpět do původního režimu řízení
        #self.nanolib_helper.write_number(self.device_handle, current_mode, Nanolib.OdIndex(0x6060, 0x00), 8)

        self.enable_voltage()
        self.switch_on()
        self.enable_operation()
        self.set_profile_position_mode()
        # 7. Ověření nové polohy – měla by odpovídat 3600
        new_position = self.get_position()
        print(f"New Actual Position after setting home: {new_position}")

        self.stop_motor()

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
        return self.initialized
