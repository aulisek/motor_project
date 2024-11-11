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

    # if bus_hardware_ids.empty():
        # raise Exception('No bus hardware found.')
        
    # print('\nAvailable bus hardware:\n')

    line_num = 0
    # just for better overview: print out available hardware
   # for bus_hardware_id in bus_hardware_ids:
        # print('{}. {} with protocol: {}'.format(line_num, bus_hardware_id.getName(), bus_hardware_id.getProtocol()))
        # line_num += 1

    # print('\nPlease select (type) bus hardware number and press [ENTER]:', end ='');
    
    # Manual hardcoded to avoid connecting the device every time
    line_num = 2
    
    print('Device line was set to 2 in the code');
    
    # if ((line_num < 0) or (line_num >= bus_hardware_ids.size())):
        # raise Exception('Invalid selection!')
        
    # Use the selected bus hardware
    bus_hw_id = bus_hardware_ids[line_num]
    print(bus_hw_id)

    # create bus hardware options for opening the hardware
    bus_hw_options = nanolib_helper.create_bus_hardware_options(bus_hw_id)

    # now able to open the hardware itself
    nanolib_helper.open_bus_hardware(bus_hw_id, bus_hw_options)

    nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)
    
    # either scan the whole bus for devices (in case the bus supports scanning)
    # device_ids = nanolib_helper.scan_bus(bus_hw_id)
    
    # nanolib_helper.set_logging_level(Nanolib.LogLevel_Off)
    
    # print("")
    # for device_id in device_ids:
        # print("Found Device: {}".format(device_id.toString()))
        
    # if (device_ids.size() == 0):
        # raise Exception('No devices found.')

    # print('\nAvailable devices:\n')

    line_num = 0
    # just for better overview: print out available hardware
    # for id in device_ids:
       # print('{}. {} [device id: {}, hardware: {}]'.format(line_num, id.getDescription(), id.getDeviceId(), id.getBusHardwareId().getName()))
       # line_num += 1

    # print('\nPlease select (enter) device number(0-{}) and press [ENTER]:'.format(line_num - 1), end ='');
    

    
    # print('');
    
    # if ((line_num < 0) or (line_num >= device_ids.size())):
       # raise Exception('Invalid selection!')

    # We can create the device id manually, to obtain the device ID run device_ids = nanolib_helper.scan_bus(bus_hw_id)
    device_id = Nanolib.DeviceId(bus_hw_id, 5, "")
    # or select first found device on the bus
    # device_id = device_ids[line_num]
    
    device_handle = nanolib_helper.create_device(device_id)

    # now connect to the device
    nanolib_helper.connect_device(device_handle)

    # now ready to work with the controller, here are some examples on how to access the
    # object dictionary:
    object_dictionary_access_examples(nanolib_helper, device_handle)
    
    
    # ### example code to let the motor run in Profile Velocity mode
    
    # # stop a possibly running NanoJ program
    # nanoj_control = nanolib_helper.write_number(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)
    
    # # choose Profile Velocity mode
    # mode_of_operation = nanolib_helper.write_number(device_handle, 3, Nanolib.OdIndex(0x6060, 0x00), 8)
    
    # # set the desired speed in rpm
    # speed = ctypes.c_int64(int(input("Insert the velocity in RPM:")))
    # time_run = int(input("Insert desired time of rotating in seconds:"))
    # target_velocity = nanolib_helper.write_number(device_handle, speed.value, Nanolib.OdIndex(0x60FF, 0x00), 32)
    
    # # switch the state machine to "operation enabled"
    # status_word = nanolib_helper.write_number(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
    # status_word = nanolib_helper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
    # status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # # let the motor run for desired time
    # time.sleep(time_run)
        
    # # stop the motor
    # status_word = nanolib_helper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # # set the desired speed in rpm, now counterclockwise
    # target_velocity = nanolib_helper.write_number(device_handle, -100, Nanolib.OdIndex(0x60FF, 0x00), 32)
    
    # # start the motor    
    # status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # # let the motor run for 3s
    # time.sleep(3)
    
    # # stop the motor
    # status_word = nanolib_helper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)

     ### example code to let the motor run in Profile Position mode
    
    # stop a possibly running NanoJ program
    nanoj_control = nanolib_helper.write_number(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)
    
    # # Homing Mode
    # nanolib_helper.write_number(device_handle, 35, Nanolib.OdIndex(0x6098, 0x00), 8)
    # nanolib_helper.write_number(device_handle, 720, Nanolib.OdIndex(0x608F, 0x01), 32)
    # nanolib_helper.write_number(device_handle, 1, Nanolib.OdIndex(0x608F, 0x02), 32)

     # switch the state machine to "enable voltage"
    status_word = nanolib_helper.write_number(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # choose Homing mode value = 6
    # mode_of_operation = nanolib_helper.write_number(device_handle, 6, Nanolib.OdIndex(0x6060, 0x00), 8)

    # switch the state machine to "switch on"
    status_word = nanolib_helper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # switch the state machine to "enable operation state"
    status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # Start homing 
    # status_word = nanolib_helper.write_number(device_handle, 0x1F, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # while(True):
    #     status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
    #     print("Print:", status_word)
    #     if ((status_word & 0x1400) != 0x1400):
    #          break
    #     time.sleep(0.01)

    # switch the state machine to "switch on"
    status_word = nanolib_helper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)

    # choose Profile Position mode value = 1
    mode_of_operation = nanolib_helper.write_number(device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)
    
    



    # # set the desired speed in rpm
    # target_velocity = nanolib_helper.write_number(device_handle, 54, Nanolib.OdIndex(0x6081, 0x00), 32)
    
    # # set the desired target position
    # target_velocity = nanolib_helper.write_number(device_handle, 5400, Nanolib.OdIndex(0x607A, 0x00), 32)
    # print("Printing:",target_velocity)
    # # switch the state machine to "operation enabled"
    # status_word = nanolib_helper.write_number(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
    # status_word = nanolib_helper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
    # status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # # move the motor to the desired target psoition relatively
    # status_word = nanolib_helper.write_number(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # # 6041 - destination reached
    # while(True):
    #     status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
    #     if ((status_word & 0x1400) == 0x1400):
    #         break
        
    # status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # # set the new desired target position
    # target_velocity = nanolib_helper.write_number(device_handle, -3600, Nanolib.OdIndex(0x607A, 0x00), 32)
    
    # # move the motor to the desired target psoition relatively
    # status_word = nanolib_helper.write_number(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    
    ### example code to let the motor run in Profile Position mode
    
    # stop a possibly running NanoJ program
    nanoj_control = nanolib_helper.write_number(device_handle, 0, Nanolib.OdIndex(0x2300, 0x00), 32)
    
    # choose Profile Position mode
    mode_of_operation = nanolib_helper.write_number(device_handle, 1, Nanolib.OdIndex(0x6060, 0x00), 8)
    
    # set the desired speed in rpm
    target_velocity = nanolib_helper.write_number(device_handle, 100, Nanolib.OdIndex(0x6081, 0x00), 32)
    
    # set the desired target position
    target_velocity = nanolib_helper.write_number(device_handle, 36000, Nanolib.OdIndex(0x607A, 0x00), 32)
    
    # switch the state machine to "operation enabled"
    status_word = nanolib_helper.write_number(device_handle, 6, Nanolib.OdIndex(0x6040, 0x00), 16)
    status_word = nanolib_helper.write_number(device_handle, 7, Nanolib.OdIndex(0x6040, 0x00), 16)
    status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # move the motor to the desired target psoition relatively
    status_word = nanolib_helper.write_number(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)
    status_word = nanolib_helper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)
    while(True):
        status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
        print(bin(status_word))
        if ((status_word & 0x1400) == 0x1400):
            break
        
    status_word = nanolib_helper.write_number(device_handle, 0xF, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    # set the new desired target position
    target_velocity = nanolib_helper.write_number(device_handle, -36000, Nanolib.OdIndex(0x607A, 0x00), 32)
    
    # move the motor to the desired target psoition relatively
    status_word = nanolib_helper.write_number(device_handle, 0x5F, Nanolib.OdIndex(0x6040, 0x00), 16)
    
    while(True):
        status_word = nanolib_helper.read_number(device_handle, Nanolib.OdIndex(0x6041, 0x00))
        print(bin(status_word))
        if ((status_word & 0x1400) == 0x1400):
            break
    
    # stop the motor
    status_word = nanolib_helper.write_number(device_handle, 0x6, Nanolib.OdIndex(0x6040, 0x00), 16)

    # cleanup and close everything
    nanolib_helper.disconnect_device(device_handle)
    nanolib_helper.close_bus_hardware(bus_hw_id)

    print("Closed everything successfully")