import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui


pg.setConfigOptions(imageAxisOrder='row-major')


class ImageItem(pg.ImageItem):
    ''' ImageItem with modified mouse click event which prints and stores the location of the cursor click position. '''
    def __init__(self):
        super().__init__()
        self.click_position = None

    def mouseClickEvent(self, event):
        self.click_position = int(event.pos().x()), int(event.pos().y()) # returns clicked pixel's location as integer coordinates
        print(self.click_position)  # TODO: replace with sprite at click position
        # return self.click_position


# TODO : show intensity number and more basic qt label based on autoalign
class DisplayPanel(pg.GraphicsLayoutWidget):
    
    class Signal(QtCore.QObject):
        update = QtCore.pyqtSignal()
        close  = QtCore.pyqtSignal()
        
    __title  = "Hyperspecter - Display Panel 2022"

    def __init__(self, number_of_channels, parent=None):
        ''' DisplayPanel displays a panel of microscope images where each column represents a different input channel.
            DisplayPanel inherits from the convenience class GraphicsLayoutWidget which combines a GraphicsView and GraphicsLayout.

            Attributes : 
                number_of_channels (int): the number of channels to be displayed
                simulate (bool): simulate data as noise
                parent (object): the object which invoked the display panel
    '''
        super().__init__()
        self.number_of_channels = number_of_channels
        self.parent = parent
        
        self.images = []
        self.plots = []
        self.image_levels = []
        self.default_image_minimum = 0
        self.default_image_maximum = 1
        self.click_position = None
        self.signal = self.Signal()

        self.image_data = None

        self.setupUI()
        self.setupSignals()
        self.activateWindow()
        self.show()

    def setupUI(self):
        self.setWindowTitle(self.__title)
        self.resize(400*self.number_of_channels, 525)
        layout = self.ci.layout # layout is an instance of QGraphicsGridLayout
        layout.setRowStretchFactor(1, 10) # stretches out the image row so that the images appear larger
        layout.setRowStretchFactor(2,  1) # maintains size of the plots

        for i in range(self.number_of_channels):
            # Add labels
            self.addLabel(f'CH{i}', row=0, col=i)

            # Add empty images
            vb = self.addViewBox(row=1, col=i)
            vb.setAspectLocked()
            vb.setMouseEnabled(x=False, y=False)
            image = ImageItem()
            vb.addItem(image)
            self.images.append(image)
            self.image_levels.append((self.default_image_minimum,self.default_image_maximum))
            
            # Add empty plots
            plot = self.addPlot(row=2, col=i)
            plot.setMouseEnabled(x=False, y=False)
            self.plots.append(plot.plot()) # Initializes plot so it can be updated later

    def setupSignals(self):
        ''' Connects signals to slots. '''
        pass

    def setImage(self, image_data, image_minimums=None, image_maximums=None):
        ''' Sets the image.

            INPUT :
                image_data = 3D array containing the image data for each channel [channel,y,x]
                image_minimums = 2D array containing minimum image intensities to be displayed for image levelling [channel, minimums]
                image_maximums = 2D array containing maximum image intensities to be displayed for image levelling [channel, maximums]
                
        '''
        assert len(image_data) == self.number_of_channels, f'image_data must contain {self.number_of_channels} channels. Create a new display to update number of channels.'

        if not image_minimums:
            image_minimums = [levels[0] for levels in self.image_levels]
        if not image_maximums:
            image_maximums = [levels[1] for levels in self.image_levels]

        for channel in range(self.number_of_channels):
            self.images[channel].setImage(image_data[channel], levels=[image_minimums[channel],image_maximums[channel]])
            # self.images[channel].setImage(image_data[channel], autoLevels=True)

    def setIntensityPlot(self, intensity_data, wavenumbers=None):
        ''' Sets the average intensity plot. 

            INPUT :
                intensity_data = 2D array containing the average image intensity for any previous images having type [channel,intensity]
                wavenumbers = 2D array containing the wavenumbers to associate with each value in intensity_data having type [channel,wavenumber]
        '''
        assert len(intensity_data) == self.number_of_channels, f'intensity_data must contain {self.number_of_channels} channels. Create a new display to update number of channels.'

        for channel in range(self.number_of_channels):
            if wavenumbers:
                self.plots[channel].setData(y=intensity_data[channel], x=wavenumbers)
            else:
                self.plots[channel].setData(intensity_data[channel])

    # def update(self, image_data, image_maximums=None, image_minimums=None, intensity_data=None, wavenumbers=None):
    #     ''' Sets the image and intensity plot to 

    #         INPUT :
    #             image_data = 3D array containing the image data for each channel having type [channel,y,x]
    #             image_maximums = 1D array containing maximum image intensities to be displayed for image levelling
    #             image_minimums = 1D array containing minimum image intensities to be displayed for image levelling
    #             intensity_data = 2D array containing the average image intensity for any previous images having type [channel,intensity]
    #             wavenumbers = 2D array containing the wavenumbers to associate with each value in intensity_data having type [channel,wavenumber]
    #     '''
    #     self.set_image(image_data, image_minimums, image_maximums)
    #     self.set_intensity_plot(intensity_data, wavenumbers)

    def setDefaultImageLevels(self, minimum=0, maximum=1):
        self.default_image_minimum = minimum
        self.default_image_maximum = maximum

    def setLevels(self, image_levels):
        ''' Set image levels.
        
        Inputs:
            levels: list containing levels=(min, max) for each image. Dimension: [channel, levels]
        
        '''
        self.image_levels = image_levels
        for i,image in enumerate(self.images):
            image.setLevels(image_levels[i])

    def autoLevel(self):
        for channel, image in enumerate(self.images):
            try:
                levels = image.quickMinMax(targetSize=10000)
                self.image_levels[channel] = levels
                image.setLevels(levels)
                print(f'Image {channel} autolevels: {levels}')
            except:
                pass
            

    def closeEvent(self, event):
        self.signal.close.emit()
        event.accept()


