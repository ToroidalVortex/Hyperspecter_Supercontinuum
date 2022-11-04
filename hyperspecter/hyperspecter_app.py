import os
import sys
import time
from ctypes import c_short
import traceback
import configparser
from queue import Queue
from threading import Thread

import numpy as np
import tifffile as tf
from PyQt5 import QtCore, QtWidgets, QtGui

from gui.gui import HyperspecterGUI
from microscope_controller import MicroscopeController
from motion_control.stage_controllers import Stage, stages
import ADIO
import utils


try:
    import mcc
    mcc_loaded = True
    print('MCC loaded properly')
except:
    mcc_loaded = False
    print('MCC failed to load')


class Hyperspecter:
    def __init__(self):
        ''' Hyperspecter application. 

        Usage:  hyperspecter = Hyperspecter()
        
        '''
        self.path = os.path.dirname(os.path.abspath(__file__))
        self.app = QtWidgets.QApplication(sys.argv)
        self.gui = HyperspecterGUI()
        self.settings = self.gui.getSettings()
        self.microscope = MicroscopeController()
        
        delay_name = 'DDS220'
        delay_serial_number = stages[delay_name]['SN']
        delay_hwtype = stages[delay_name]['HW']
        self.delay_stage = Stage(delay_serial_number, delay_hwtype, name=delay_name)
        
        self.config = {}
        self.config = utils.load_config(f'{self.path}/default_config.ini')
        # self.save_config('test.ini', self.config)
        
        
        '''
        Coefficients of the polynomials used for calibration.
        Use:
            np.polyval(self.delay_to_wavenumber, delays) 
            np.polyval(self.wavenumber_to_delay, wavenumbers)
        to obtain wavenumbers/delays from delays/wavenumbers. Delays in [mm], wavenumbers in [cm-1]
        '''
        self.delay_to_wavenumber = [870.38, -63210]
        self.wavenumber_to_delay = [0.0011, 72.37]
        
        self.image_data = []
        self.average_intensities = [[] for _ in range(self.microscope.number_of_channels)]
        # self.PMT_level = 0
        self.PMT_levels = [0,0,0,0]
        self.PMT_powered = False
        self.microscope_open = False
        self.pump_open = False
        self.stokes_open = False
        self.acquiring = False
        
        self.microscope_shutter = ADIO.DigitalOutput("Dev1/port0/line7")
        if mcc_loaded:
            self.MCC = mcc.MCCDev()
            self.pump = 1
            self.stokes = 2
            self.close_stokes_shutter()
            self.close_pump_shutter()
            self.close_microscope_shutter()

        self.setup_signals()
        sys.exit(self.app.exec_())
    
    def setup_signals(self):
        self.gui.ui.acquireButton.clicked.connect(self.acquire_toggle)
        self.gui.ui.pumpToggleButton.clicked.connect(self.toggle_pump_shutter)
        self.gui.ui.stokesToggleButton.clicked.connect(self.toggle_stokes_shutter)
        self.gui.signal.update.connect(self.update)
        self.gui.signal.close.connect(self.gui_closed)

        # PMT level control
        # self.gui.ui.PMTSlider0.valueChanged.connect(lambda: self.set_PMT_level(self.gui.ui.PMTSlider0.value(), 0))
        self.gui.ui.PMTSlider1.valueChanged.connect(lambda: self.set_PMT_level(self.gui.ui.PMTSlider1.value(), 1))
        self.gui.ui.PMTSlider2.valueChanged.connect(lambda: self.set_PMT_level(self.gui.ui.PMTSlider2.value(), 2))
        self.gui.ui.PMTSlider3.valueChanged.connect(lambda: self.set_PMT_level(self.gui.ui.PMTSlider3.value(), 3))

        # Delay stage position buttons
        self.gui.ui.delayStagePresetButton0.clicked.connect(lambda: self.delay_stage.move_abs(self.gui.ui.delayStagePresetWidget0.value()))
        self.gui.ui.delayStagePresetButton1.clicked.connect(lambda: self.delay_stage.move_abs(self.gui.ui.delayStagePresetWidget1.value()))
        self.gui.ui.delayStagePresetButton2.clicked.connect(lambda: self.delay_stage.move_abs(self.gui.ui.delayStagePresetWidget2.value()))

    def gui_closed(self):
        # Stop everything
        self.acquiring = False
        self.set_PMT_off()
        self.microscope.stop()
        if mcc_loaded:
            self.close_stokes_shutter()
            self.close_pump_shutter()
            self.close_microscope_shutter()

        # Quit application
        self.app.quit()

    def open_microscope_shutter(self):
        self.microscope_shutter.low()
        self.microscope_open = True
        self.gui.ui.microscopeStatus.setText('Microscope Shutter: Open')

    def close_microscope_shutter(self):
        self.microscope_shutter.high()
        self.microscope_open = False
        self.gui.ui.microscopeStatus.setText('Microscope Shutter: Closed')

    def open_pump_shutter(self):
        if mcc_loaded:
            self.MCC.set_digital_out(0, self.pump)
            self.pump_open = True
            self.gui.ui.pumpStatus.setText('Open')

    def close_pump_shutter(self):
        if mcc_loaded:
            self.MCC.set_digital_out(1, self.pump)
            self.pump_open = False
            self.gui.ui.pumpStatus.setText('Closed')

    def open_stokes_shutter(self):
        if mcc_loaded:
            self.MCC.set_digital_out(0, self.stokes)
            self.stokes_open = True
            self.gui.ui.stokesStatus.setText('Open')

    def close_stokes_shutter(self):
        if mcc_loaded:
            self.MCC.set_digital_out(1, self.stokes)
            self.stokes_open = False
            self.gui.ui.stokesStatus.setText('Closed')

    def toggle_pump_shutter(self):
        if self.pump_open:
            self.close_pump_shutter()
        else:
            self.open_pump_shutter()

    def toggle_stokes_shutter(self):
        if self.stokes_open:
            self.close_stokes_shutter()
        else:
            self.open_stokes_shutter()
    
    def set_PMT_level(self, value, channel):
        self.PMT_levels[channel] = value/100 # divide by correction factor equal to slider max value
        if self.PMT_powered and mcc_loaded:
            self.MCC.set_analog_out(self.PMT_levels[channel], channel)

    def set_PMT_on(self):
        # turn on PMTs
        if mcc_loaded:
            for channel, PMT_level in enumerate(self.PMT_levels):
                self.MCC.set_analog_out(PMT_level, channel)
            self.gui.ui.PMTStatus.setText('On')
            self.PMT_powered = True

    def set_PMT_off(self):
        # turn off PMTs
        if mcc_loaded:
            for channel, PMT_level in enumerate(self.PMT_levels):
                self.MCC.set_analog_out(0.0, channel)
            self.gui.ui.PMTStatus.setText('Off')
            self.PMT_powered = False

    def acquire_toggle(self):
        if not self.acquiring:
            self.acquire()
        elif self.acquiring:
            self.stop_acquire()

    def acquire(self):
        self.acquiring = True
        self.gui.ui.acquireButton.setText('Stop')
        if self.gui.display_panel is None:
                self.gui.createDisplayPanel()
        
        self.settings = self.gui.getSettings()
        self.microscope.update_settings(self.settings)

        if self.settings['save']:
            # Create save directory
            self.save_time = time.strftime("%Y_%m_%d_%H%M%S", time.gmtime())
            self.save_directory = f"{self.settings['directory']}/{self.settings['filename']}_{self.save_time}"
            os.mkdir(self.save_directory)
            
            # Save settings
            utils.save_settings(f'{self.save_directory}/settings.txt', self.settings)
        
        # Producer-consumer pattern for image processing
        image_q = Queue() # images are pushed as they are produced and pulled when they are ready to be processed
        consumer_thread = Thread(target=self.process_frames, args=(image_q,))
        consumer_thread.deamon = True
        consumer_thread.start()
        
        if not self.settings['simulate']:
            self.set_PMT_on()
            self.open_microscope_shutter()
            
        scan_mode = self.settings['scan mode']

        if scan_mode == 'Single Frame':
            print('single frame')
            producer_thread = Thread(target=self.acquire_frame, args=(image_q,))
            producer_thread.deamon = True
            producer_thread.start()
            
        elif scan_mode == 'Scan':
            print('scan')
            self.clear_data()
            producer_thread = Thread(target=self.acquire_scan, args=(image_q,))
            producer_thread.deamon = True
            producer_thread.start()
        
        elif scan_mode == 'Monitor':
            print('monitor')
            self.clear_data()
            producer_thread = Thread(target=self.microscope.get_frames, args=(image_q,))
            producer_thread.deamon = True
            producer_thread.start()

    def stop_acquire(self):
        self.microscope.stop()
        self.set_PMT_off()
        self.close_microscope_shutter()
        self.acquiring = False
        self.gui.ui.acquireButton.setText('Acquire')
        
    def process_frames(self, image_q):
        while self.acquiring:
            frame = image_q.get()

            if frame is None:
                self.stop_acquire()
                break

            # Storing image data for further use
            self.image_data.append(frame)
            for channel, array in enumerate(frame):
                self.average_intensities[channel].append(np.mean(array))

                # Save images
                if self.settings['save']:
                    levels = self.gui.display_panel.image_levels[channel]
                    array = utils.convert_to_16_bit(array, levels[0], levels[1])
                    tf.imwrite(f'{self.save_directory}/CH{channel}.tiff', array, append=True, bigtiff=True)
            
            # Display images
            self.gui.updateImages(frame)
            self.gui.updateIntensityPlots(self.average_intensities)

            


    def acquire_frame(self, image_q):
        ''' Acquires a single frame and adds it to the queue. '''
        frame = self.microscope.get_frame()
        image_q.put(frame)
        image_q.put(None) # add sentinel value
    
    def acquire_scan(self, image_q):
        ''' Scan method that adds each frame in a scan to the image_q queue. '''

        if self.settings['simulate']:
            
            for _ in range(10):
                frame = self.microscope.get_frame()
                image_q.put(frame)
        else:

            # Calculate scan points
            start = self.settings['scan start']
            end = self.settings['scan end']
            step = self.settings['step size']
            if end < start:
                step = -1*step
            
            wavenumbers = np.arange(start, end+step, step)
            delay_positions = np.polyval(self.wavenumber_to_delay, wavenumbers)

            ### initiate scan
            for position in delay_positions:
                try:
                    
                    ### set delay stage position
                    self.delay_stage.move_abs(position)

                    frame = self.microscope.get_frame()
                    image_q.put(frame)

                except:
                    break

        image_q.put(None) # add sentinel value
    
    def monitor(self, image_q):
        ''' Scan method that continuously adds frames to the image_q queue. '''
        while self.acquiring:
            try:
                frame = self.microscope.get_frame()
                image_q.put(frame)
            except KeyboardInterrupt:
                break
        
        image_q.put(None) # add sentinel value

    def clear_data(self):
        self.image_data = []
        self.average_intensities = [[] for _ in range(self.microscope.number_of_channels)]
    
    def update(self):
        ''' Update config based on gui settings. '''
        # Update settings
        self.settings = self.gui.getSettings()

        # Update estimated scan times
        scan_time = utils.estimate_imaging_time(
            self.settings['scan start'],
            self.settings['scan end'],
            self.settings['step size'],
            self.settings['line dwell time'] * self.settings['image resolution'] / 1000
        )
        self.gui.ui.estimatedScanTimeLabel.setText(f'Estimated Scan Time: {scan_time} seconds')

        scan_time = utils.estimate_imaging_time(
            self.settings['polarization scan start'],
            self.settings['polarization scan end'],
            self.settings['polarization step size'],
            self.settings['line dwell time'] * self.settings['image resolution'] / 1000
        )
        self.gui.ui.estimatedPolarizationScanTimeLabel.setText(f'Estimated Scan Time: {scan_time} seconds')

        # Update current delay stage position
        delay_position = self.delay_stage.get_position()
        wavenumber = np.polyval(self.delay_to_wavenumber, delay_position)
        self.gui.ui.delayStagePosition.setText(f'{delay_position:.3f} mm ({wavenumber:.0f} cm-1)')

        # Update preset values
        self.gui.ui.delayStagePreset0.setText(f'{np.polyval(self.delay_to_wavenumber, self.gui.ui.delayStagePresetWidget0.value()):.0f} cm-1')
        self.gui.ui.delayStagePreset1.setText(f'{np.polyval(self.delay_to_wavenumber, self.gui.ui.delayStagePresetWidget1.value()):.0f} cm-1')
        self.gui.ui.delayStagePreset2.setText(f'{np.polyval(self.delay_to_wavenumber, self.gui.ui.delayStagePresetWidget2.value()):.0f} cm-1')

def handle_exception(exc_type, exc_value, exc_traceback):
        ''' Prints error that crashed application. '''
        print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        sys.exit(1)

def main():
    sys.excepthook = handle_exception
    
    ############ Code required for custom application icon in taskbar ############
    import ctypes
    import os
    myappid = u'hyperspecter'  # arbitrary string
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    ##############################################################################
    
    hyperspecter = Hyperspecter()

if __name__ == '__main__':
    main()