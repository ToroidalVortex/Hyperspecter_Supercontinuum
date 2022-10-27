import time

from .PyAPT import APTMotor

# Check "APT User" program for details about connected devices.
stages = {

    'DDS220' : {
        'SN' : 94839332,
        'HW' : 31
    },

    'MLS203 Y Axis' : {
        'SN' : 94839333,
        'HW' : 31
    },
    
    'MLS203 X Axis' : {
        'SN' : 94839334,
        'HW' : 31
    }
}

class Stage:
    def __init__(self, serial_number, hwtype=31, verbose=False, name='', simulate=False):
        ''' Base class applicable for all devices that can be controlled with the PyAPT framework.'''
        self.serial_number = serial_number
        self.hwtype = hwtype
        self.verbose = verbose
        self.name = name
        self.simulating = simulate
        try :
            self.motor = APTMotor(serial_number, hwtype, verbose)
            self.motor_loaded = True
            self.motor.aptdll.EnableEventDlg(False) ## Added 2017-10-03 : Prevents appearing of APT event dialog which causes 64 bit systems to crash
            self.position = self.get_position()
        except :
            self.motor_loaded = False
            self.position = 100
            if self.verbose: print('Stage not loaded.')
        
        self.positionStageOK = True
        self.target_position = self.position
        self.endScanPosition = None

    def __del__(self):
        if self.motor_loaded:
            try: self.motor.cleanUpAPT()
            except: f'Resource (S/N:{self.serial_number}) not released properly.'

    def simulate_motion(self, distance, velocity=10):
        dt = 0.1
        if self.moveType == 'Continuous':
            while (self.position < self.EndPos.value()) & (self.simulating):
                time.sleep(dt)
                self.position += (self.MoveDef.value())*dt

    def get_position(self):
        if self.motor_loaded:
            self.position = self.motor.getPos()
            return self.position
        else:
            return self.position

    def move_abs(self, position, velocity=10):
        if self.motor_loaded:
            self.motor.mcAbs(position, velocity)
        else:
            self.position = position

    def move_rel(self, distance, velocity=10):
        if self.motor_loaded:
            self.motor.mcRel(distance, velocity)
        else:
            self.position += distance

if __name__ == '__main__':
    
    name = 'DDS220'
    serial_number = stages[name]['SN']
    hwtype = stages[name]['HW']
    
    delay_stage = Stage(serial_number, hwtype, name=name, verbose=False)
    
    print(f'Position: {delay_stage.get_position()}')
    
    delay_stage.move_abs(110)
    
    print(f'Position: {delay_stage.get_position()}')