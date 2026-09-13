"""Convert the editable Chinese Markdown manuscript into a typeset LaTeX source."""
from pathlib import Path
import re,subprocess,shutil

ROOT=Path(__file__).resolve().parents[1]
pandoc=shutil.which('pandoc') or str(Path.home()/'.local/bin/pandoc')
body=subprocess.check_output([pandoc,str(ROOT/'中文论文初稿.md'),'-f','markdown+tex_math_dollars','-t','latex','--syntax-highlighting=none'],text=True)
body=re.sub(r'\\pandocbounded\{\\includegraphics\[.*?\]\{(figures/[^}]+)\.png\}\}',
    lambda m:r'\includegraphics[width=0.98\linewidth]{'+m[1]+'.pdf}',body)
body=body.replace(r'\def\LTcaptype{none}',r'\def\LTcaptype{table}')
body=body.replace(r'\begin{figure}',r'\begin{figure}[htbp]')
captions=iter(['核心集合与几何符号','算法模块的输入、输出与限制','自建实验组、独立布局与用途','Q3锁定验证的完整流程结果','Q3共同父方案的机制矩阵','Q4最新锁定验证的完整流程结果','构造等边三角形定位区域的测向数据','Q2固定候选库的完整复核结果','主要结论的性质及证据边界'])
def convert_table(m):
    chunk=m[0].replace(r'\begin{longtable}[]',r'\begin{tabular}').replace(r'\end{longtable}',r'\bottomrule'+'\n'+r'\end{tabular}')
    chunk=chunk.replace(r'\endhead','').replace(r'\bottomrule\noalign{}'+'\n'+r'\endlastfoot','')
    return r'\begin{table}[H]'+'\n'+r'\centering\small'+'\n'+r'\caption{'+next(captions)+'}\n'+chunk+'\n'+r'\end{table}'
body=re.sub(r'\\begin\{longtable\}.*?\\end\{longtable\}',convert_table,body,flags=re.S)
# Keep the abstract on its own first page. Numbering is already explicit in the draft.
body=re.sub(r'\\section\{1\s+引言：问题重述与总体思路\}',lambda m:r'\clearpage'+'\n'+m[0],body)
preamble=r'''\documentclass[UTF8,fontset=none,zihao=-4,a4paper]{ctexart}
\usepackage[margin=25mm,footskip=11mm]{geometry}
\setCJKmainfont{Noto Serif CJK SC}[BoldFont=Noto Serif CJK SC Bold,ItalicFont=Noto Serif CJK SC]
\setCJKsansfont{Noto Sans CJK SC}
\setmainfont{Times New Roman}
\usepackage{fancyvrb}
\usepackage[section]{placeins}
\usepackage{amsmath,amssymb,booktabs,longtable,array,calc,graphicx,float,caption,xurl}
\usepackage[unicode,hidelinks,pdfauthor={},pdftitle={从两次测向到完整清除：中文论文初稿}]{hyperref}
\setcounter{secnumdepth}{0}
\setlength{\parskip}{3pt}
\setlength{\emergencystretch}{3em}
\linespread{1.12}
\renewcommand{\arraystretch}{1.2}
\captionsetup{font=small,labelfont=bf,skip=6pt}
\ctexset{section={format=\large\bfseries,beforeskip=13pt,afterskip=8pt},subsection={format=\normalsize\bfseries,beforeskip=9pt,afterskip=5pt}}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\begin{document}
\begin{center}
{\zihao{3}\bfseries 从两次测向到完整清除：\\有界误差下无线电干扰源的鲁棒定位与在线调度}\par
\vspace{5pt}{\small 中文论文初稿}
\end{center}
'''
(ROOT/'中文论文初稿.tex').write_text(preamble+body+'\n\\end{document}\n')
print('Wrote self-contained LaTeX source; 19 vector figure references.')
