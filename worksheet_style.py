"""Use the same vector motifs on optional worksheet stationery, without changing exercises."""
from xml.etree import ElementTree
from reportlab.lib.colors import HexColor
from reportlab.graphics.shapes import Drawing, Group, Circle, Ellipse
from reportlab.graphics.svgpath import SvgPath
from reportlab.graphics import renderPDF


def artwork(motif):
    from report import motif_svg, THEMES
    theme = THEMES.get(motif, THEMES['stars'])
    svg = motif_svg(motif).replace('var(--accent)', theme[1]).replace('var(--soft)', theme[2])
    root = ElementTree.fromstring(svg)
    group = Group()
    group.transform = (1, 0, 0, -1, 0, 240)
    def visit(node, inherited):
        attrs = {**inherited, **node.attrib}
        tag = node.tag.rsplit('}', 1)[-1]
        def color(value):
            return None if value == 'none' else HexColor(theme[1] if value == 'currentColor' else value)
        kwargs = dict(fillColor=color(attrs.get('fill', '#000000')),
                      strokeColor=color(attrs.get('stroke', 'none')),
                      strokeWidth=float(attrs.get('stroke-width', 1)))
        if tag == 'path':
            group.add(SvgPath(attrs['d'], **kwargs))
        elif tag == 'circle':
            group.add(Circle(float(attrs['cx']), float(attrs['cy']), float(attrs['r']), **kwargs))
        elif tag == 'ellipse':
            group.add(Ellipse(float(attrs['cx']), float(attrs['cy']), float(attrs['rx']), float(attrs['ry']), **kwargs))
        for child in node:
            visit(child, attrs)
    visit(root, {})
    drawing = Drawing(280, 240)
    drawing.add(group)
    return drawing


def draw_stationery(c, width, height, motif):
    from report import THEMES
    accent, soft = THEMES.get(motif, THEMES['stars'])[1:3]
    c.saveState()
    c.setStrokeColor(HexColor(accent))
    c.setLineWidth(1)
    c.roundRect(28, 27, width-56, height-43, 12, stroke=1, fill=0)
    c.setFillColor(HexColor(soft))
    c.roundRect(34, height-63, width-68, 45, 8, stroke=0, fill=1)
    drawing = artwork(motif)
    drawing.scale(.18, .18)
    renderPDF.draw(drawing, c, width-89, height-62)
    c.restoreState()
