"""Redraw manuscript Figures 1 and 8 as explanatory vector diagrams.

Contract: Figure 1 explains the Q1–Q4 dependency chain; Figure 8 explains
task-level receding-horizon scheduling and the two valid stopping conditions.
All small geometric drawings are conceptual, without coordinate or scale claims.
No experimental observations, strategy code, or quantitative results are changed.
Python/matplotlib produces both the authoritative figures and review comparisons.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import sys

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mcm-flow-redesign-mpl")
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, Polygon, Rectangle, FancyBboxPatch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures"
REVIEW = ROOT / "figure_review" / "batch01"
AUDIT = REVIEW / "audit"
SKILL_SCRIPTS = Path.home() / ".codex/skills/nature-figure/scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))
from audit_panel_alignment import require_matplotlib_panel_alignment

NAVY = "#233D50"
TEAL = "#237D8C"
ORANGE = "#B96438"
PURPLE = "#8265A3"
MUTED = "#617580"
LINE = "#C7D4DA"
PALE = "#EFF5F7"
WARM = "#FBF2EB"
WHITE = "#FFFFFF"

# The installed PuHuiTi face is regular-only. Convert the needed Noto bold
# outlines to TrueType for reliable editable embedding through matplotlib and TeX.
# CFF outlines with pdf.fonttype=42 can extract as text yet disappear in the PDF.
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools import subset
font_chars = Path(__file__).read_text() + "改前改后图0123456789"
font_key = hashlib.sha256(font_chars.encode()).hexdigest()[:12]
bold_path = Path(os.environ["MPLCONFIGDIR"]) / f"NotoSansCJKsc-Bold-{font_key}.ttf"
if not bold_path.exists():
    bold_path.parent.mkdir(parents=True, exist_ok=True)
    source_font = TTFont("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", fontNumber=2)
    subsetter = subset.Subsetter()
    subsetter.populate(text=font_chars)
    subsetter.subset(source_font)
    glyph_set = source_font.getGlyphSet()
    glyph_order = source_font.getGlyphOrder()
    glyphs = {}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        glyph_set[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        glyphs[name] = pen.glyph()
    builder = FontBuilder(source_font["head"].unitsPerEm, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(source_font.getBestCmap())
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(source_font["hmtx"].metrics)
    builder.setupHorizontalHeader(ascent=source_font["hhea"].ascent,
                                  descent=source_font["hhea"].descent)
    builder.setupNameTable({"familyName": "MCM Figure CJK", "styleName": "Bold",
                            "uniqueFontIdentifier": "MCMFigureCJK-Bold",
                            "fullName": "MCM Figure CJK Bold",
                            "psName": "MCMFigureCJK-Bold"})
    builder.setupOS2(usWeightClass=700, sTypoAscender=source_font["OS/2"].sTypoAscender,
                    sTypoDescender=source_font["OS/2"].sTypoDescender,
                    usWinAscent=source_font["OS/2"].usWinAscent,
                    usWinDescent=source_font["OS/2"].usWinDescent)
    builder.setupPost()
    builder.setupMaxp()
    builder.save(bold_path)

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Alibaba PuHuiTi", "DejaVu Sans"],
    "font.size": 9,
    "text.color": NAVY,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "axes.unicode_minus": False,
    "savefig.facecolor": WHITE,
})


def text(ax, x, y, value, size=9, color=NAVY, weight="normal", ha="left"):
    kwargs = {"fontproperties": font_manager.FontProperties(
        fname=bold_path, family="Noto Sans CJK SC")} if weight == "bold" else {}
    return ax.text(x, y, value, fontsize=size, color=color, weight=weight,
                   ha=ha, va="center", linespacing=1.65, zorder=8, **kwargs)


def panel(ax, x, y, w, h, face=PALE, edge="none", radius=1.2):
    patch = FancyBboxPatch((x, y), w, h,
                          boxstyle=f"round,pad=0,rounding_size={radius}",
                          facecolor=face, edgecolor=edge, linewidth=.8, zorder=0)
    ax.add_patch(patch)
    return patch


def arrow(ax, points, color=NAVY, width=1.15, dashed=False):
    """Orthogonal paths keep the last segment's arrowhead away from labels."""
    if len(points) > 2:
        xy = np.asarray(points[:-1])
        ax.plot(xy[:, 0], xy[:, 1], color=color, linewidth=width,
                linestyle="--" if dashed else "-", zorder=3,
                solid_joinstyle="round", solid_capstyle="round")
    ax.annotate("", xy=points[-1], xytext=points[-2], zorder=3,
                arrowprops=dict(arrowstyle="->", color=color, lw=width,
                                mutation_scale=9, shrinkA=0, shrinkB=0,
                                linestyle="--" if dashed else "-"))


