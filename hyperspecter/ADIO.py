''' Analog/Digital Input/Output using the NI BNC-2110 DAQ connected to the NI PCI-6110. 
    NI DAQmx Documentation: https://documentation.help/NI-DAQmx-C-Functions/
    PyDAQmx  Documentation: https://pythonhosted.org/PyDAQmx/
'''
import numpy as np

try:
    import PyDAQmx as pdmx
except:
    print('PyDAQmx import failed. Simulating PyDAQmx.')
    import FakePyDAQmx as pdmx


class DigitalOutput:

    def __init__(self, channel_name):
        ''' Set channel_name to the name of the digital output channel(s).  (e.g. "Dev1/port0/line0")
            Use the NI MAX software to configure and test channels.   
        '''
        self.channel_name = channel_name
        self.task = pdmx.Task()
        try:
            self.task.CreateDOChan(
                lines=self.channel_name, 
                nameToAssignToLines='', 
                lineGrouping=pdmx.DAQmx_Val_ChanForAllLines
            )
            self.task.StartTask()
            self.deviceLoaded = True
        except Exception as e:
            print(e)
            self.deviceLoaded = False

    def write(self, data, samples_per_channel=1, auto_start=1, timeout=10):
        ''' Writes data to the given digital output channel(s). data must be an array of n 8-bit unsigned integers,
            where n is the number of channels and each element of the array is the output for the given channels. 
        '''
        if self.deviceLoaded:
            self.task.WriteDigitalU8(
                numSampsPerChan=samples_per_channel,
                autoStart=auto_start,
                timeout=timeout,
                dataLayout=pdmx.DAQmx_Val_GroupByChannel,
                writeArray=data,
                reserved=None,
                sampsPerChanWritten=None
            )

    def high(self):
        ''' Writes 255 (HIGH) to digital output channel(s). '''
        self.write(np.array([255], dtype=np.uint8))

    def low(self):
        ''' Writes 0 (LOW) to digital output channel(s). '''
        self.write(np.array([0], dtype=np.uint8))

    def close(self):
        ''' Closes connection with current digital output channel. '''
        if self.deviceLoaded:
            self.task.StopTask()


