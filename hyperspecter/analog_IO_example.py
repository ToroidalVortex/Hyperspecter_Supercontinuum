import ctypes
import time

import numpy as np
import matplotlib.pyplot as plt

try:
    import PyDAQmx as pdmx
except:
    print('PyDAQmx import failed. Simulating PyDAQmx.')
    import FakePyDAQmx as pdmx


rate = 2500000
samples = 250000

# Configure analog input task
ai = pdmx.Task()
ai.CreateAIVoltageChan(
    physicalChannel='/Dev1/ai3', 
    nameToAssignToChannel='',
    terminalConfig=pdmx.DAQmx_Val_Cfg_Default,
    minVal=-10.,
    maxVal=10.,
    units=pdmx.DAQmx_Val_Volts,
    customScaleName=None
)
ai.CfgSampClkTiming(
    source=None,
    rate=rate,
    activeEdge=pdmx.DAQmx_Val_Rising,
    sampleMode=pdmx.DAQmx_Val_ContSamps,
    # sampleMode=pdmx.DAQmx_Val_FiniteSamps,
    sampsPerChan=1
)

# Configure analog output task
ao = pdmx.Task()
ao.CreateAOVoltageChan(
    physicalChannel='/Dev1/ao0',
    nameToAssignToChannel='',
    minVal=-10.,
    maxVal=10.,
    units=pdmx.DAQmx_Val_Volts,
    customScaleName=None
)
ao.CfgSampClkTiming(
    source='/Dev1/ai/SampleClock',
    rate=rate,
    activeEdge=pdmx.DAQmx_Val_Rising,
    sampleMode=pdmx.DAQmx_Val_ContSamps,
    # sampleMode=pdmx.DAQmx_Val_FiniteSamps,
    sampsPerChan=samples*5
)
ao.CfgDigEdgeStartTrig(
    triggerSource='/Dev1/ai/StartTrigger',
    triggerEdge=pdmx.DAQmx_Val_Rising
)

ao.WriteAnalogF64(
    numSampsPerChan=samples,
    autoStart=False,
    timeout=10,
    dataLayout=pdmx.DAQmx_Val_GroupByChannel,
    writeArray=np.array([x/samples for x in range(samples)], dtype=np.float64),
    sampsPerChanWritten=None,
    reserved=None
)

ao.StartTask()

ai.StartTask()

read_array = np.zeros(samples, dtype=np.float64)
ai.ReadAnalogF64(
    numSampsPerChan=samples,
    timeout=10,
    fillMode=pdmx.DAQmx_Val_GroupByChannel,
    readArray=read_array,
    arraySizeInSamps=samples,
    sampsPerChanRead=None,
    reserved=None
)

# ai.WaitUntilTaskDone(10)
time.sleep(10)

ai.StopTask()
ai.ClearTask()

ao.StopTask()
ao.ClearTask()