class TestDisplayPanel(pg.GraphicsLayoutWidget):
    def __init__(self):
        super().__init__()
        
        self.image_data = []
        self.number_of_channels = 2
        self.images = []
        self.plots = []
        
        self.initUI()
        self.update_data()
        
        self.activateWindow()
        self.show()

    def initUI(self):

        self.setWindowTitle('Test Canvas')

        self.layout = self.ci.layout # layout is an instance of QGraphicsGridLayout
        self.layout.setRowStretchFactor(1, 10) # stretches out the image row so that the images appear larger
        self.layout.setRowStretchFactor(2, 1)

        self.resize(400*self.number_of_channels, 525)

        for channel in range(self.number_of_channels):
            self.layout.setColumnStretchFactor(channel, 1)

            self.addLabel(f'CH{channel}', row=0, col=channel, colspan=1)

            vb = self.addViewBox(row=1, col=channel, colspan=1)
            vb.setAspectLocked()
            vb.setMouseEnabled(x=False, y=False)
            image = ImageItem()
            vb.addItem(image)
            self.images.append(image)
            

            plot = self.addPlot(row=2, col=channel, colspan=1)
            plot.setMouseEnabled(x=False, y=False)
            self.plots.append(plot.plot()) # Initializes plot so it can be updated later

    def update_data(self):
        for channel in range(self.number_of_channels):
            # Plot random data
            self.images[channel].setImage(np.random.randn(50, 50))
            self.plots[channel].setData(np.random.random(50)*2000)
        
        
        


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    # test_display_panel = TestDisplayPanel()
    display_panel = DisplayPanel(2)
    display_panel.setImage(np.random.randn(2,50,50))
    display_panel.setIntensityPlot(np.random.randn(2,100))
    app.exec_()
