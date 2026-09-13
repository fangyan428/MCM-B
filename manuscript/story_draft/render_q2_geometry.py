"""Render the Q2 intersection geometry and second-point counterexamples.

Run from any working directory. Only figures/fig03_q2_failures.{png,pdf,svg}
are generated. Panel (a) uses an admissible alpha=0 geometry for explaining
the variables; it is not a simulated search trajectory.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Arc, Polygon
import numpy as np


def dimension(ax, start, end, label, text_at, color):
    ax.annotate("", xy=end, xytext=start,
                arrowprops={"arrowstyle": "<->", "lw": 1.0, "color": color,
                            "shrinkA": 0, "shrinkB": 0})
    ax.text(*text_at, label, ha="center", va="center", color=color,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})


def main():
    output = Path(__file__).resolve().parent / "figures"
    output.mkdir(exist_ok=True)
    noto = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if noto.is_file():
        font_manager.fontManager.addfont(str(noto))
        family = font_manager.FontProperties(fname=str(noto)).get_name()
    else:
        family = "sans-serif"
    plt.rcParams.update({
        "font.family": family,
        "font.size": 11,
        "mathtext.fontset": "dejavusans",
        "axes.unicode_minus": False,
        "axes.linewidth": 0.9,
        # Type 3 embeds glyph outlines reliably for the OpenType/CFF Noto TTC;
        # Type 42 can leave its Chinese and ordinary digit glyphs invisible.
        "pdf.fonttype": 3,
        "svg.fonttype": "path",
        "svg.hashsalt": "q2-intersection-geometry",
        "savefig.facecolor": "white",
    })

    ink = "#243D4C"
    teal = "#228598"
    orange = "#BC6032"
    gray = "#7B8990"

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.85))
    fig.subplots_adjust(left=0.065, right=0.99, bottom=0.17, top=0.90, wspace=0.22)
    for ax in axes:
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(-130, 1650)
        ax.set_ylim(-360, 840)
        ax.set_xticks([0, 500, 1000, 1500])
        ax.set_yticks([0, 400, 800])
        ax.tick_params(labelsize=10, length=3.5, pad=3)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("沿首次示向方向 / m", labelpad=6)
        ax.set_ylabel("法向位置 / m", labelpad=5)

    ax = axes[0]
    ax.set_title("(a) 交会三角形与横向距离", fontsize=12, pad=12, color=ink)
    source = np.array([1200.0, 0.0])
    second = np.array([800.0, 605.0])
    vertices = np.array([[0.0, 0.0], second, source])
    ax.add_patch(Polygon(vertices, closed=True, facecolor=teal,
                         edgecolor="none", alpha=0.065))
    ax.plot([0, 800], [0, 605], color=gray, lw=1.3)
    ax.plot([0, 1200], [0, 0], color=ink, lw=1.6)
    ax.plot([800, 1200], [605, 0], color=teal, lw=1.9)
    ax.plot([800, 800], [0, 605], color=orange, lw=1.5, ls=(0, (4, 2.5)))
    ax.plot([760, 760, 800], [0, 40, 40], color=orange, lw=1.0)
    ax.scatter(vertices[:, 0], vertices[:, 1], s=29, color=ink, zorder=5)
    ax.scatter([800], [0], s=19, color=orange, zorder=5)
    ax.text(-18, -55, r"$S$", color=ink, ha="right", va="top")
    ax.text(800, 656, r"$Q=(800,605)$", color=ink, ha="center")
    ax.text(1250, 15, r"$G$", color=ink, va="bottom")
    ax.text(824, -48, r"$H$", color=orange, va="top")
    ax.text(738, 180, r"$c=|Q-H|=b$", color=orange, ha="right", va="center")

    ax.annotate("", xy=(420, 0), xytext=(125, 0),
                arrowprops={"arrowstyle": "->", "lw": 1.7, "color": ink})
    ax.text(287, 41, r"$u$", color=ink, ha="center")
    ax.annotate("", xy=(0, 325), xytext=(0, 0),
                arrowprops={"arrowstyle": "->", "lw": 1.2, "color": ink})
    ax.text(-35, 300, r"$v$", color=ink, ha="right")
    ax.text(70, 755, r"示意：$\alpha=0$", color=gray, fontsize=10)

    for x in (0, 800, 1200):
        ax.plot([x, x], [-90, -295 if x != 800 else -178],
                color=gray, lw=0.6, alpha=0.65)
    dimension(ax, (0, -150), (800, -150), r"$a$", (400, -150), ink)
    dimension(ax, (0, -270), (1200, -270), r"$r=|G-S|$", (600, -270), ink)

    bearing_at_g = np.degrees(np.arctan2(second[1], second[0] - source[0]))
    ax.add_patch(Arc(source, 270, 270, theta1=bearing_at_g, theta2=180,
                     color=teal, lw=1.2))
    mid_angle = np.deg2rad((bearing_at_g + 180) / 2)
    beta_at = source + 195 * np.array([np.cos(mid_angle), np.sin(mid_angle)])
    ax.text(*beta_at, r"$\beta$", color=teal, ha="center", va="center")
    ax.text(1065, 338, r"$d_2=|G-Q|$", color=teal, ha="center", va="center",
            rotation=bearing_at_g - 180, rotation_mode="anchor")

    ax = axes[1]
    ax.set_title("(b) 仅横移或前移的反例", fontsize=12, pad=12, color=ink)
    ax.plot([0, 1500], [500, 0], color=orange, lw=1.9, ls=(0, (4.5, 2.5)))
    ax.plot([0, 1500], [0, 0], color=teal, lw=2.2)
    ax.scatter([0, 1500], [0, 0], s=34, color=ink, zorder=5)
    ax.scatter([0], [500], s=39, color=orange, zorder=5)
    ax.scatter([500], [0], s=31, color=teal, zorder=5)
    ax.text(0, 57, r"首测点 $S$", color=ink, ha="left")
    ax.text(1500, 110, "源 (1500,0)", color=ink, ha="right")
    ax.text(40, 573, "横移点 (0,500)", color=orange, ha="left")
    distance = np.hypot(1500.0, 500.0)
    ax.text(770, 406, f"{distance:.2f} m：失联", color=orange, ha="center")
    ax.text(650, 755, "本例接收半径 1500 m", color=gray, ha="center", fontsize=10)
    ax.text(730, -150, "前移点 (500,0)", color=teal, ha="center")
    ax.text(730, -248, "中心线重合，交会退化", color=teal, ha="center")

    for suffix in ("png", "pdf", "svg"):
        kwargs = {"dpi": 300} if suffix == "png" else {}
        if suffix == "pdf":
            kwargs["metadata"] = {"CreationDate": None, "ModDate": None}
        elif suffix == "svg":
            kwargs["metadata"] = {"Date": None}
        destination = output / f"fig03_q2_failures.{suffix}"
        fig.savefig(destination, **kwargs)
        if suffix == "svg":
            destination.write_text(
                "\n".join(line.rstrip() for line in destination.read_text().splitlines()) + "\n"
            )
    plt.close(fig)


if __name__ == "__main__":
    main()
