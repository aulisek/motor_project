import time
from nanotec_nanolib import Nanolib

class SamplerNotifyCallback(Nanolib.SamplerNotify):
    
    def __init__(self, samplerExample):
        super().__init__()
        self.isSamplerActive = True
        if(isinstance(samplerExample, SamplerExample)):
            self.samplerExample = samplerExample
        else:
            raise Exception("Invalid SamplerExample Object")
    
    def notify(self, lastError, samplerState, sampleDatas, applicationData):
        # Be aware that notifications are executed in the context of separate threads 
        # other than thread that started the sampler.
        # 
        # Be careful when calling Nanolib functionality here, as doing so may cause this method
        # to be called recursively, potentially causing your application to deadlock.
        # 
        # For the same reason, this method should not throw exceptions.
        self.isSamplerActive = True
        self.samplerExample.processSampledData(sampleDatas)
        self.samplerState = samplerState
        if(
            (samplerState != Nanolib.SamplerState_Ready) and 
            (samplerState != Nanolib.SamplerState_Running)
        ):
            if (samplerState == Nanolib.SamplerState_Failed):
                print("")
                print("Sampler execution failed with error: " + lastError.getError())
            # It's now safe to destroy (this) notification object
            self.isSamplerActive = False

class SamplerExample():
    
    def __init__(self, deviceHandle, nanolibHelper):
        self.nanolibAccessor = nanolibHelper.nanolib_accessor

        self.samplerInterface = self.nanolibAccessor.getSamplerInterface()
        self.samplerConfiguration = Nanolib.SamplerConfiguration()

        if(
            isinstance(deviceHandle, Nanolib.DeviceHandle)
        ):
            self.deviceHandle = deviceHandle
        else:
            raise Exception("Invalid DeviceHandle")
        
        odIndex_Vector = [
            Nanolib.OdIndex(0x230F, 0x00),
            Nanolib.OdIndex(0x4014, 0x03)
        ]
        odIndex_Vector = Nanolib.OdIndexVector(odIndex_Vector)
        self.trackedAddresses = odIndex_Vector
        self.addressNames = ["UpTime", "Temperature"]
        self.lastIteration = 0
        self.listTitle = []
        self.sampleNumber = 0
        self.triggerAddress = Nanolib.OdIndex(0x2400, 0x01)
        self.startTrigger = Nanolib.SamplerTrigger()
        self.startTrigger.condition = Nanolib.SamplerTriggerCondition_TC_GREATER
        self.startTrigger.address = self.triggerAddress
        self.startTrigger.value = 10
    
    def executeWithCallbackNormal(self):
        print(">>" + " " + "Sampler with callback in normal mode:")
        self.printColumnHeading()
        samplerNotifyCallback = SamplerNotifyCallback(self)
        self.setSamplerConfiguration(Nanolib.SamplerMode_Normal)
        self.startSampler(samplerNotifyCallback)
        while(samplerNotifyCallback.isSamplerActive):
            time.sleep(0.100)

    def executeWithCallbackRepetitive(self):
        print(">>" + " " + "Sampler with callback in repetative mode:")
        self.printColumnHeading()
        samplerNotifyCallback = SamplerNotifyCallback(self)
        self.setSamplerConfiguration(Nanolib.SamplerMode_Repetitive)
        self.startSampler(samplerNotifyCallback)
        while(samplerNotifyCallback.isSamplerActive):
            time.sleep(0.100)
            if(self.lastIteration >= 4):
                self.samplerInterface.stop(
                    self.deviceHandle
                )
    
    def executeWithCallbackContinuous(self):
        print(">>" + " " + "Sampler with callback in continuous mode:")
        self.printColumnHeading()
        samplerNotifyCallback = SamplerNotifyCallback(self)
        self.setSamplerConfiguration(Nanolib.SamplerMode_Continuous)
        self.startSampler(samplerNotifyCallback)
        time.sleep(10.000)
        self.samplerInterface.stop(
            self.deviceHandle
        )

    def executeWithCallback(self):
        self.executeWithCallbackNormal()
        print("")
        self.executeWithCallbackRepetitive()
        print("")
        self.executeWithCallbackContinuous()
        print("")
    
    def executeWithoutCallbackNormal(self):
        print(">>" + " " + "Sampler without callback in normal mode:")
        self.printColumnHeading()

        self.setSamplerConfiguration(Nanolib.SamplerMode_Normal)
        self.nanolibAccessor.writeNumber(self.deviceHandle, 0, self.triggerAddress, 32)
        self.startSampler(None)
        self.nanolibAccessor.writeNumber(self.deviceHandle, 11, self.triggerAddress, 32)

        lastState = None
        isLoopActive = True
        while(isLoopActive):
            time.sleep(0.100)
            samplerState = self.getSamplerState()
            if(
                samplerState != Nanolib.SamplerState_Ready and
                samplerState != Nanolib.SamplerState_Running
            ):
                if (samplerState == Nanolib.SamplerState_Failed):
                    lastError = self.getSamplerLastError()
                    print("")
                    print("Sampler execution failed with error: " + lastError.getError())
                    return
                isLoopActive = False
            
            if(samplerState != lastState):
                lastState = samplerState
            self.processSampledData(self.getSamplerData())
    
    def executeWithoutCallbackRepetitive(self):
        print(">>" + " " + "Sampler without callback in repetative mode:")
        self.printColumnHeading()

        self.setSamplerConfiguration(Nanolib.SamplerMode_Repetitive)
        self.nanolibAccessor.writeNumber(self.deviceHandle, 0, self.triggerAddress, 32)
        self.startSampler(None)
        self.nanolibAccessor.writeNumber(self.deviceHandle, 11, self.triggerAddress, 32)

        lastState = None
        isLoopActive = True
        while(isLoopActive):
            time.sleep(0.100)
            samplerState = self.getSamplerState()
            if(
                samplerState != Nanolib.SamplerState_Ready and
                samplerState != Nanolib.SamplerState_Running
            ):
                if (samplerState == Nanolib.SamplerState_Failed):
                    lastError = self.getSamplerLastError()
                    print("")
                    print("Sampler execution failed with error: " + lastError.getError())
                    return
                isLoopActive = False
            
            if(self.lastIteration >= 4):
                self.samplerInterface.stop(
                    self.deviceHandle
                )
            
            if(samplerState != lastState):
                lastState = samplerState
            self.processSampledData(self.getSamplerData())
    
    def executeWithoutCallbackContinuous(self):
        print(">>" + " " + "Sampler without callback in continuous mode:")
        self.printColumnHeading()

        self.setSamplerConfiguration(Nanolib.SamplerMode_Continuous)
        self.nanolibAccessor.writeNumber(self.deviceHandle, 0, self.triggerAddress, 32)
        self.startSampler(None)
        self.nanolibAccessor.writeNumber(self.deviceHandle, 11, self.triggerAddress, 32)

        lastState = None
        isLoopActive = True
        secondsPassed = 0
        while(isLoopActive):
            time.sleep(1.000)
            secondsPassed += 1
            
            if(secondsPassed >= 10):
                self.samplerInterface.stop(
                    self.deviceHandle
                )
            
            samplerState = self.getSamplerState()
            if(
                samplerState != Nanolib.SamplerState_Ready and
                samplerState != Nanolib.SamplerState_Running
            ):
                if (samplerState == Nanolib.SamplerState_Failed):
                    lastError = self.getSamplerLastError()
                    print("")
                    print("Sampler execution failed with error: " + lastError.getError())
                    return
                isLoopActive = False
            
            if(samplerState != lastState):
                lastState = samplerState
            self.processSampledData(self.getSamplerData())
        
        print("")
    
    def executeWithoutCallback(self):
        self.executeWithoutCallbackNormal()
        print("")
        self.executeWithoutCallbackRepetitive()
        print("")
        self.executeWithoutCallbackContinuous()
        print("")
    
    def processSampledData(self, resultData):
        if(isinstance(resultData, Nanolib.SampleDataVector)):
            dataArray = resultData
        else:
            dataArray = resultData.getResult()
        
        countId = 0
        for data in dataArray:
            countId += 1
            sampledValues = data.sampledValues
            
            allValues = []
            allValuesTime = []
            for obj in sampledValues:
                allValues.append(obj.value)
                allValuesTime.append(obj.collectTimeMsec)
            
            if(self.lastIteration != data.iterationNumber):
                self.sampleNumber = 0
            self.lastIteration = data.iterationNumber
            
            rowValues = []
            rowValues.append(self.lastIteration)
            rowValues.append(self.sampleNumber)
            for listId in range(0, len(self.addressNames)):
                rowValues.append(allValues[listId])
                rowValues.append(allValuesTime[listId])
            self.printColumnRow(
                rowValues
            )
            self.sampleNumber += 1
    
    def printColumnRow(self, newList, endLine = "\n"):
        endLine = str(endLine)
        if(isinstance(newList, list)):
            newString = ""
            for listId in range(0, len(newList)):
                newString += str(newList[listId])
                if(listId < len(newList) - 1):
                    countTitleSymbols = len(str(self.listTitle[listId]))
                    countValueSymbols = len(str(newList[listId]))
                    countPreviousTitleSymbols = 0
                    countPreviousValueSymbols = 0
                    if(listId >= 1):
                        countPreviousTitleSymbols = len(str(self.listTitle[listId - 1]))
                        countPreviousValueSymbols = len(str(newList[listId - 1]))
                    
                    if(countTitleSymbols >= countValueSymbols):
                        for countValueSymbolId in range(0, (countTitleSymbols - countValueSymbols) + 3):
                            newString += " "
                    else:
                        newString += " "
            print(
                newString, 
                end = endLine
            )
    
    def printColumnHeading(self, endLine = "\n"):
        newList = ["Iteration", "Sample"]
        for listId in self.addressNames:
            newList.append(listId)
            newList.append("Time")
        self.listTitle = newList
        # print("")
        print("-------------------------------------------------------")
        newString = ""
        countId = 0
        for newValue in newList:
            newValue = str(newValue)
            newString += newValue
            for countId in range(0, 3):
                newString += " "
            countId += 1
        print(newString)
        print("-------------------------------------------------------")
    
    def startSampler(self, notifyCallback):
        self.lastIteration = 0
        self.sampleNumber = 0

        resultStart = self.samplerInterface.start(
            self.deviceHandle,
            notifyCallback,
            0
        )
        if(resultStart.hasError()):
            raise Exception("samplerInterface.start:" + " " + str(resultStart.getError()))
    
    def setSamplerConfiguration(self, targetMode):
        if targetMode == Nanolib.SamplerMode_Continuous:
            self.samplerConfiguration.durationMilliseconds = 0
        else:
            self.samplerConfiguration.durationMilliseconds = 4000
        self.samplerConfiguration.periodMilliseconds = 1000
        self.samplerConfiguration.preTriggerNumberOfSamples = 0 # Unused currently
        self.samplerConfiguration.trackedAddresses = self.trackedAddresses
        self.samplerConfiguration.startTrigger = self.startTrigger
        self.samplerConfiguration.usingSoftwareImplementation = (targetMode == Nanolib.SamplerMode_Continuous)
        self.samplerConfiguration.mode = targetMode

        resultConfigure = self.samplerInterface.configure(
            self.deviceHandle,
            self.samplerConfiguration
        )
        if(resultConfigure.hasError()):
            raise Exception("samplerInterface.configure:" + " " + str(resultConfigure.getError()))
    
    def getSamplerState(self):
        resultSamplerState = self.samplerInterface.getState(self.deviceHandle)
        if(resultSamplerState.hasError()):
            raise Exception("samplerInterface.getState:" + " " + str(resultSamplerState.getError()))
        samplerState = resultSamplerState.getResult()
        return samplerState
    
    def getSamplerData(self):
        resultSamplerData = self.samplerInterface.getData(self.deviceHandle)
        if(resultSamplerData.hasError()):
            raise Exception("samplerInterface.getData:" + " " + str(resultSamplerData.getError()))
        return resultSamplerData

    def getSamplerLastError(self):
        return self.samplerInterface.getLastError(self.deviceHandle)

    def getSamplerStateAsText(self, key):
        key = int(key)

        switchCases = {
            0: "Unconfigured",
            1: "Configured",
            2: "Ready",
            3: "Running",
            4: "Completed",
            5: "Failed",
            6: "Cancelled"
        }

        # Search by key or return it if it is not found
        result = (switchCases.get(key, key))

        return result
