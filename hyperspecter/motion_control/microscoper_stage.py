import time
from threading import Thread

from PyAPT import APTMotor

class baseDevice(object):
    def __init__(self):
        self.motorLoaded = False
        self.stageUpdate = False
        self.presetWidgets = [None for i in range(999)]
        self.movePresetFunction = [None for i in range(999)]
        self.currentPosition = None
        self.simulating = False


    def baseDeviceHasNumbers(self,inputString):
        return any(char.isdigit() for char in inputString)

    def baseDeviceGetNumber(self,inputString):
        for char in inputString:
            if char.isdigit():
                return int(char)

    def baseDeviceDefMovePresetFunction(self,n):
        def MoveFunction():
            pos = self.presetWidgets[n].value()
            # pos = self.presetWidgets[n].value()
            # pos = eval("self.presetWidget%s.value()"%n)
            if self.motorLoaded:
                # self.threadThis(self.verifyMoveStatus(self.MoveAbs(pos)))
                self.MoveAbs(pos)
            else:
                self.currentPosition = pos
        # exec("self.MovePreset%s = MoveFunction"%n)
        exec("self.movePresetFunction[%i] = MoveFunction"%n)
        return MoveFunction

    def setWidgets(self,widgets):
        for widget in widgets:
            widgetName = widget.objectName().lower()
            if 'start' in widgetName :  self.StartPos = widget
            if 'end' in widgetName : self.EndPos = widget
            if ('move' in widgetName) or ('offset' in widgetName) : self.MoveDef = widget
            if 'current' and 'position' in widgetName : self.currentStagePositionText = widget
            if 'preset' in widgetName :
                if self.baseDeviceHasNumbers(widgetName) :
                    n = self.baseDeviceGetNumber(widgetName)
                    self.presetWidgets[n] = widget
                    # exec("self.presetWidget%s = widget"%n)
                    self.baseDeviceDefMovePresetFunction(n)
                    # self.movePresetFunction[n] = self.baseDeviceDefMovePresetFunction(n)
                    ## exec("self.MovePreset%s = self.__defMovePresetFunction(n)"%n)
            print('%s Stage widget connected.'%widget.objectName())

    def verifyMoveStatus(self,function,*args):
        def changeBool(*args):
            self.positionStageOK = False
            try : function(*args)
            except : function
            self.positionStageOK = True
        return changeBool

    def threadThis(self, function, args=(), name=None):
        thread = Thread(target=function, args=args, name=name)
        thread.daemon = False
        thread.start()

    def getPositionThread(self):
        if self.stageUpdate:
            print('Get position thread started...')
        while self.stageUpdate:
            time.sleep(0.05)
            self.currentPosition = self.GetPos()

    def simulateStageMotion(self):
        dt = 0.1
        if self.moveType == 'Continuous':
            while (self.currentPosition < self.EndPos.value()) & (self.simulating):
                time.sleep(dt)
                self.currentPosition += (self.MoveDef.value())*dt

    def GetPos(self):
        pass

    def MoveAbs(self,pos=None):
        pass

    def MoveRel(self,pos=None):
        pass

class LStage(baseDevice):

    def __init__(self,serialNumber=94839332,hwtype=31,verbose=True,widgets=None,name=''):
        baseDevice.__init__(self)
        self.serial = serialNumber
        self.motorLoaded = False
        self.name = name
        try :
            self.motor = APTMotor(serialNumber,HWTYPE=hwtype,verbose=verbose)
            self.motorLoaded = True
            self.motor.aptdll.EnableEventDlg(False) ## Added 2017-10-03 : Prevents appearing of APT event dialog which causes 64 bit systems to crash
            self.currentPosition = self.GetPos()
            print("Stage %s loaded currently at %.4f."%(serialNumber,self.currentPosition))
        except :
            self.motorLoaded = False
            self.currentPosition = 100
            print("Stage not loaded, simulating stage at position %.4f"%(self.currentPosition))

        self.SetMoveType()
        if widgets is not None :
            self.setWidgets(widgets)
        self.stageUpdate = True
        self.threadThis(self.getPositionThread, name='getPositionThread')
        self.positionStageOK = True
        self.targetPosition = self.currentPosition
        self.endScanPosition = None


    def GetPos(self):
        if self.motorLoaded :
            return self.motor.getPos()
        else :
            return self.currentPosition

    def MoveAbs(self,absPosition=110, moveVel=10):
        def Move():
            self.motor.mcAbs(absPosition, moveVel)
        if self.motorLoaded :
            self.threadThis(Move)
        else :
            self.currentPosition = absPosition

    def MoveRel(self,relative_distance,velocity=10):
        def Move():
            self.motor.mcRel(relative_distance, moveVel=velocity)
        if self.motorLoaded :
            self.threadThis(Move)
        else :
            self.currentPosition += relative_distance

    def MoveDir(self,direction='Up',execute=False,velocity=10):
        direction = direction.lower()
        def moveUp():
            self.motor.mcAbs(self.currentPosition + self.MoveDef.value(), moveVel=velocity)
        def moveDown():
            self.motor.mcAbs(self.currentPosition - self.MoveDef.value(), moveVel=velocity)

        if execute:
            if self.motorLoaded :
                if ('up' in direction) or ('right' in direction):
                    self.threadThis(moveUp)
                if ('down' in direction) or ('left' in direction):
                    self.threadThis(moveDown)
            else :
                if ('up' in direction) or ('right' in direction):
                    self.currentPosition = self.currentPosition + self.MoveDef.value()
                if ('down' in direction) or ('left' in direction):
                    self.currentPosition = self.currentPosition - self.MoveDef.value()

    def SetMoveType(self,moveType='None'):
        self.moveType = moveType

    def SetStartPosition(self):
        self.Stop()
        time.sleep(0.1)
        if self.motorLoaded:
            if ('none' not in self.moveType.lower()):
                self.threadThis(self.MoveAbs(float(self.StartPos.value())))
                while abs(self.currentPosition - float(self.StartPos.value())) > 1e-5 :
                    time.sleep(0.1)
        else :
            if ('none' not in self.moveType.lower()):
                self.currentPosition = float(self.StartPos.value())
                self.positionStageOK = True

        self.endScanPosition = self.EndPos.value()

        # self.signal.setStartPositionDone.emit()

    def SetStartScan(self):
        if self.motorLoaded:
            if 'continuous' in self.moveType.lower():
                self.threadThis(self.MoveAbs(self.EndPos.value(),self.MoveDef.value()))
            if 'discrete' in self.moveType.lower():
                self.threadThis(self.MoveAbs(self.currentPosition + self.MoveDef.value()))
        else :
            self.simulating = True
            self.threadThis(self.simulateStageMotion)
        while not self.positionStageOK :
            time.sleep(0.1)

    def SetSpeed(self,maxVel=10,minVel=0,acc=10):
        if self.motorLoaded :
            self.motor.setVelocityParameters(minVel, acc, maxVel)

    def Stop(self):
        if self.motorLoaded :
            try : self.motor.aptdll.MOT_StopImmediate(self.motor.SerialNum)
            except : self.motor.aptdll.MOT_StopProfiled(self.motor.SerialNum)
        else :
            # print("Stopping stage %s"%(self.name))
            self.simulating = False

    def Clear(self):
        try : self.motor.aptdll.cleanUpAPT()
        except : pass



if __name__ == '__main__':
    delay_stage = LStage()
    print(f'Position: {delay_stage.GetPos()}')