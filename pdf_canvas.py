"""Worksheet PDF drawing through Omarchy's system Cairo and Pango libraries.

Coordinates stay in points from the bottom left, preserving the exercise layout.
"""
from functools import lru_cache
import math

import cairo
import gi

gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Pango, PangoCairo

letter = (612.0, 792.0)
A4 = (595.2755905511812, 841.8897637795277)


def _layout(context, text, font, size):
    layout = PangoCairo.create_layout(context)
    layout.get_context().set_round_glyph_positions(False)
    options = cairo.FontOptions()
    options.set_hint_metrics(cairo.HINT_METRICS_OFF)
    PangoCairo.context_set_font_options(layout.get_context(), options)
    description = Pango.FontDescription()
    description.set_family('Liberation Sans')
    description.set_weight(Pango.Weight.BOLD if font.endswith('-Bold') else Pango.Weight.NORMAL)
    description.set_absolute_size(size * Pango.SCALE)
    layout.set_font_description(description)
    layout.set_text(str(text), -1)
    return layout


_measure_context = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))


@lru_cache(maxsize=4096)
def stringWidth(text, font, size):
    return _layout(_measure_context, text, font, size).get_size()[0] / Pango.SCALE


def _color(value):
    if isinstance(value, str):
        value = value.removeprefix('#')
        return tuple(int(value[i:i+2], 16) / 255 for i in (0, 2, 4))
    return tuple(value)


class Path:
    def __init__(self):
        self.commands = []

    def moveTo(self, x, y):
        self.commands.append(('move_to', (x, y)))

    def lineTo(self, x, y):
        self.commands.append(('line_to', (x, y)))

    def close(self):
        self.commands.append(('close_path', ()))


class Canvas:
    def __init__(self, filename, pagesize=letter, invariant=True):
        self.width, self.height = pagesize
        self.surface = cairo.PDFSurface(filename, self.width, self.height)
        self.surface.set_metadata(cairo.PDF_METADATA_CREATOR, 'Easy Math Books')
        if invariant:
            self.surface.set_metadata(cairo.PDF_METADATA_CREATE_DATE, '2000-01-01T00:00:00Z')
            self.surface.set_metadata(cairo.PDF_METADATA_MOD_DATE, '2000-01-01T00:00:00Z')
        self._reset()

    def _reset(self):
        self.context = cairo.Context(self.surface)
        self.context.translate(0, self.height)
        self.context.scale(1, -1)
        self.fill = self.stroke = (0, 0, 0)
        self.font, self.size = 'Helvetica', 12
        self.states = []

    def setTitle(self, title):
        self.surface.set_metadata(cairo.PDF_METADATA_TITLE, title)

    def setFont(self, font, size):
        self.font, self.size = font, size

    def setFillColor(self, color):
        self.fill = _color(color)

    def setStrokeColor(self, color):
        self.stroke = _color(color)

    def setFillColorRGB(self, red, green, blue):
        self.fill = (red, green, blue)

    def setFillGray(self, grey):
        self.fill = (grey, grey, grey)

    def setStrokeGray(self, grey):
        self.stroke = (grey, grey, grey)

    def setLineWidth(self, width):
        self.context.set_line_width(width)

    def setLineCap(self, cap):
        self.context.set_line_cap(cap)

    def drawString(self, x, y, text):
        context = self.context
        context.save()
        context.translate(x, y)
        context.scale(1, -1)
        context.set_source_rgb(*self.fill)
        layout = _layout(context, text, self.font, self.size)
        context.move_to(0, -layout.get_baseline() / Pango.SCALE)
        PangoCairo.show_layout(context, layout)
        context.restore()

    def drawRightString(self, x, y, text):
        self.drawString(x - stringWidth(text, self.font, self.size), y, text)

    def drawCentredString(self, x, y, text):
        self.drawString(x - stringWidth(text, self.font, self.size) / 2, y, text)

    def _paint(self, stroke, fill):
        if fill:
            self.context.set_source_rgb(*self.fill)
            if stroke:
                self.context.fill_preserve()
            else:
                self.context.fill()
        if stroke:
            self.context.set_source_rgb(*self.stroke)
            self.context.stroke()
        elif not fill:
            self.context.new_path()

    def line(self, x1, y1, x2, y2):
        self.context.new_path()
        self.context.move_to(x1, y1)
        self.context.line_to(x2, y2)
        self._paint(True, False)

    def rect(self, x, y, width, height, stroke=1, fill=0):
        self.context.new_path()
        self.context.rectangle(x, y, width, height)
        self._paint(stroke, fill)

    def roundRect(self, x, y, width, height, radius, stroke=1, fill=0):
        radius = min(radius, width / 2, height / 2)
        context = self.context
        context.new_path()
        for cx, cy, start in ((x+width-radius, y+height-radius, 0),
                              (x+radius, y+height-radius, math.pi/2),
                              (x+radius, y+radius, math.pi),
                              (x+width-radius, y+radius, math.pi*1.5)):
            context.arc(cx, cy, radius, start, start+math.pi/2)
        context.close_path()
        self._paint(stroke, fill)

    def beginPath(self):
        return Path()

    def drawPath(self, path, stroke=1, fill=0):
        self.context.new_path()
        for method, arguments in path.commands:
            getattr(self.context, method)(*arguments)
        self._paint(stroke, fill)

    def saveState(self):
        self.context.save()
        self.states.append((self.fill, self.stroke, self.font, self.size))

    def restoreState(self):
        self.context.restore()
        self.fill, self.stroke, self.font, self.size = self.states.pop()

    def draw_svg(self, svg, x, y, width, height):
        gi.require_version('Rsvg', '2.0')
        from gi.repository import Rsvg
        handle = Rsvg.Handle.new_from_data(svg.encode('utf-8'))
        viewport = Rsvg.Rectangle()
        viewport.x = viewport.y = 0
        viewport.width, viewport.height = width, height
        self.context.save()
        try:
            self.context.translate(x, y+height)
            self.context.scale(1, -1)
            handle.render_document(self.context, viewport)
        finally:
            self.context.restore()

    def showPage(self):
        self.context.show_page()
        self._reset()

    def save(self):
        self.surface.finish()
