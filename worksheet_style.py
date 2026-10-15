"""Use report vector motifs as worksheet stationery through system librsvg."""


def artwork(motif):
    from report import motif_svg, THEMES
    theme = THEMES.get(motif, THEMES['stars'])
    return (motif_svg(motif).replace('var(--accent)', theme[1])
            .replace('var(--soft)', theme[2]).replace('currentColor', theme[1]))


def draw_stationery(c, width, height, motif):
    from report import THEMES
    accent, soft = THEMES.get(motif, THEMES['stars'])[1:3]
    c.saveState()
    c.setStrokeColor(accent)
    c.setLineWidth(1)
    c.roundRect(28, 27, width-56, height-43, 12, stroke=1, fill=0)
    c.setFillColor(soft)
    c.roundRect(34, height-63, width-68, 45, 8, stroke=0, fill=1)
    c.draw_svg(artwork(motif), width-89, height-62, 280*.18, 240*.18)
    c.restoreState()
