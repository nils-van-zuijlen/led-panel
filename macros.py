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

from dataclasses import dataclass, astuple


@dataclass()
class Color:
    red: int = 0
    green: int = 0
    blue: int = 0

    @property
    def white(self):
        if self.red == self.green == self.blue:
            return self.red
        else:
            raise TypeError("white is not defined if red, green and blue are different")

    @white.setter
    def white(self, value):
        self.red = self.green = self.blue = value


class Macro:
    """Base Macro class"""
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.index = 0

    @property
    def empty_color_panel(self):
        return [[Color() for _ in range(self.cols)] for _ in range(self.rows)]

    @property
    def empty_table_panel(self):
        return [[[0, 0, 0] for _ in range(self.cols)] for _ in range(self.rows)]

    def decode(self, panel):
        p = []
        try:
            _ = panel[0][0].red
        except AttributeError:
            for row in panel:
                for pixel in row:
                    p.append(tuple(pixel))
        else:
            for row in panel:
                for pixel in row:
                    p.append(astuple(pixel))
        return p

    def __iter__(self):
        return self

    def __next__(self):
        if self.index == len(self):
            self.index = 0
            raise StopIteration

        val = self.decode(self.loop(self.index))

        self.index += 1

        return val


class TestPixels(Macro):
    """An example macro"""
    def __init__(self, cols, rows):
        super(self.__class__, self).__init__(cols, rows)

    def loop(self, i):
        i -= 1

        if i == -1:
            panel = self.empty_color_panel

            for row in panel:
                for pixel in row:
                    pixel.white = 255

            return panel
        else:
            panel = self.empty_table_panel

            row = i % self.rows
            col = (i // self.rows) % self.cols
            color = ((i // self.rows) // self.cols) % self.cols

            panel[row][col][color] = 255

        return panel

    def __len__(self):
        return self.cols * self.rows * 3 + 1

    @property
    def step_length(self):
        """Length of a step in ms"""
        return 500
