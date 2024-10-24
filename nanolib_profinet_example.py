import time
from nanotec_nanolib import Nanolib

class ProfinetExample():
    
    def __del__(self):
        print("")
    
    def printIfNanolibError(self, nanolibResult):
        if(nanolibResult.hasError()):
            print(str(nanolibResult.getError()))
            print("")
    
    def __init__(self, busHardwareId, profinetDCP):
        print("")
        if(
            isinstance(busHardwareId, Nanolib.BusHardwareId)
        ):
            self.busHardwareId = busHardwareId
        else:
            raise Exception("Invalid BusHardwareId")
        
        self.profinetDCP = profinetDCP
    
    def execute(self):
        profinetDCP = self.profinetDCP
        resultServiceAvailable = profinetDCP.isServiceAvailable(self.busHardwareId)
        
        if(resultServiceAvailable.hasError() == False):
            print("Scanning for Profinet devices...")
            resultProfinetDeviceVector = profinetDCP.scanProfinetDevices(self.busHardwareId)
            print("")
            profinetDeviceVector = resultProfinetDeviceVector.getResult()
            
            if(len(profinetDeviceVector) >= 1):
                targetProfinetDevice = profinetDeviceVector[0]
                
                for profinetDevice in profinetDeviceVector:
                    print("" + "Name:" + "    " + str(profinetDevice.deviceName))
                    print("" + "IP:" + "      " + self.convertIntegerToIPv4(profinetDevice.ipAddress))
                    print("")
                
                result = profinetDCP.validateProfinetDeviceIp(self.busHardwareId, targetProfinetDevice)
                if(result.hasError() == False):
                    print("Device IP is valid into current network.")
                else:
                    print("Device IP is not valid into current network.")
                self.printIfNanolibError(result)
                print("")
                
                result = profinetDCP.blinkProfinetDevice(self.busHardwareId, targetProfinetDevice)
                if(result.hasError() == False):
                    print("Blink the device succeeded.")
                else:
                    print("Blink the device failed.")
                self.printIfNanolibError(result)
                print("")
            
            else:
                print("No Profinet devices found.")
                print("")
        
        else:
            print("Service not available.")
            print("")
    
    def convertIntegerToIPv4(self, number):
        number = int(number)
        result = str(number)

        if(
            number >= 0x_01_00_00_01 and
            number <= 0x_FF_FF_FF_FF
        ):
            numberString = str(format(number, '08x'))

            octet1 = int((numberString[0:2]), 16)
            octet2 = int((numberString[2:4]), 16)
            octet3 = int((numberString[4:6]), 16)
            octet4 = int((numberString[6:8]), 16)

            result = str(octet1) + "." + str(octet2) + "." + str(octet3) + "." + str(octet4)

        return result
