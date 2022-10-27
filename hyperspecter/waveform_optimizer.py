import numpy as np
import pyqtgraph as pg
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from PyQt5 import QtWidgets, QtCore, QtGui

import ADIO
import utils


class WaveformOptimizer:

    __title  = "Waveform Optimizer 2022"

    def __init__(self, parent=None):
        self.window = pg.GraphicsLayoutWidget(parent=parent)
        self.window.setWindowTitle(self.__title)
        # self.layout = self.window.ci.layout # layout is an instance of QGraphicsGridLayout

        self.setup_plots()
        self.get_actual_waveform()
        self.plot_data()
        # self.get_delay()
        self.window.activateWindow()
        self.window.show()
        
        

    def setup_plots(self):
        self.window.addLabel('X', row=0, col=0)
        self.window.addLabel('Y', row=1, col=0)

        x_plot = self.window.addPlot(row=0, col=1)
        x_plot.setMouseEnabled(x=False, y=False)
        x_plot.addLegend()
        self.x_control_plot = x_plot.plot(pen='r', name="control")
        self.x_actual_plot = x_plot.plot(pen='g', name="actual")

        y_plot = self.window.addPlot(row=1, col=1)
        y_plot.setMouseEnabled(x=False, y=False)
        y_plot.addLegend()
        self.y_control_plot = y_plot.plot(pen='r', name="control")
        self.y_actual_plot = y_plot.plot(pen='g', name="actual")
        

    def configure_ADIO(self, mode='finite'):

        self.resolution = 256 # px
        self.line_dwell_time = 5 # ms
        self.number_of_lines = 5 # how many scans to consider
        
        # Galvo mirror scan setup
        amplitude = 3.0
        x_offset  = 0.0
        y_offset  = 0.0
        offset = (x_offset, y_offset)
        
        # x_scan, y_scan, self.samples_per_line, self.throwaway, self.flyback, self.padding = utils.generate_sawtooth_scan(
        #     resolution=(self.resolution,self.number_of_lines),
        #     amplitude=amplitude,
        #     offset=offset,
        #     fill_fraction=0.6,
        #     flyback=int(0.2*self.resolution),
        #     padding=(100,0)
        # )

        x_scan, y_scan, self.samples_per_line, self.throwaway, self.padding = utils.generate_bidirectional_scan(
            resolution=(self.resolution,self.number_of_lines),
            amplitude=amplitude,
            offset=offset,
            fill_fraction=1.0,
            padding=(100,0)
        )

        # x_scan = x_amplitude * utils.triangle(self.resolution, 1, self.number_of_lines) + x_offset
        # y_scan = y_amplitude * utils.sawtooth(self.resolution, self.number_of_lines, 1) + y_offset
        
        write_data = np.concatenate((x_scan, y_scan))

        self.x_control = x_scan
        self.y_control = y_scan

        self.clock_rate = round(1000*self.samples_per_line/self.line_dwell_time)
        mode = 'finite'
        self.samples_per_channel = self.samples_per_line * self.number_of_lines + sum(self.padding)
        self.read_samples = self.samples_per_channel
        
        self.input = ADIO.AnalogInput(
            channel_name='Dev1/ai2:3',
            clock_rate=self.clock_rate,
            mode=mode,
            samples_per_channel=self.samples_per_channel,
            offset=0
        )

        self.output = ADIO.AnalogOutput(
            channel_name='Dev1/ao0:1',
            clock_rate=self.clock_rate,
            mode=mode,
            samples_per_channel=self.samples_per_channel,
            source='/Dev1/ai/SampleClock',
            trigger='/Dev1/ai/StartTrigger'
        )

        # self.number_of_channels = self.pmts.number_of_channels
        self.output.write(write_data)
        

    def get_actual_waveform(self):
        self.configure_ADIO()
        data = self.input.read(samples_per_channel=self.read_samples)
        self.input.wait()
        self.output.stop()
        self.output.clear()
        self.input.stop()
        self.input.clear()
        
        self.x_actual = data[1] * 1.6
        self.y_actual = data[0] * 1.6

    def plot_data(self):
        self.x_control_plot.setData(self.x_control)
        self.x_actual_plot.setData(self.x_actual)
        self.y_control_plot.setData(self.y_control)
        self.y_actual_plot.setData(self.y_actual)

    def get_delay(self):
        # Get first peak of control waveform
        control_peaks, _ = find_peaks(self.x_control, prominence=1)
        control_peak = control_peaks[0]

        # Get first peak of actual waveform
        actual_peaks, _ = find_peaks(self.x_actual, prominence=1)
        actual_peak = actual_peaks[0]

        # Calculate difference
        delay = actual_peak - control_peak
        print(f'Delay: {delay} samples')

        # Plot to verify peak locations
        plt.figure()
        plt.plot(self.x_control, 'r-')
        plt.plot(control_peak, self.x_control[control_peak], 'rx')
        plt.plot(self.x_actual, 'g-')
        plt.plot(actual_peak, self.x_actual[actual_peak], 'gx')
        plt.show()

        return delay

        

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    wo = WaveformOptimizer()
    app.exec_()