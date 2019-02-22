#!/bin/env python3

# LED Panel
# Copyright (C) 2019 Nils VAN ZUIJLEN

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from datetime import datetime, timedelta
import math
import threading
import subprocess

from ola.DMXConstants import DMX_UNIVERSE_SIZE
from RPi import GPIO
from RPLCD.i2c import CharLCD

from LedPanel import STATUS_LED
import macros

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
    return subprocess.check_output(["hostname", "-i"]).decode().split(' ')[0]


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
        if child not in self.children:
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
            print("E: gotoSelectedChild called on screen {} with selectedChild not being "
                  "in correct range".format(self.scr_id))
        except TypeError:
            print("E: gotoSelectedChild called on screen {} with selectedChild being None"
                  .format(self.scr_id))

    def gotoParent(self):
        if self.parent is not None:
            self.manager.current = self.parent
        else:
            print("E: gotoParent called on screen {} with parent being None"
                  .format(self.scr_id))

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

    It can not be a child of any other screen,
    raises ParentalError if you try to do it anyway
    """
    def __init__(self, scr_id, showname, manager, text):
        super(StartScreen, self).__init__(scr_id, showname, manager)
        self.text = text

    def setParent(self):
        raise ParentalError("Assigning a Start screen as child of someone")

    onOK = gotoSelectedChild

    def computeDisplay(self):
        super(StartScreen, self).computeDisplay()
        self.second_line = self.text[:20]


class EndScreen(Screen):
    """An End screen

    It can not have childrens, if you try to assign some anyway,
    it will raise a ParentalError
    """
    def addChild(self, child):
        raise ParentalError('EndScreen cannot have any children')

    onOK = gotoParent

    onBack = gotoParent


class MenuScreen(Screen):
    """A Menu Screen"""
    onOK = gotoSelectedChild

    onBack = gotoParent

    onUp = incrementSelectedChild

    onDown = decrementSelectedChild

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


class MacroScreen(EndScreen):
    """Screen used to run macros"""
    def __init__(self, scr_id, showname, manager, macro, repeat=True):
        super(MacroScreen, self).__init__(scr_id, showname, manager)
        self.macro = macro
        self.running = False
        self.repeat = repeat
        self.panel = self.manager.panel

    def onOK(self):
        if self.running:
            self._stop()
        else:
            self._run()

    def onBack(self):
        self._stop()
        super(self.__class__, self).onBack()

    def onUp(self):
        if not self.running:
            self._run()

    def computeDisplay(self):
        super(self.__class__, self).computeDisplay()
        if self.running:
            self.second_line = "En cours"
        else:
            self.second_line = "A l'arret"

    def _run(self):
        self.running = True

        self.panel.unsubscribeFromUniverses()

        self.panel.threadSafeSchedule(
            self.macro.step_length,
            self._run_callback
            )

    def _run_callback(self):
        if not self.running:
            return

        try:
            frame = next(self.macro)
        except StopIteration:
            if self.repeat:
                frame = next(self.macro)
            else:
                return

        # send the frame to the panel
        frame

        self.panel.threadSafeSchedule(
            self.macro.step_length,
            self._run_callback
            )

    def _stop(self):
        self.running = False
        self.panel.subscribeToUniverses()

    onDown = _stop


class ScreenManager:
    """Manages Screens

    Creates the arborescence needed for a LedPanel and manages it

    Please call cleanup() once you have finished.
    """
    def __init__(self, panel):
        self.panel = panel

        self.lcd_lock = threading.RLock()
        self.gpio_lock = threading.Lock()

        home = StartScreen('HOME', 'LedPanel 289', self,
                           'Made by N.V.Zuijlen')
        main_menu = MenuScreen('MAIN_MENU', 'Menu', self)
        manual_menu = MenuScreen('MANUAL_MENU', 'Manuel', self)
        universe_selector = ValueScreen('UNIVERSE_SELECTOR', 'Choix Univers', self,
                                        self.panel.start_universe, 0, math.inf)
        channel_selector = ValueScreen('CHANNEL_SELECTOR', 'Choix Adresse', self,
                                       self.panel.start_channel+1, 1, DMX_UNIVERSE_SIZE)
        blackout = ToggleScreen('BLACKOUT', 'Blackout', self)
        test_pattern = MacroScreen('TEST_PATTERN', 'Test leds', self, macros.TestPixels())
        ip_info = InformationScreen('IP_INFO', 'Adresse IP', self, get_ip_address())

        universe_selector.setCallback(lambda uni: self.panel.setAddress(universe=uni))
        channel_selector.setCallback(lambda chan: self.panel.setAddress(channel=chan))
        blackout.setCallback(lambda off: self.panel.setOnOff(not off))

        home.addChild(main_menu)

        main_menu.addChild(universe_selector)
        main_menu.addChild(channel_selector)
        main_menu.addChild(manual_menu)
        main_menu.addChild(ip_info)

        manual_menu.addChild(blackout)
        manual_menu.addChild(test_pattern)

        self.current = home

        with self.lcd_lock:
            self.lcd = CharLCD(i2c_expander='PCF8574', address=0x3F, cols=20, rows=4,
                               auto_linebreaks=False, backlight_enabled=False)

            self.lcd.cursor_mode = 'hide'

            # UP/DOWN arrow. Use as char \x00
            self.lcd.create_char(0, (
                0b00100,
                0b01110,
                0b11111,
                0b00000,
                0b00000,
                0b11111,
                0b01110,
                0b00100
                ))

            self.updateScreen()
            #self.backlightOn()

    def listenToGPIO(self):
        for pin in [UP_BUTTON, DOWN_BUTTON, OK_BUTTON, BACK_BUTTON]:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin, GPIO.RISING,
                callback=self.getGPIOCallback(),
                bouncetime=200
                )

    def getGPIOCallback(self):
        def GPIOCallback(channel):
            with self.gpio_lock:
                GPIO.output(STATUS_LED, GPIO.HIGH)
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

                GPIO.output(STATUS_LED, GPIO.LOW)
        return GPIOCallback

    def backlightOn(self):
        self.on_time = datetime.now()
        with self.lcd_lock:
            self.lcd.backlight_enabled = True
        self.panel.threadSafeSchedule(
            11*1000,
            self.turn_off_backlight_if_inactivity
            )

    def turn_off_backlight_if_inactivity(self):
        if datetime.now() - self.on_time >= timedelta(seconds=10):
            with self.lcd_lock:
                self.lcd.backlight_enabled = False

    def updateScreen(self):
        self.current.computeDisplay()

        with self.lcd_lock:
            self.lcd.clear()
            self.lcd.write_string(self.current.first_line)
            self.lcd.crlf()
            self.lcd.write_string(self.current.second_line)

    def cleanup(self):
        GPIO.cleanup()
        with self.lcd_lock:
            self.lcd.close(clear=True)


if __name__ == '__main__':
    from LedPanel import LEDPanel

    GPIO.setmode(GPIO.BCM)

    # panel = fakepanel()  # use this if you do not want the real panel to fire up.
    panel = LEDPanel(universe=0, channel=1)
    manager = ScreenManager(panel)

    try:
        #manager.backlightOn()
        with manager.lcd_lock:
            manager.lcd.backlight_enabled = True

        manager.listenToGPIO()
        manager.updateScreen()

        GPIO.setup(STATUS_LED, GPIO.OUT)
        GPIO.output(STATUS_LED, GPIO.LOW)

        panel.run()
    finally:
        GPIO.output(STATUS_LED, GPIO.LOW)
        manager.cleanup()
        panel.setOnOff(False)
