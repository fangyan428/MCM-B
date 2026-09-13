"""Render only the Q1 diameter-circle counterexample (Figure 3).

Run from any working directory; outputs are beside this script in figures/.
Coordinates are analytic: an equilateral triangle of side length 39 metres.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, Polygon
import numpy as np


def main():
    root = Path(__file__).resolve().parent
    output = root / "figures"
    output.mkdir(exist_ok=True)

    noto = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if noto.is_file():
        font_manager.fontManager.addfont(str(noto))
        family = font_manager.FontProperties(fname=str(noto)).get_name()
    else:
        family = "sans-serif"
    plt.rcParams.update({
        "font.family": family,
        "font.size": 12,
        "mathtext.fontset": "dejavusans",
        "axes.unicode_minus": False,
        "axes.linewidth": 0.9,
        "pdf.fonttype": 3,
        "svg.fonttype": "path",
        "svg.hashsalt": "q1-diameter-circle-39m",
        "savefig.facecolor": "white",
    })

    purple = "#8763AA"
    orange = "#BC6032"
    teal = "#228598"
    red = "#BD424A"
    ink = "#243D4C"
    side = 39.0
    height = side * np.sqrt(3.0) / 2.0
    vertices = np.array([[0.0, 0.0], [side, 0.0], [side / 2.0, height]])
    diameter_centre = np.array([side / 2.0, 0.0])
    enclosing_centre = np.array([side / 2.0, height / 3.0])
    diameter_radius = side / 2.0
    enclosing_radius = side / np.sqrt(3.0)

    fig = plt.figure(figsize=(7.4, 3.7), facecolor="white")
    ax = fig.add_axes([0.065, 0.17, 0.47, 0.78])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-6, 45)
    ax.set_ylim(-23, 40)
    ax.set_xticks([0, 10, 20, 30, 40])
    ax.set_yticks([-20, -10, 0, 10, 20, 30, 40])
    ax.set_xlabel(r"$x$ / m", labelpad=3)
    ax.set_ylabel(r"$y$ / m", labelpad=3)
    ax.tick_params(labelsize=11, length=3.5, pad=3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.add_patch(Polygon(vertices, closed=True, facecolor=purple, alpha=0.16,
                         edgecolor="none", zorder=1))
    ax.plot(*np.vstack([vertices, vertices[0]]).T, color=purple, lw=1.8, zorder=3)
    ax.add_patch(Circle(enclosing_centre, enclosing_radius, fill=False,
                        edgecolor=teal, lw=1.7, zorder=2))
    ax.add_patch(Circle(diameter_centre, diameter_radius, fill=False,
                        edgecolor=orange, lw=1.9, linestyle=(0, (4.5, 2.5)), zorder=4))
    ax.plot([0, side], [0, 0], color=ink, lw=2.2, zorder=5)
    ax.scatter(vertices[:2, 0], vertices[:2, 1], s=15, color=purple, zorder=6)
    ax.scatter(*vertices[2], s=43, color=red, zorder=7)
    ax.text(vertices[2, 0], vertices[2, 1] + 2.1, r"$V_3$", color=red,
            ha="center", va="bottom", fontsize=12)
    ax.scatter(*diameter_centre, s=21, color=orange, zorder=6)
    ax.scatter(*enclosing_centre, s=21, color=teal, zorder=6)
    ax.text(diameter_centre[0] + 2.2, -4.5, r"$q_D$", color=orange, fontsize=11)
    ax.text(enclosing_centre[0] + 2.2, enclosing_centre[1] - 0.7,
            r"$q_{\min}$", color=teal, fontsize=11)
    ax.annotate("", xy=(side / 2.0, height - 1.1),
                xytext=(side / 2.0, diameter_radius + 0.8),
                arrowprops={"arrowstyle": "<->", "color": red, "lw": 1.1}, zorder=6)
    ax.text(side / 2.0 + 7.2, 26.5, "圆外", color=red, fontsize=11, va="center")

    note = fig.add_axes([0.565, 0.17, 0.405, 0.78])
    note.set_axis_off()
    note.set_xlim(0, 1)
    note.set_ylim(0, 1)
    for y, color, style, label, formula in [
        (0.86, purple, "-", "定位区域（等边三角形）", r"$D=39\ \mathrm{m}$"),
        (0.56, orange, (0, (4.5, 2.5)), "直径圆", r"$D/2=19.50\ \mathrm{m}$"),
        (0.26, teal, "-", "最小覆盖圆", r"$R_{\min}=22.52\ \mathrm{m}>D/2$"),
    ]:
        note.plot([0.0, 0.115], [y, y], color=color, lw=1.9, linestyle=style)
        note.text(0.155, y, label, va="center", fontsize=12, color=ink)
        note.text(0.0, y - 0.12, formula, va="center", fontsize=12.5, color=color)

    for suffix in ("png", "pdf", "svg"):
        kwargs = {"dpi": 300} if suffix == "png" else {}
        if suffix == "pdf":
            kwargs["metadata"] = {"CreationDate": None, "ModDate": None}
        elif suffix == "svg":
            kwargs["metadata"] = {"Date": None}
        destination = output / f"fig02_diameter.{suffix}"
        fig.savefig(destination, **kwargs)
        if suffix == "svg":
            destination.write_text(
                "\n".join(line.rstrip() for line in destination.read_text().splitlines()) + "\n"
            )
    plt.close(fig)


if __name__ == "__main__":
    main()
