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

from rpi_ws281x import PixelStrip

from ola.ClientWrapper import ClientWrapper as OLAClientWrapper
from ola.DMXConstants import DMX_UNIVERSE_SIZE

class ClientWrapper(OLAClientWrapper):
    def Execute(self, f):
        self._ss.Execute(f)
        

class LEDPanel:
    """Listens to new data on the needed universes"""
    def __init__(self, universe, channel):
        self.start_universe = universe
        self.start_channel = channel - 1 # Channels will be numbered starting from 0 in this class
        self._rows = 17
        self._columns = self._rows # We assume it's a square

        self.updateUniversesChannels()

        self._strip = PixelStrip(num=self._led_count, pin=12) # uses PWM0
        self._strip.begin()

        self._wrapper = ClientWrapper()
        self._client = self._wrapper.Client()

        self.subscribeToUniverses()

    def getCallbackForUniverse(self, universe):
        if universe == self.start_universe:
            first_channel = self.start_channel
            last_channel = self._last_channel_used_in_first_universe + 1

            first_pixel_index = 0
        elif universe == self._last_universe:
            first_channel = 0
            last_channel = self._last_channel + 1

            first_pixel_index = self._led_count - (self._rows_in_last_universe * self._columns)
        elif universe > self.start_universe and universe < self._last_universe:
            first_channel = 0
            last_channel = self._last_channel + 1

            internal_universe_index = universe - self.start_universe
            pixels_in_first = self._rows_in_first_universe * self._columns
            pixels_in_full = self._rows_per_full_universe * self._columns
            first_pixel_index = pixels_in_first + (internal_universe_index - 1) * pixels_in_full
        else:
            raise ValueError('universe must be one of the listened universes')

        strip = self._strip
        old_universes = self._old_universes

        def callback(data):
            data = list(data)[first_channel:last_channel]

            if universe not in old_universes or data != old_universes[universe]:
                old_universes[universe] = data

                for i in range(0, last_channel - first_channel, 3):
                    try:
                        r = data[i]
                    except IndexError:
                        r = 0

                    try:
                        g = data[i+1]
                    except IndexError:
                        g = 0

                    try:
                        b = data[i+2]
                    except IndexError:
                        b = 0

                    strip.setPixelColorRGB(int(i/3)+first_pixel_index, r, g, b)
                strip.show()
                print(universe)

        return callback

    def updateUniversesChannels(self):
        self._led_count = self._rows * self._columns
        self._channel_count_per_row = self._columns * 3

        self._rows_per_full_universe = DMX_UNIVERSE_SIZE // self._channel_count_per_row
        channels_in_first_universe = DMX_UNIVERSE_SIZE - self.start_channel
        self._rows_in_first_universe = channels_in_first_universe // self._channel_count_per_row

        self._last_channel_used_in_first_universe = self.start_channel + \
            self._rows_in_first_universe * self._channel_count_per_row - 1

        self._universe_count = 1
        rows_left = self._rows - self._rows_in_first_universe
        while rows_left >= self._rows_per_full_universe:
            self._universe_count += 1
            rows_left -= self._rows_per_full_universe

        if rows_left != 0:
            self._universe_count += 1
            self._last_channel = rows_left * self._channel_count_per_row - 1
            self._rows_in_last_universe = rows_left
        else:
            self._last_channel = DMX_UNIVERSE_SIZE

        self._last_universe = self.start_universe + self._universe_count - 1

        self._old_universes = {}

    def subscribeToUniverses(self):
        for uni in range(self.start_universe, self._last_universe + 1):
            self._client.RegisterUniverse(uni, self._client.REGISTER, self.getCallbackForUniverse(uni))

    def unsubscribeFromUniverses(self):
        for uni in range(self.start_universe, self._last_universe + 1):
            self._client.RegisterUniverse(uni, self._client.UNREGISTER, data_callback=None)

    def run(self):
        print("Launched LEDPanel")
        self._wrapper.Run()

    def setOnOff(self, activate=True):
        self._strip.setBrightness(activate * 255)
        self._strip.show()

    def threadSafeSchedule(self, time_in_ms, callback):
        def f():
            self._wrapper.AddEvent(time_in_ms, callback)
        self._wrapper.Execute(f)

    def setAddress(self, universe=None, channel=None):
        universe = universe if universe is not None else self.start_universe
        channel = channel if channel is not None else self.start_channel

        self.unsubscribeFromUniverses()

        self.start_universe = universe
        self.start_channel = channel

        self.updateUniversesChannels()
        self.subscribeToUniverses()

if __name__ == '__main__':
    panel = LEDPanel(0,1)
    try:
        panel.run()
    except KeyboardInterrupt:
        panel.setOnOff(False)
