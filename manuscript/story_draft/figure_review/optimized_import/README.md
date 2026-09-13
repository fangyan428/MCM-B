# 优化图片入稿记录

2026-09-13：将项目根目录 `优化的图片/` 的四张图片加入《中文论文初稿》，同步更新 Markdown、LaTeX 和 PDF。论文现有20幅图，共44页。

| 来源 | 论文位置 | 入稿文件 |
|---|---|---|
| ` 图 5.png` | 替换图5 | `figures/fig04_q2_region_optimized.png` |
| `图 7.png` | 替换图7 | `figures/fig17_shrink_optimized.png` |
| `图 10.png` | 替换图10 | `figures/fig07_q3_cover_optimized.png` |
| `放在图 12的后面，新图.png` | 图12后新增图13 | `figures/fig20_q4_coverage_certificate.png` |

图片副本与来源逐字节一致。LaTeX 用 `trim` 和 `clip` 隐藏图片自带的重复图号及外围空白，由原生图注统一编号。原图13—19顺延为14—20，正文引用同步更新。原有图形资产未覆盖。

图注保留必要的数学口径：图5的填色不充当式（7）、（8）的数值区域；图7的R数值为固定坐标轴包围盒中心的覆盖半径；图10距离由式（11）计算；新图13的内切半径为圆心到边的垂距，外环顶点半径仍为1870 m。未改动实验结果或模型公式。

检查：20幅图编号连续；Markdown与LaTeX图片顺序一致；引用文件全部存在；全文没有超出页面的文本。用Poppler渲染并查看PDF第13、17、20、24页，确认四张新图完整可读、图注不重复，图12与新图13相邻。编译没有缺失引用或越界警告，只有一处不影响阅读的Underfull hbox。

继续排版时直接编译现有 `中文论文初稿.tex`；目录中的旧Markdown转换器早于现有手工排版，不用于覆盖本次LaTeX源码。可在项目根目录运行：

```bash
XDG_CACHE_HOME="$PWD/manuscript/build/revision2-cache" manuscript/build/revision2-tools/tectonic manuscript/story_draft/中文论文初稿.tex
```

后续尺寸调整：图10宽度由正文宽度的98%缩至76%，图13由98%缩至80%，均保持居中与原始宽高比；Markdown尺寸标注同步。重新编译并渲染核查两处版面。

同步保留远端提交 `5e30846a3` 的附录排版更新，并从合并后的源码重新生成PDF。
