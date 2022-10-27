from textwrap import fill
import time
from queue import Queue

import numpy as np

import ADIO
import utils


class MicroscopeController:
    def __init__(self, resolution=256, line_dwell_time=5, zoom=1, scan_pattern='sawtooth', fill_fraction=1.0, flyback=0, 
                y_offset=0, delay=0, start_wait=100, simulate=False, number_of_channels=4):
        ''' MicroscopeController allows the user to define the behaviour of the laser scanning microscope. 
        
        Attributes:
            resolution (int): the number of pixels along each axis of the square raster scan.
            line_dwell_time (int): the time in milliseconds it will take for the laser to strafe one line of pixels.
            zoom: how much to scale down the size of the laser scan path.
            scan_pattern: indicates whether to use the 'sawtooth' or 'triangle' scan pattern.
            fill_fraction: ratio between the acquired samples and total samples in the laser scan path.
                Although shutters can be used to block the beam and acquisition can be toggled, it is practical
                to record all samples and simply remove the extra samples in post-processing. 

                fill_fraction = resolution / total_samples

            simulate (bool): simulate image data as random noise instead of actually producing real image data.
            number_of_channels (int): the number of channels to simulate.
                Note: pmts.number_of_channels gives the actual number of input channels to be read from.

        Usage:
            microscope = MicroscopeController(resolution=250, line_dwell_time=5, simulate=False)
            frame = microscope.get_frame()
            
        '''
        self.resolution = resolution
        self.line_dwell_time = line_dwell_time
        self.zoom = zoom
        self.scan_pattern = scan_pattern
        self.fill_fraction = fill_fraction
        self.flyback = flyback
        self.y_offset = y_offset
        self.delay = delay
        self.start_wait = start_wait
        self.simulate = simulate
        self.number_of_channels = number_of_channels # number of channels to simulate
        self.acquiring = False

    def update_settings(self, settings):
        assert not self.acquiring, 'Must stop acquiring to modify parameters.'
        self.resolution = settings['image resolution']
        self.line_dwell_time = settings['line dwell time']
        self.zoom = settings['zoom']
        self.scan_pattern = settings['scan pattern']
        self.fill_fraction = settings['fill fraction']
        self.flyback = settings['flyback']
        self.simulate = settings['simulate']
        self.y_offset = settings['galvo y-axis offset']
        self.delay = settings['scan delay']
    
    def __configure_microscope(self, mode):
        if self.simulate: return 0 # if simulating, bypass hardware configuration

        MAX_GALVO_VOLTAGE = 10.0 # plus/minus volts

        # Galvo mirror scan setup
        # Set peak-peak voltage to double the anticipated waveform amplitude then
        # subtract half of the amplitude off so that the waveform is centered at 0V
        self.amplitude = MAX_GALVO_VOLTAGE / self.zoom
        x_offset    = 0.0
        y_offset    = self.y_offset
        self.offset = (x_offset, y_offset)
        
        if self.scan_pattern == 'sawtooth':
            x_data, y_data, self.samples_per_line, self.throwaway, self.flyback, self.padding = utils.generate_sawtooth_scan(
                resolution=(self.resolution,self.resolution),
                amplitude=self.amplitude,
                offset=self.offset,
                fill_fraction=self.fill_fraction,
                flyback=self.flyback,
                padding=(self.start_wait, self.delay)
            )
        
        elif self.scan_pattern == 'bidirectional':
            x_data, y_data, self.samples_per_line, self.throwaway, self.padding = utils.generate_bidirectional_scan(
                resolution=(self.resolution,self.resolution),
                amplitude=self.amplitude,
                offset=self.offset,
                fill_fraction=self.fill_fraction,
                padding=(self.start_wait, self.delay)
            )


        write_data = np.concatenate((x_data, y_data))
        
        self.clock_rate = round(1000*self.samples_per_line/self.line_dwell_time)
        self.read_samples = self.samples_per_line * self.resolution + sum(self.padding)

        if mode == 'finite':
            self.samples_per_channel = self.read_samples
        elif mode == 'continuous':
            self.samples_per_channel = 1

        self.pmts = ADIO.AnalogInput(
            channel_name='Dev1/ai0:3',
            clock_rate=self.clock_rate,
            mode=mode,
            samples_per_channel=self.samples_per_channel,
            offset=0
        )

        self.galvos = ADIO.AnalogOutput(
            channel_name='Dev1/ao0:1',
            clock_rate=self.clock_rate,
            mode=mode,
            samples_per_channel=self.samples_per_channel,
            source='/Dev1/ai/SampleClock',
            trigger='/Dev1/ai/StartTrigger'
        )

        # self.number_of_channels = self.pmts.number_of_channels
        self.galvos.write(write_data)

    def get_frame(self):
        ''' Takes a single image with the microscope. 

            Returns:
                read_data: 3D numpy array containing image data of type [channel, y, x]
        '''
        if self.simulate:
            time.sleep(self.line_dwell_time/1000*self.resolution) # simulate work
            return np.random.randn(self.number_of_channels, self.resolution, self.resolution)
        else:
            self.__configure_microscope(mode='finite')
            data = self.pmts.read(samples_per_channel=self.read_samples)
            self.pmts.wait()
            self.galvos.stop()
            self.galvos.clear()
            self.pmts.stop()
            self.pmts.clear()
            
            frame = self.process_frame(data)
            
            return frame
        
    def get_frames(self, image_q:Queue):
        ''' Continuously record frames and add them to a queue. Sentinel value of None type indicates the reading process has been terminated. 
            This should be used as the "producer" within the typical producer-consumer pattern.

        Inputs:
            image_q (queue.Queue): a thread-safe queue to add images to as they are produced.
        '''
        self.acquiring = True

        if self.simulate:
            while self.acquiring:
                try:
                    time.sleep(self.line_dwell_time/1000*self.resolution) # simulate work
                    frame = np.random.randn(self.number_of_channels, self.resolution, self.resolution)
                    image_q.put(frame)
                except KeyboardInterrupt:
                    self.acquiring = False
                    break
        else:
            self.__configure_microscope(mode='continuous')
            while self.acquiring:
                try:
                    data = self.pmts.read(samples_per_channel=self.read_samples)
                    
                    frame = self.process_frame(data)
                    
                    image_q.put(frame)
                except KeyboardInterrupt:
                    self.acquiring = False
                    break

            self.galvos.stop()
            self.galvos.clear()
            self.pmts.stop()
            self.pmts.clear()

        image_q.put(None) # sentinel value

    def process_frame(self, raw_data):
        frame = [[] for _ in range(self.pmts.number_of_channels)]
        for channel, channel_data in enumerate(raw_data):
            channel_data = channel_data[self.start_wait+self.delay:] # shift data to account for start wait and delay
            frame[channel] = np.array_split(channel_data, self.resolution) # separates image channel data into 2D list of arrays

            # Account for fill fraction
            for line, line_data in enumerate(frame[channel]):
                start = self.throwaway
                stop = start + self.resolution
                frame[channel][line] = line_data[start:stop]
                
            if self.scan_pattern == 'bidirectional':
                # Flip every other row
                for i in range(1, self.resolution, 2):
                    frame[channel][i] = np.flip(frame[channel][i])

        return np.array(frame)

    def stop(self):
        self.acquiring = False
        


