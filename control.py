# -*- coding: utf-8 -*-

###########################################################################################################
# This Example Code is based on our experience with typical user requirements in a wide range
# of industrial applications and is provided without guarantee regarding correctness and completeness.
# It serves as general guidance and should not be construed as a commitment of Nanotec to guarantee its
# applicability to the customer application without additional tests under the specific conditions
# and – if and when necessary – modifications by the customer. 

# The responsibility for the applicability and use of the Example Code in a particular
# customer application lies solely within the authority of the customer.
# It is the customer's responsibility to evaluate, investigate and decide,
# whether the Example Code is valid and suitable for the respective customer application, or not.
# Defects resulting from the improper handling of devices and modules are excluded from the warranty.
# Under no circumstances will Nanotec be liable for any direct, indirect, incidental or consequential damages
# arising in connection with the Example Code provided. In addition, the regulations regarding the
# liability from our Terms and Conditions of Sale and Delivery shall apply.
############################################################################################################

# Author: Fabian Schober, Nanotec

from nanolib_helper import Nanolib, NanolibHelper
# from Nanolib import NanoLibAccessor
import time
import ctypes

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


if __name__ == '__main__':
    nanolib_helper = NanolibHelper()

    # create access to the nanolib
    nanolib_helper.setup()
    
    print('Nanolib Example')

    # its possible to set the logging level to a different level
    nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)

    # list all hardware available, decide for the first one
    bus_hardware_ids = nanolib_helper.get_bus_hardware()

    if bus_hardware_ids.empty():
        raise Exception('No bus hardware found.')
        
    print('\nAvailable bus hardware:\n')

    line_num = 0
    # just for better overview: print out available hardware
    for bus_hardware_id in bus_hardware_ids:
        print('{}. {} with protocol: {}'.format(line_num, bus_hardware_id.getName(), bus_hardware_id.getProtocol()))
        line_num += 1

    print('\nPlease select (type) bus hardware number and press [ENTER]:', end ='');
    
    line_num = int(input())
    
    print('');
    
    if ((line_num < 0) or (line_num >= bus_hardware_ids.size())):
        raise Exception('Invalid selection!')
        
    # Use the selected bus hardware
    bus_hw_id = bus_hardware_ids[line_num]
    print(bus_hw_id)

    # create bus hardware options for opening the hardware
    bus_hw_options = nanolib_helper.create_bus_hardware_options(bus_hw_id)

    # now able to open the hardware itself
    nanolib_helper.open_bus_hardware(bus_hw_id, bus_hw_options)

    nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)
    
    # either scan the whole bus for devices (in case the bus supports scanning)
    device_ids = nanolib_helper.scan_bus(bus_hw_id)
    
    nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)
    
    print("")
    for device_id in device_ids:
        print("Found Device: {}".format(device_id.toString()))
        
    if (device_ids.size() == 0):
        raise Exception('No devices found.')

    print('\nAvailable devices:\n')

    line_num = 0
    # just for better overview: print out available hardware
    for id in device_ids:
        print('{}. {} [device id: {}, hardware: {}]'.format(line_num, id.getDescription(), id.getDeviceId(), id.getBusHardwareId().getName()))
        line_num += 1

    print('\nPlease select (enter) device number(0-{}) and press [ENTER]:'.format(line_num - 1), end ='');
    
    line_num = int(input())
    
    print('');
    
    if ((line_num < 0) or (line_num >= device_ids.size())):
        raise Exception('Invalid selection!')

    # We can create the device id manually    
    # device_id = Nanolib.DeviceId(bus_hw_id, 1, "")
    # or select first found device on the bus
    device_id = device_ids[line_num]
    
    device_handle = nanolib_helper.create_device(device_id)

    # now connect to the device
    nanolib_helper.connect_device(device_handle)

    # now ready to work with the controller, here are some examples on how to access the
    # object dictionary:
    object_dictionary_access_examples(nanolib_helper, device_handle)
    
    
    ### example code to let the motor run in Profile Velocity mode
    
    # stop a possibly running NanoJ program
    nanoj_control = nanolib_helper.write_number(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)
    
    # choose Profile Velocity mode
    mode_of_operation = nanolib_helper.write_number(device_handle, 3, Nanolib.OdIndex(0x6060, 0x00), 8)
    
    # set the desired speed in rpm
    speed = ctypes.c_int64(int(input("Insert the velocity in RPM:")))
    time_run = int(input("Insert desired time of rotating in seconds:"))
    target_velocity = nanolib_helper.write_number(device_handle, speed.value, Nanolib.OdIndex(0x60FF, 0x00), 32)
    
    # switch the state machine to "operation enabled"
    status_word = nanolib_helper.write_number(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
    status_word = nanolib_helper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
    status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # let the motor run for desired time
    time.sleep(time_run)
        
    # stop the motor
    status_word = nanolib_helper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # set the desired speed in rpm, now counterclockwise
    target_velocity = nanolib_helper.write_number(device_handle, -100, Nanolib.OdIndex(0x60FF, 0x00), 32)
    
    # start the motor    
    status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # let the motor run for 3s
    time.sleep(3)
    
    # stop the motor
    status_word = nanolib_helper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)

    # cleanup and close everything
    nanolib_helper.disconnect_device(device_handle)
    nanolib_helper.close_bus_hardware(bus_hw_id)

    print("Closed everything successfully")
