"""Write a standalone SVG scientific diagram; sampled fill, analytic constraints in report."""
from pathlib import Path
import numpy as np
from strategy import candidate, DELTA

def point(a,b):return (80+.36*a,430-.36*b)
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1060" height="850" viewBox="0 0 1060 850">',
'<rect width="1060" height="850" fill="white"/>',
'<style>text{font-family:Arial,sans-serif;fill:#183047}.title{font-size:24px;font-weight:600}.body{font-size:16px}.small{font-size:13px}</style>',
'<text x="50" y="40" class="title">Second detection point: guaranteed reception and geometry</text>',
'<text x="50" y="66" class="body">Local coordinates: first detection at S, first bearing along +a (metres)</text>']
for a in range(0,1051,10):
 for b in range(-1050,1051,10):
  h=a*np.cos(DELTA)-abs(b)*np.sin(DELTA)
  reception=a*a+b*b-10*h+25<=1e6 and a*a+b*b<=2000*h
  if reception:
   x,y=point(a,b)
   color='#24a896' if candidate([a,b]) else '#dde4ea'
   parts.append(f'<rect x="{x-1.8:.2f}" y="{y-1.8:.2f}" width="3.6" height="3.6" fill="{color}"/>')
for r in [500,1000,1500]:
 x,_=point(r,0)
 parts.append(f'<line x1="{x}" y1="100" x2="{x}" y2="790" stroke="#ccd4dc" stroke-dasharray="3 5"/>')
 parts.append(f'<text x="{x-16}" y="450" class="small">{r}</text>')
for b in [-1000,-500,500,1000]:
 _,y=point(0,b)
 parts.append(f'<text x="25" y="{y+5}" class="small">{b}</text>')
parts += ['<line x1="65" y1="430" x2="665" y2="430" stroke="#30475c"/>','<line x1="80" y1="810" x2="80" y2="90" stroke="#30475c"/>',
'<text x="650" y="420" class="body">a</text>','<text x="65" y="95" class="body">b</text>']
x1,y1=point(1500*np.cos(DELTA),1500*np.sin(DELTA));x2,y2=point(1500*np.cos(DELTA),-1500*np.sin(DELTA))
parts.append(f'<path d="M80 430 L{x1} {y1} L{x2} {y2} Z" fill="#f7b44b" fill-opacity=".8" stroke="#bd7519"/>')
for a,b,label in [(0,0,'S'),(800,605,'Q+ (800, 605)'),(800,-605,'Q- (800, -605)')]:
 x,y=point(a,b)
 if a:parts.append(f'<line x1="80" y1="430" x2="{x}" y2="{y}" stroke="#1e6575" stroke-dasharray="6 4"/>')
 parts.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#123a54"/><text x="{x+10}" y="{y-10}" class="body">{label}</text>')
for y,color,label in [(160,'#dde4ea','Guaranteed reception region'),(210,'#24a896','Safe candidates: angle >= 20 deg'),(260,'#f7b44b','Initial +/-1 deg source sector')]:
 parts.append(f'<rect x="700" y="{y-15}" width="20" height="20" fill="{color}"/><text x="730" y="{y}" class="body">{label}</text>')
for i,line in enumerate(['Full source sector: 5 < r <= 1500 m','Receiver radius: 1000 <= R <= 1500 m','Blue dots: sampled minimax design','','Candidate fill sampled every 10 m.','Analytic inequalities define the region.','Target-disc clipping is not used.']):
 parts.append(f'<text x="700" y="{330+i*27}" class="small">{line.replace("<","&lt;")}</text>')
parts.append('<text x="50" y="830" class="small">Reflection gives equivalent choices for the full sector; actual target-disc clipping may break this symmetry.</text></svg>')
Path(__file__).with_name('candidate_region.svg').write_text('\n'.join(parts))