class AnalogOutput:

    def __init__(self, channel_name, voltage_min=-10., voltage_max=10., clock_rate=2500000, mode='continuous', samples_per_channel=2048, source=None, trigger=None):
        ''' Maximum clock rate is 2.5 MHz for analog output channels. Samples per channel should be no more than 1/10 clock rate.
            Mode can be set to 'continuous' or 'finite'
        '''
        assert mode in ['continuous', 'finite']

        self.channel_name = channel_name
        self.number_of_channels = self.get_number_of_channels(self.channel_name)
        self.voltage_min = voltage_min
        self.voltage_max = voltage_max
        self.clock_rate = int(clock_rate)
        self.mode = mode
        self.samples_per_channel = int(samples_per_channel)
        self.source = source
        self.trigger = trigger
        self.task_started = False

        self.task = pdmx.Task()
        self.__configure_task()
    
    def __configure_task(self):
        ''' Configures the Task object. '''
        self.task.CreateAOVoltageChan(
            physicalChannel=self.channel_name,
            nameToAssignToChannel='',
            minVal=self.voltage_min,
            maxVal=self.voltage_max,
            units=pdmx.DAQmx_Val_Volts,
            customScaleName=None
        )

        if self.mode == 'continuous':
            sample_mode = pdmx.DAQmx_Val_ContSamps
        elif self.mode == 'finite':
            sample_mode = pdmx.DAQmx_Val_FiniteSamps

        self.task.CfgSampClkTiming(
            source=self.source,
            rate=self.clock_rate,
            activeEdge=pdmx.DAQmx_Val_Rising,
            sampleMode=sample_mode,
            sampsPerChan=self.samples_per_channel
        )
        
        if self.trigger:
            self.task.CfgDigEdgeStartTrig(triggerSource=self.trigger, triggerEdge=pdmx.DAQmx_Val_Rising)

    def write(self, data, samples_per_channel=None, auto_start=False, timeout=10.):
        ''' Writes analog output data to channels. Data should be grouped by channel. 
            Example:
                If CH1 and CH2 have the following output arrays,
                    CH1 = [x1, x2, x3, ..., xn] 
                    CH2 = [y1, y2, y3, ..., yn]
                They should be concatenated with np.concatenate((CH1,CH2)) as follows.
                    data = [x1, x2, x3, ..., xn, y1, y2, y3, ..., yn]
        '''
        
        if not samples_per_channel:
            samples_per_channel = round(data.size/self.number_of_channels)
        else:
            samples_per_channel = int(samples_per_channel)
        
        self.task.WriteAnalogF64(
            numSampsPerChan=samples_per_channel,
            autoStart=auto_start,
            timeout=timeout,
            dataLayout=pdmx.DAQmx_Val_GroupByChannel,
            writeArray=data,
            sampsPerChanWritten=None,
            reserved=None
        )
        
        self.start()

    # def zero(self):
    #     ''' Outputs zero. '''
    #     self.task.WriteAnalogScalarF64(False,10,0.0,None)

    def start(self):
        ''' Preferred way to start the task. '''
        if not self.task_started:
            self.task.StartTask()
            self.task_started = True

    def wait(self, timeout=10.):
        ''' Waits for the task to finish. If the task takes longer than timeout (seconds) it is terminated. '''
        self.task.WaitUntilTaskDone(timeout)

    def stop(self):
        ''' Preferred way to stop the task. '''
        if self.task_started:
            # self.zero()
            self.task.StopTask()
            self.task_started = False

    def clear(self):
        ''' Preferred way to clear the task. '''
        if self.task_started: self.stop()
        self.task.ClearTask()

    def get_number_of_channels(self, channel_name):
        ''' Returns the number of channels in the given analog channel name. 
            The channel name is of the form "Dev1/["ai" or "ao"][first channel]:[last channel]".
            
            Example: "Dev1/ai1:3" specifies that we are using the analog input channels 1, 2, and 3 on the device named Dev1.
            So the number of channels is 3. 
        '''
        
        # Determine if analog input or output.
        if 'ai' in channel_name:
            ch = 'ai'
            raise Exception('Analog input channel cannot be used for analog output.')
        else:
            ch = 'ao'
        
        i = channel_name.find(ch) + 2   # i is the index of the first channel
        j = channel_name.find(':')      # j is the index of the last channel

        if j == -1:
            number_of_channels = 1 # if no last channel is given, there is only one channel being used
        else:
            # if there is a last channel, the number of channels is the difference between the first and last (+1 since it's inclusive)
            lower = int(channel_name[i:j])
            upper = int(channel_name[j+1:])
            number_of_channels = upper - lower + 1
        return number_of_channels