def canvas(height):
    fig = plt.figure(figsize=(7.086614173, height / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 180), ylim=(height, 0))
    ax.axis("off")
    return fig, ax


def save(fig, stem, axes=None, ids=None):
    AUDIT.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, axes=axes, panel_ids=ids,
        row_groups=[ids] if ids else None,
        json_out=AUDIT / f"{stem}.alignment.json", strict=True,
    )
    fig.savefig(OUT / f"{stem}.pdf")
    fig.savefig(OUT / f"{stem}.svg")
    svg_path = OUT / f"{stem}.svg"
    svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text().splitlines()) + "\n")
    fig.savefig(OUT / f"{stem}.png", dpi=300)
    plt.close(fig)
    print(stem, report["verdict"])


def mini_geometry(ax, index):
    """Conceptual objects only; station ratios preserve the stated constructions."""
    if index == 0:
        pts = np.array([[5, 35], [10, 20], [26, 15], [32, 31], [19, 42]])
        ax.add_patch(Circle((19, 29), 16, fill=False, edgecolor=TEAL, lw=.9))
        ax.add_patch(Polygon(pts, facecolor="#EBE5F1", edgecolor=PURPLE, lw=1.15))
        distance = np.linalg.norm(pts[:, None] - pts[None, :], axis=2)
        i, j = np.unravel_index(np.argmax(distance), distance.shape)
        ends = pts[[i, j]]
        ax.plot(ends[:, 0], ends[:, 1], color=NAVY, lw=1.45)
        ax.scatter(ends[:, 0], ends[:, 1], s=12, color=NAVY, zorder=4)
        assert np.max(np.linalg.norm(pts - [19, 29], axis=1)) <= 16
        # A radius and a diameter are different objects, even in the overview.
        ax.plot([19, 35], [29, 29], color=TEAL, lw=1.0)
        ax.scatter([19], [29], s=9, color=TEAL, zorder=4)
    elif index == 1:
        ax.add_patch(Polygon([[4, 37], [33, 28], [33, 33]],
                             facecolor="#EBE5F1", edgecolor=PURPLE, lw=1))
        ax.add_patch(Polygon([[12, 31], [19, 17], [27, 22], [29, 28]],
                             facecolor="#E0EEF0", edgecolor="none"))
        ax.add_patch(Polygon([[12, 39], [19, 46], [27, 41], [29, 34]],
                             facecolor="#E0EEF0", edgecolor="none"))
        ax.plot([4, 23, 31], [37, 23, 30.5], color=TEAL, lw=1.1)
        ax.scatter([4], [37], color=NAVY, s=20, zorder=4)
        ax.scatter([23], [23], color=ORANGE, s=27, zorder=4)
        ax.scatter([31], [30.5], color=PURPLE, s=15, zorder=4)
    elif index == 2:
        ctr = np.array([19, 30])
        ang = np.arange(6) * np.pi / 3
        ring = ctr + 9.4 * np.c_[np.cos(ang), np.sin(ang)]
        ax.add_patch(Circle(ctr, 15, fill=False, edgecolor=LINE, lw=1.1))
        for p in np.vstack([ctr, ring]):
            ax.add_patch(Circle(p, 8.35, facecolor="#E7F0F2", edgecolor=LINE,
                                lw=.45, alpha=.38))
        route = np.vstack([ctr, ring[[0, 1, 2, 3]]])
        ax.plot(route[:, 0], route[:, 1], color=TEAL, lw=1.25)
        ax.scatter(ring[:, 0], ring[:, 1], s=14, color=TEAL, zorder=4)
        ax.scatter(*ctr, s=16, color=NAVY, zorder=4)
        arrow(ax, [tuple(route[1]), tuple(route[2])], color=ORANGE)
    else:
        ctr = np.array([19, 30])
        ang = np.arange(12) * np.pi / 6
        inner = ctr + (950 / 1870 * 15.6) * np.c_[np.cos(ang), np.sin(ang)]
        outer = ctr + 15.6 * np.c_[np.cos(ang + np.pi / 12), np.sin(ang + np.pi / 12)]
        ax.add_patch(Circle(ctr, 1800 / 1870 * 15.6, fill=False,
                            edgecolor=LINE, lw=1.0))
        for k in range(12):
            p = np.vstack([ctr, inner[k], inner[(k + 1) % 12], outer[k], inner[k]])
            ax.plot(p[:, 0], p[:, 1], color=LINE, lw=.5)
            p = np.vstack([inner[k], outer[(k - 1) % 12], outer[k]])
            ax.plot(p[:, 0], p[:, 1], color=LINE, lw=.5)
        ax.add_patch(Polygon([inner[0], inner[1], outer[0]], facecolor="#F5DFCB",
                             edgecolor=ORANGE, lw=1.1, zorder=3))
        ax.scatter(inner[:, 0], inner[:, 1], s=8, color=TEAL, zorder=4)
        ax.scatter(outer[:, 0], outer[:, 1], s=8, color=ORANGE, zorder=4)
        ax.scatter(*ctr, s=14, color=NAVY, marker="*", zorder=4)


