#!/bin/env python3
# Copyright (C) 2019 Nils VAN ZUIJLEN

from datetime import datetime, timedelta
import math
import subprocess

from ola.DMXConstants import DMX_UNIVERSE_SIZE
from RPi import GPIO

import liquidcrystal_i2c

UP_BUTTON = 26
DOWN_BUTTON = 6
OK_BUTTON = 19
BACK_BUTTON = 13

class fakepanel:
    def __init__(self):
        self.threadSafeSchedule = lambda a, b: None
        self.start_universe = 0
        self.start_channel = 1
        self.setOnOff = lambda a: None
    def setAddress(self, universe=None, channel=None):
        pass
    def run(self):
        input()


def get_ip_address():
    return str(subprocess.check_output(["hostname", "-i"])).split('\n')[0]

class ParentalError(ValueError):
    pass

class Screen:
    def __init__(self, scr_id, showname, manager):
        self.scr_id = scr_id
        self.showname = showname
        self.manager = manager

        self.children = []
        self.parent = None

        self.selectedChild = None
        self.callback = lambda a: None

    def addChild(self, child):
        if not child in self.children:
            self.children.append(child)
        child.setParent(self)
        if self.selectedChild is None:
            self.selectedChild = 0

    def removeChild(self, child):
        try:
            self.children.remove(child)
        except ValueError:
            pass
        else:
            child.unsetParent()

        if len(self.children) == 0:
            self.selectedChild = None
        else:
            self.selectedChild = 0

    def setParent(self, parent):
        self.parent = parent

    def unsetParent(self):
        self.parent = None

    def gotoSelectedChild(self):
        try:
            self.manager.current = self.children[self.selectedChild]
        except IndexError:
            print("E: gotoSelectedChild called on screen " + self.scr_id + " with selectedChild not being in correct range")
        except TypeError:
            print("E: gotoSelectedChild called on screen " + self.scr_id + " with selectedChild being None")
    def gotoParent(self):
        if self.parent is not None:
            self.manager.current = self.parent
        else:
            print("E: gotoParent called on screen " + self.scr_id + " with parent being None")

    def incrementSelectedChild(self):
        self.selectedChild += 1
        if self.selectedChild > len(self.children) - 1:
            self.selectedChild = 0
    def decrementSelectedChild(self):
        self.selectedChild -= 1
        if self.selectedChild < 0:
            self.selectedChild = len(self.children) - 1

    def computeDisplay(self):
        self.first_line = self.showname[:20]
        self.second_line = ''

    def setCallback(self, callback):
        self.callback = callback

    def onOK(self):
        pass
    def onBack(self):
        pass
    def onUp(self):
        pass
    def onDown(self):
        pass

class StartScreen(Screen):
    """A Start screen

    It can not be a child of any other screen, raises ParentalError if you try to do it anyway
    """
    def __init__(self, scr_id, showname, manager, text):
        super(StartScreen, self).__init__(scr_id, showname, manager)
        self.text = text

    def setParent(self):
        raise ParentalError("Assigning a Start screen as child of someone")

    def onOK(self):
        self.gotoSelectedChild()

    def computeDisplay(self):
        super(StartScreen, self).computeDisplay()
        self.second_line = self.text[:20]

class EndScreen(Screen):
    """An End screen

    It can not have childrens, if you try to assign some anyway, it will rise a ParentalError
    """
    def addChild(self, child):
        raise ParentalError('EndScreen cannot have any children')
    
    def onOK(self):
        self.gotoParent()
    def onBack(self):
        self.gotoParent()

class MenuScreen(Screen):
    """A Menu Screen"""
    def onOK(self):
        self.gotoSelectedChild()
    def onBack(self):
        self.gotoParent()

    def onUp(self):
        self.incrementSelectedChild()
    def onDown(self):
        self.decrementSelectedChild()

    def computeDisplay(self):
        super(MenuScreen, self).computeDisplay()
        self.second_line = '\x00' + self.children[self.selectedChild].showname[:19]

class ValueScreen(EndScreen):
    """Enables the user to set a value

    `initial` is the default value taken by this screen
    `minimum` and `maximum` are the allowed boundaries for the value
    """
    def __init__(self, scr_id, showname, manager, initial, minimum, maximum):
        super(ValueScreen, self).__init__(scr_id, showname, manager)
        
        self.value = initial
        self.old_value = initial
        self.minimum = minimum
        self.maximum = maximum

    def onOK(self):
        self.callback(self.value)
        super(ValueScreen, self).onOK()
        self.old_value = self.value

    def onBack(self):
        self.value = self.old_value
        super(ValueScreen, self).onBack()

    def onUp(self):
        if self.value == self.maximum:
            if math.isfinite(self.minimum):
                self.value = self.minimum
        else:
            self.value += 1
    def onDown(self):
        if self.value == self.minimum:
            if math.isfinite(self.maximum):
                self.value = self.maximum
        else:
            self.value -= 1

    def computeDisplay(self):
        super(ValueScreen, self).computeDisplay()
        self.second_line = '\x00' + str(self.value)[:19]