class AnalogInput:
    
    def __init__(self, channel_name, voltage_min=-10., voltage_max=10., clock_rate=5000000, mode='continuous', samples_per_channel=8192, source=None, trigger=None, offset=1):
        ''' Maximum clock rate is 5 MHz for analog output channels. Samples per channel should be no more than 1/10 clock rate.
        '''
        assert mode in ['continuous', 'finite'], f'{mode} is not a valid mode.'

        self.channel_name = channel_name
        self.number_of_channels = self.get_number_of_channels(self.channel_name)
        self.voltage_min = voltage_min
        self.voltage_max = voltage_max
        self.clock_rate = int(clock_rate)
        self.mode = mode
        self.samples_per_channel = int(samples_per_channel)
        self.source = source
        self.trigger = trigger
        self.offset = offset
        self.task_started = False

        self.task = pdmx.Task()
        self.__configure_task()

    def __configure_task(self):
        
        self.task.CreateAIVoltageChan(
            physicalChannel=self.channel_name, 
            nameToAssignToChannel='',
            terminalConfig=pdmx.DAQmx_Val_Cfg_Default,
            minVal=self.voltage_min,
            maxVal=self.voltage_max,
            units=pdmx.DAQmx_Val_Volts,
            customScaleName=None
        )

        if self.mode == 'continuous':
            sample_mode = pdmx.DAQmx_Val_ContSamps
        elif self.mode == 'finite':
            sample_mode = pdmx.DAQmx_Val_FiniteSamps

        self.task.CfgSampClkTiming(
            source=self.source,
            rate=self.clock_rate,
            activeEdge=pdmx.DAQmx_Val_Falling,
            sampleMode=sample_mode,
            sampsPerChan=self.samples_per_channel
        )

        # Sets read offset in samples. This removes the extra sample that was being read before the analog output started.
        offset = pdmx.int32(self.offset)
        pdmx.DAQmxSetReadOffset(self.task.taskHandle, offset)
        # pdmx.DAQmxGetReadOffset(self.task.taskHandle, pdmx.byref(offset))
        # print(f'Read offset: {offset}')
        
        if self.trigger:
            self.task.CfgDigEdgeStartTrig(triggerSource=self.trigger, triggerEdge=pdmx.DAQmx_Val_Rising)


    def read(self, samples_per_channel=None, timeout=10):
        ''' Reads analog input according to the configured task. 

            Inputs : 
                samples_per_channel (int): the number of samples to be read.
                timeout (float): time to wait before stopping task. 

            Returns :
                read_data: 2D numpy array containing read data separated by channel [channel, data]
        '''
        if not samples_per_channel:
            samples_per_channel = self.samples_per_channel
        else:
            samples_per_channel = int(samples_per_channel)

        self.start()

        read_array = np.zeros((self.number_of_channels*samples_per_channel), dtype=np.float64)
        self.task.ReadAnalogF64(
            numSampsPerChan=samples_per_channel,
            timeout=timeout,
            fillMode=pdmx.DAQmx_Val_GroupByChannel,
            readArray=read_array,
            arraySizeInSamps=self.number_of_channels * samples_per_channel,
            sampsPerChanRead=None,
            reserved=None
        )
        return np.split(read_array, self.number_of_channels)
        # return read_array

    def start(self):
        ''' Preferred way to start the task. '''
        if not self.task_started:
            self.task.StartTask()
            self.task_started = True

    def wait(self, timeout=10.):
        ''' Waits for the task to finish. If the task takes longer than timeout (seconds) it is terminated. '''
        self.task.WaitUntilTaskDone(timeout)

    def stop(self):
        ''' Preferred way to stop the task. '''
        if self.task_started:
            self.task.StopTask()
            self.task_started = False

    def clear(self):
        ''' Preferred way to clear the task. '''
        if self.task_started: self.stop()
        self.task.ClearTask()

    def get_number_of_channels(self, channel_name):
        ''' Returns the number of channels in the given analog channel name. 
            The channel name is of the form "Dev1/["ai" or "ao"][first channel]:[last channel]".
            
            Example: "Dev1/ai1:3" specifies that we are using the analog input channels 1, 2, and 3 on the device named Dev1.
            So the number of channels is 3. 
        '''
        
        # Determine if analog input or output.
        if 'ai' in channel_name:
            ch = 'ai'
        else:
            ch = 'ao'
            raise Exception('Analog output channel cannot be used for analog input.')
        
        i = channel_name.find(ch) + 2   # i is the index of the first channel
        j = channel_name.find(':')      # j is the index of the last channel

        if j == -1:
            number_of_channels = 1 # if no last channel is given, there is only one channel being used
        else:
            # if there is a last channel, the number of channels is the difference between the first and last (+1 since it's inclusive)
            lower = int(channel_name[i:j])
            upper = int(channel_name[j+1:])
            number_of_channels = upper - lower + 1
        return number_of_channels