def overview():
    fig, base = canvas(109)
    text(base, 6, 7, "从局部定位到完整清除", size=12, weight="bold")
    text(base, 174, 7, "问题递进 · 方法衔接", size=8, color=MUTED, ha="right")
    columns = []
    labels = [
        ("Q1", "区域与覆盖", "测向取交定位区域", "区分直径与覆盖半径"),
        ("Q2", "鲁棒第二点", "接收约束与交会几何", "权衡定位精度与路程"),
        ("Q3", "全向多源搜索", "七站发现 · 联合调度", "兼顾共享观测与清除"),
        ("Q4", "定向混合场景", "双环发现 · 光学回退", "重建发现与清除保证"),
    ]
    for i, (qid, title, method, purpose) in enumerate(labels):
        x = 6 + i * 43.5
        ax = fig.add_axes([x / 180, (109 - 76) / 109, 37.5 / 180, 60 / 109])
        ax.set(xlim=(0, 37.5), ylim=(60, 0))
        ax.axis("off")
        columns.append(ax)
        text(ax, 0, 3, qid, 9, TEAL, "bold")
        text(ax, 37.5, 3, title, 10, NAVY, "bold", "right")
        ax.plot([0, 37.5], [8, 8], color=LINE, lw=.8)
        mini_geometry(ax, i)
        text(ax, 18.75, 51, method, 8.5, NAVY, "bold", "center")
        text(ax, 18.75, 58, purpose, 8, MUTED, ha="center")
        if i < 3:
            arrow(base, [(x + 38.8, 46), (x + 42.2, 46)], color=MUTED, width=.9)
    panel(base, 6, 82, 168, 20, face=PALE)
    text(base, 10, 87.5, "Q3–Q4 在线执行", 8, TEAL, "bold")
    steps = ["观测反馈", "更新位置区域", "选择合法动作", "执行当前任务"]
    centers = [61, 93, 126, 158]
    for i, (x, value) in enumerate(zip(centers, steps)):
        text(base, x, 87.5, value, 8.4, NAVY, ha="center")
        if i < 3:
            arrow(base, [(x + 13.5, 87.5), (centers[i + 1] - 13.5, 87.5)],
                  color=TEAL, width=.9)
    arrow(base, [(158, 91.5), (158, 97), (61, 97), (61, 91.5)],
          color=TEAL, width=.8)
    # The feedback label is outside the return stroke, never overprinted on it.
    text(base, 10, 97, "任务完成后重排", 8, MUTED)
    save(fig, "fig01_overview", columns, ["Q1", "Q2", "Q3", "Q4"])