if __name__ == '__main__':
    import sys
    import time
    import numpy as np
    import pyqtgraph as pg
    from PyQt5 import QtCore, QtGui, QtWidgets

    microscope = MicroscopeController(simulate=True)
    frame = microscope.get_frame()
    number_of_channels = microscope.number_of_channels

    # Create Qt application
    app = QtWidgets.QApplication(sys.argv)
    
    # Create main window for application
    display_panel = pg.GraphicsLayoutWidget()
    display_panel.setWindowTitle('Microscope Test')
    display_panel.resize(400*number_of_channels, 525)
    layout = display_panel.ci.layout # layout is an instance of QGraphicsGridLayout
    layout.setRowStretchFactor(1, 10) # stretches out the image row so that the images appear larger

    for i in range(number_of_channels):
        # Add labels
        display_panel.addLabel(f'CH{i}', row=0, col=i)

        # Add empty images
        vb = display_panel.addViewBox(row=1, col=i)
        vb.setAspectLocked()
        vb.setMouseEnabled(x=False, y=False)
        image = pg.ImageItem()
        vb.addItem(image)
        image.setImage(frame[i])
        
        # Add empty plots
        plot = display_panel.addPlot(row=2, col=i)
        plot.setMouseEnabled(x=False, y=False)
        plot.plot(np.random.random(50))
    
    display_panel.show()

    # Start Application
    sys.exit(app.exec_())