if __name__ == '__main__':
    import time
    import matplotlib.pyplot as plt
    import utils

    # TODO: move the tests to the tests folder

    def test_analog_output():
        ''' Test analog output.
            
            Instructions: Connect oscilloscope to Dev1/ao0. Produce 1 Hz sine wave with amplitude of 1 V.
        '''

        clock_rate = 625000 # samples per second
        duration = 5 # seconds
        sine_frequency = 1 # Hz
        
        number_of_samples = duration * clock_rate
        f = sine_frequency/clock_rate
        t = np.arange(number_of_samples)
        data = np.sin(2*np.pi*f*t)

        plt.figure()
        plt.plot(data)
        plt.show()

        ao = AnalogOutput('Dev1/ao0', clock_rate=clock_rate, mode='finite', samples_per_channel=number_of_samples)
        ao.write(data, samples_per_channel=number_of_samples)
        ao.wait(10)
        ao.stop()
        ao.clear()

    def test_galvo_scan():
        ''' Testing ananlog output for controlling galvo mirrors
        
            Instructions: Connect oscilloscope CH1 to Dev1/ao0 and CH2 to Dev1/ao1.
        '''

        x_pixels = 250 # pixels
        y_pixels = 250 # pixels
        samples_per_pixel = 1
        line_dwell_time = 5 # milliseconds

        samples_per_line = round(x_pixels * samples_per_pixel)

        clock_rate = round(1000*samples_per_line/line_dwell_time)

        x_axis = utils.sawtooth(x_pixels, samples_per_pixel, y_pixels)
        y_axis = utils.sawtooth(y_pixels, samples_per_line, 1)

        # data = np.vstack((x_axis,y_axis)).ravel('F')
        data = np.concatenate((x_axis, y_axis))

        plt.figure()
        plt.plot(x_axis)
        plt.plot(y_axis)
        plt.show()

        # Finite output sets voltage to galvo for only one frame of imaging
        # ao = AnalogOutput('Dev1/ao0:1', clock_rate=clock_rate, mode='finite', samples_per_channel=samples_per_pixel*x_pixels*y_pixels)
        ao = AnalogOutput('Dev1/ao0:1', clock_rate=clock_rate, mode='continuous', samples_per_channel=1)
        ao.write(data)
        try:
            # ao.wait(20)
            time.sleep(20)
        except KeyboardInterrupt:
            pass
        ao.stop()
        ao.clear()

    def test_analog_input():
        ''' Testing ananlog input from function generator

            Instructions: Connect function generator output (1 kHz sine wave) to Dev1/ai3.
        '''

        clock_rate = 5E6 # samples per second
        read_time = 5 # milliseconds

        number_of_samples = int(read_time/1000 * clock_rate)

        ai = AnalogInput('Dev1/ai3')
        data = ai.read(samples_per_channel=number_of_samples)
        ai.clear()

        plt.figure()
        plt.plot(data)
        plt.show()

    def benchmark_read_speed():
        ''' Benchmarking read speed for 250 x 250 = 62500 pixels
        '''

        number_of_samples = 62500

        ai = AnalogInput('Dev1/ai3', clock_rate=5000000, mode='finite', samples_per_channel=number_of_samples)
        ai.start()

        start_time = time.perf_counter()
        ai.read(samples_per_channel=number_of_samples)
        end_time = time.perf_counter()
        
        ai.clear()

        print(f'Time: {end_time - start_time}')

    def test_sync_io():
        ''' Testing synchonous ananlog output and input. 

            Instructions: Connect Dev1/ao0 to Dev1/ai3.
        '''

        points = 250 # pixels
        repeats_per_point = 1
        duration = 5 # milliseconds

        samples_per_line = round(points * repeats_per_point)
        clock_rate = round(1000*samples_per_line/duration)

        write_data = 3 * utils.sawtooth(points, repeats_per_point) - 1.5

        ai = AnalogInput('Dev1/ai3', clock_rate=clock_rate, mode='continuous', samples_per_channel=1)
        ao = AnalogOutput('Dev1/ao0', clock_rate=clock_rate, mode='continuous', samples_per_channel=1, source='/Dev1/ai/SampleClock', trigger='/Dev1/ai/StartTrigger')
        ao.write(write_data)
        
        read_data = [[] for _ in range(ai.number_of_channels)]

        ## For continuous reading mode
        for i in range(5):
            try:
                data = ai.read(samples_per_channel=samples_per_line)
                for channel, array in enumerate(data):
                    read_data[channel].extend(array.tolist())
            except KeyboardInterrupt:
                print('loop terminated')
                break

        ### For finite reading mode
        # data = ai.read(samples_per_channel=len(write_data))
        # ai.wait()
        # for channel, array in enumerate(data):
        #     read_data[channel].extend(array.tolist())



        ao.stop()
        ao.clear()

        ai.stop()
        ai.clear()

        plt.figure(0)
        plt.plot(read_data[0])
        plt.show()


    benchmark_read_speed()