class ToggleScreen(EndScreen):
    """A Toggle button screen"""
    def __init__(self, scr_id, showname, manager):
        super(ToggleScreen, self).__init__(scr_id, showname, manager)

        self.state = False

    def onOK(self):
        self.state = not self.state

        self.callback(self.state)

    def onUp(self):
        last = self.state
        self.state = True
        if last != self.state:
            self.callback(self.state)
    def onDown(self):
        last = self.state
        self.state = False
        if last != self.state:
            self.callback(self.state)

    def computeDisplay(self):
        super(ToggleScreen, self).computeDisplay()
        if self.state:
            self.second_line = '\x00Allume'
        else:
            self.second_line = '\x00Eteint'

class InformationScreen(EndScreen):
    """Shows a value"""
    def __init__(self, scr_id, showname, manager, value):
        super(InformationScreen, self).__init__(scr_id, showname, manager)
        self.value = value

    def computeDisplay(self):
        super(InformationScreen, self).computeDisplay()
        self.second_line = self.value[:20]

class ScreenManager:
    """Manages Screens
    
    Creates the arborescence needed for a LedPanel and manages it

    Please call GPIO.cleanup() once you have finished.
    """
    def __init__(self, panel):
        self.panel = panel

        home = StartScreen('HOME', 'LedPanel 289', self,
            'Made by N.V.Zuijlen')
        main_menu = MenuScreen('MAIN_MENU', 'Menu', self)
        manual_menu = MenuScreen('MANUAL_MENU', 'Manuel', self)
        universe_selector = ValueScreen('UNIVERSE_SELECTOR', 'Choix Univers',
            self, self.panel.start_universe, 0, math.inf)
        channel_selector = ValueScreen('CHANNEL_SELECTOR', 'Choix Adresse',
            self, self.panel.start_channel, 1, DMX_UNIVERSE_SIZE)
        blackout = ToggleScreen('BLACKOUT', 'Blackout', self)
        test_pattern = ToggleScreen('TEST_PATTERN', 'Test leds', self)
        ip_info = InformationScreen('IP_INFO', 'Adresse IP', self,
            get_ip_address())

        universe_selector.setCallback(
            lambda uni: self.panel.setAddress(universe=uni)
            )
        channel_selector.setCallback(
            lambda chan: self.panel.setAddress(channel=chan)
            )
        blackout.setCallback(lambda off: self.panel.setOnOff(not off))

        home.addChild(main_menu)

        main_menu.addChild(universe_selector)
        main_menu.addChild(channel_selector)
        main_menu.addChild(manual_menu)
        main_menu.addChild(ip_info)

        manual_menu.addChild(blackout)
        manual_menu.addChild(test_pattern)

        self.current = home

        self.lcd = liquidcrystal_i2c.LiquidCrystal_I2C(0x3F, 1, numlines=4)

        # UP/DOWN arrow. Use as char \x00
        self.lcd.createChar(0, [
            0b00100,
            0b01110,
            0b11111,
            0b00000,
            0b00000,
            0b11111,
            0b01110,
            0b00100
            ])

        self.updateScreen()

    def listenToGPIO(self):
        for pin in [UP_BUTTON, DOWN_BUTTON, OK_BUTTON, BACK_BUTTON]:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin, GPIO.RISING,
                callback=self.getGPIOCallback(),
                bouncetime=500
                )

    def getGPIOCallback(self):
        def GPIOCallback(channel):
            #self.backlightOn()

            if channel == UP_BUTTON:
                print("UP", channel)
                self.current.onUp()
            elif channel == DOWN_BUTTON:
                print("DOWN", channel)
                self.current.onDown()
            elif channel == OK_BUTTON:
                print("OK", channel)
                self.current.onOK()
            elif channel == BACK_BUTTON:
                print("BACK", channel)
                self.current.onBack()
            self.updateScreen()
        return GPIOCallback

    def backlightOn(self):
        self.on_time = datetime.now()
        self.lcd.backlight()
        self.panel.threadSafeSchedule(
            11*1000,
            self.turn_off_backlight_if_inactivity
            )

    def turn_off_backlight_if_inactivity(self):
        if datetime.now() - self.on_time >= timedelta(seconds=10):
            self.lcd.noBacklight()

    def updateScreen(self):
        self.current.computeDisplay()
        self.lcd.printline(0, self.current.first_line + "                    ")
        self.lcd.printline(1, self.current.second_line + "                    ")

if __name__ == '__main__':
    from LedPanel import LEDPanel
    
    GPIO.setmode(GPIO.BCM)

    #panel = fakepanel()
    panel = LEDPanel(universe=0, channel=1)
    manager = ScreenManager(panel)

    try:
        #manager.backlightOn()
        manager.lcd.backlight()

        manager.listenToGPIO()
        manager.updateScreen()
        panel.run()
    finally:
        manager.lcd.clear()
        manager.lcd.noBacklight()
        panel.setOnOff(False)
        GPIO.cleanup()