def algorithm():
    fig, ax = canvas(122)
    for x, num, label in [(7, "01", "维护任务池"), (65, "02", "滚动排序"),
                          (121, "03", "执行与反馈")]:
        text(ax, x, 8, num, 10, TEAL, "bold")
        text(ax, x + 8, 8, label, 11, NAVY, "bold")
    ax.plot([7, 173], [14, 14], color=LINE, lw=.8)

    # One pool holds both task types. Top-level scheduling is task based.
    panel(ax, 7, 24, 44, 49)
    text(ax, 12, 33, "未完成搜索站", 9.5, NAVY, "bold")
    text(ax, 12, 41, "代表点：站点坐标", 8, MUTED)
    ax.plot([12, 46], [48, 48], color=LINE, lw=.7)
    text(ax, 12, 56, "已知未清源", 9.5, NAVY, "bold")
    text(ax, 12, 64, "代表点：区域包围盒中心", 8, MUTED)
    arrow(ax, [(52, 48.5), (63, 48.5)], color=NAVY)

    panel(ax, 65, 34, 42, 24, face=NAVY)
    text(ax, 86, 41.5, "最近邻 + 2-opt", 10, WHITE, "bold", "center")
    text(ax, 86, 51, "比较开放路径长度", 8.5, WHITE, ha="center")
    text(ax, 86, 65.5, "只执行首项任务", 9.5, ORANGE, "bold", "center")

    # The branches are alternatives, not parallel execution.
    arrow(ax, [(108.5, 46), (115, 46), (115, 32), (120, 32)])
    arrow(ax, [(115, 46), (115, 63), (120, 63)])
    panel(ax, 122, 21, 51, 22, face=PALE)
    text(ax, 126, 27.5, "搜索任务", 9.5, TEAL, "bold")
    text(ax, 126, 35.5, "到站扫描未知频道，登记新源", 8)
    panel(ax, 122, 49, 51, 31, face=WARM)
    text(ax, 126, 55.5, "源服务任务", 9.5, ORANGE, "bold")
    text(ax, 126, 64, "测向收缩 → 覆盖清除 / 光学回退", 7.8)
    text(ax, 126, 72.5, "满足接收与信息条件才共享观测", 7.8)

    # Both complete tasks merge into one record-update step.
    arrow(ax, [(174, 32), (177, 32), (177, 88), (163, 88), (163, 91)], width=.9)
    arrow(ax, [(147.5, 81), (147.5, 91)], width=.9)
    panel(ax, 64, 92, 109, 12, face=PALE, edge=LINE)
    text(ax, 118.5, 98, "任务完成：更新位置区域、扫描与清除记录", 9, NAVY, "bold", "center")
    arrow(ax, [(63, 98), (48, 98)], width=1)

    decision = Polygon([(31, 87), (47, 98), (31, 109), (15, 98)],
                       facecolor=WHITE, edgecolor=TEAL, linewidth=1.1)
    ax.add_patch(decision)
    text(ax, 31, 98, "满足停止\n条件？", 8.5, NAVY, "bold", "center")
    arrow(ax, [(31, 86), (31, 74)], color=TEAL)
    text(ax, 34, 80, "否：重建任务池", 8, TEAL)
    arrow(ax, [(14, 98), (7, 98), (7, 114), (18, 114)], color=TEAL, width=.9)
    text(ax, 11, 94, "是", 8, TEAL, ha="center")
    text(ax, 20, 114, "退出并核验反馈", 8.5, TEAL, "bold")
    text(ax, 66, 113, "停止条件：清除16源；或已知源全清除，", 7.8, MUTED)
    text(ax, 66, 118, "且每个未知频道都有七站无信号记录。", 7.8, MUTED)
    save(fig, "fig06_q3_algorithm")


def comparison(stem, number):
    """Review sheet made from the unchanged old PDF and final vector export."""
    import pymupdf
    fig, base = canvas(242)
    text(base, 6, 8, f"图{number} · 改前 / 改后", 12, NAVY, "bold")
    regions = [("改前", REVIEW / "before" / f"{stem}.pdf", 20),
               ("改后", OUT / f"{stem}.pdf", 132)]
    for title, path, top in regions:
        text(base, 6, top, title, 9, TEAL, "bold")
        doc = pymupdf.open(path)
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        imax = fig.add_axes([5 / 180, (242 - top - 107) / 242, 170 / 180, 101 / 242])
        imax.imshow(arr)
        imax.axis("off")
        doc.close()
    fig.savefig(REVIEW / f"figure{number:02d}_comparison.pdf")
    fig.savefig(REVIEW / f"figure{number:02d}_comparison.png", dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparisons", action="store_true", help="Also export review sheets.")
    args = parser.parse_args()
    overview()
    algorithm()
    if args.comparisons:
        comparison("fig01_overview", 1)
        comparison("fig06_q3_algorithm", 8)


if __name__ == "__main__":
    main()
