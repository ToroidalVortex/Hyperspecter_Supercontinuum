from PyQt5 import QtCore, QtWidgets, QtGui

from .hyperspecter_ui import Ui_Hyperspecter
from .display import DisplayPanel


class HyperspecterGUI(QtWidgets.QMainWindow):

    class Signal(QtCore.QObject):
        acquire = QtCore.pyqtSignal()
        stop = QtCore.pyqtSignal()
        update = QtCore.pyqtSignal()
        close = QtCore.pyqtSignal()
        generate_delay_stage_positions = QtCore.pyqtSignal()

    def __init__(self, channels=4):
        super().__init__()
        self.number_of_channels = channels
        self.signal = self.Signal()
        self.display_panel = DisplayPanel(self.number_of_channels, parent=self)
        self.acquiring = False
        self.setupUI()
        self.setupSignals()
        
    def setupUI(self):
        self.ui = Ui_Hyperspecter()
        self.ui.setupUi(self)
        self.setWindowTitle("Hyperspecter")
        self.setWindowIcon(QtGui.QIcon('hyperspecter/gui/lens_of_truth.png'))
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(0, screen.height() - size.height() - 100)
        self.activateWindow()
        self.show()

    def setupSignals(self):
        self.ui.actionQuit.triggered.connect(self.close)
        self.ui.directoryBrowseButton.clicked.connect(lambda: self.ui.directoryText.setText(QtWidgets.QFileDialog.getExistingDirectory()))
        self.display_panel.signal.close.connect(self.displayClosed)
        self.ui.autoLevelButton.clicked.connect(self.display_panel.autoLevel)

        # Sets text above sliders to display value of slider
        self.ui.PMTSlider0.valueChanged.connect(lambda: self.ui.PMTLevel0.setText(str(self.ui.PMTSlider0.value())))
        self.ui.PMTSlider1.valueChanged.connect(lambda: self.ui.PMTLevel1.setText(str(self.ui.PMTSlider1.value())))
        self.ui.PMTSlider2.valueChanged.connect(lambda: self.ui.PMTLevel2.setText(str(self.ui.PMTSlider2.value())))
        self.ui.PMTSlider3.valueChanged.connect(lambda: self.ui.PMTLevel3.setText(str(self.ui.PMTSlider3.value())))

        # Update timer to periodically emit update signal
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(False)
        self.timer.setInterval(500) # in milliseconds
        self.timer.timeout.connect(lambda: self.signal.update.emit())
        self.timer.start()

    def displayClosed(self):
        self.display_panel = None
        
    def createDisplayPanel(self):
        self.display_panel = DisplayPanel(self.number_of_channels, parent=self)

    def updateImages(self, image_data, levels=None):
        self.display_panel.setImage(image_data, levels)

    def updateIntensityPlots(self, intensity_data, wavenumbers=None):
        self.display_panel.setIntensityPlot(intensity_data, wavenumbers)
    
    def getSettings(self):
        settings = {}
        settings['scan mode'] = self.ui.scanModeWidget.currentText()
        settings['filename'] = self.ui.filenameText.text()
        settings['directory'] = self.ui.directoryText.text()
        settings['save'] = self.ui.saveCheckBox.isChecked()
        settings['simulate'] = self.ui.simulateCheckBox.isChecked()
        settings['zoom'] = int(self.ui.zoomWidget.value())
        settings['line dwell time'] = int(self.ui.lineDwellTimeWidget.value())
        settings['image resolution'] = int(self.ui.resolutionWidget.value())
        settings['flyback'] = int(self.ui.flybackWidget.value())
        settings['fill fraction'] = self.ui.fillFractionWidget.value()
        settings['galvo y-axis offset'] = self.ui.galvoOffsetWidget.value()
        settings['scan delay'] = self.ui.scanDelayWidget.value()
        settings['scan pattern'] = self.ui.scanPatternWidget.currentText()
        settings['scan start'] = self.ui.scanStartWidget.value()
        settings['scan end'] = self.ui.scanEndWidget.value()
        settings['step size'] = self.ui.stepSizeWidget.value()
        settings['pump power'] = self.ui.pumpPowerWidget.value()
        settings['stokes power'] = self.ui.stokesPowerWidget.value()
        settings['image levels'] = f'{self.display_panel.image_levels}'
        settings['delay presets'] = (self.ui.delayStagePresetWidget0.value(),self.ui.delayStagePresetWidget1.value(),self.ui.delayStagePresetWidget2.value())
        settings['calibration'] = (self.ui.calibrationWidget0.value(),self.ui.calibrationWidget1.value(),self.ui.calibrationWidget2.value())
        settings['polarization scan start'] = self.ui.polarizationScanStartWidget.value()
        settings['polarization scan end'] = self.ui.polarizationScanEndWidget.value()
        settings['polarization step size'] = self.ui.polarizationScanStepSizeWidget.value()
        return settings

    def setSettings(self, settings):
        self.ui.filenameText.setText(settings['filename'])
        self.ui.directoryText.setText(settings['directory'])
        self.ui.zoomWidget.setValue(int(settings['zoom']))
        self.ui.resolutionWidget.setValue(int(settings['resolution']))
        self.ui.lineDwellTimeWidget.setValue(int(settings['line dwell time']))
        self.ui.fillFractionWidget.setValue(float(settings['fill fraction']))
        self.ui.calibrationText.setText(settings['calibration file'])

    def closeEvent(self, event):
        # close all windows
        self.signal.close.emit()
        event.accept()

if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    gui = HyperspecterGUI()
    exit(app.exec_())