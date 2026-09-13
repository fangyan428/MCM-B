"""Build a size-bounded, reproducible support archive without altering originals.
Run from the project root: python manuscript/package_sources.py
Rebuild after the manuscript and AI detail PDF have been compiled.
"""
from pathlib import Path
import io, json, hashlib, tarfile, zipfile, shutil, re, csv
ROOT=Path(__file__).resolve().parent.parent
M=ROOT/'manuscript'; STAGE=M/'build/support'; STAGE.mkdir(parents=True,exist_ok=True)
selected=set()
def add(p):
 p=Path(p)
 if not p.is_absolute():p=ROOT/p
 if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':selected.add(p.relative_to(ROOT))
def glob(pattern):
 for p in ROOT.glob(pattern):add(p)
# Original problem files are needed by the source-hash verification.
for p in ROOT.glob('B题/**/*'):
 add(p)
# Complete live runtime and figure/analysis programs.
for q in ('question1','question2','question3','question4'):
 glob(q+'/*.py');glob(q+'/requirements*.txt');glob(q+'/*.md')
 glob(q+'/configs/**/*.json')
glob('question3/tests/*.py');glob('question3/docs/*.md')
glob('question3/innovation/*.py');glob('question4/innovation/*.py')
glob('question4/certificates/*.json');glob('question4/docs/*.md')
for p in ('question1/example_result.json','question2/results.json','question2/round1_tradeoff.json') :add(p)
# The complete Q3 export is required by its frozen provenance checker.
e=json.loads((ROOT/'question3/innovation/EXPORT_MANIFEST.json').read_text())
for p in e['files']:add(Path('question3/innovation')/p)
add('question3/innovation/EXPORT_MANIFEST.json')
# Original Q4 result bodies used by the independent consistency check.
e=json.loads((M/'analysis/q4_verification.json').read_text())
for p in e['input_sha256']:add(p)
# Source, locks, summaries and decision records of mechanism exploration.
reset='paper_evidence/q4_mechanism_reset_20260912'
for pat in ('*.py','*.json','*.md','validation_lock/*','reporting/*.py','reporting/WORST_CASE.*','source_review/*.json','qa/*.py','qa/*.json','qa/*.md','final_validation/*.json','round*/*.md','round*/*.json','round*/development/*.json','round*/development/code_snapshot/**/*.py','final_validation/code_snapshot/**/*.py','frozen/**/*.py'):
 glob(reset+'/'+pat)
for pat in ('*.json','*.md','results/*comparison*.json','results/*statistics*.json','results/*evidence*.json','results/*selection*.json','locks/**/*.json','frozen_baseline/**/*.py'):
 glob('question4/innovation/'+pat)
glob(reset+'/**/selection_snapshot.txt')
glob('question4/innovation/**/selection_snapshot.txt')
for pat in ('results/*/summary.json','results/*/fixtures.json','results/*/configs.json','results/*/lock.json','results/*review*.json','results/negative21*.json'):
 glob('question4/'+pat)
# Historical Q3 numerical reports and code snapshots underlying selected comparisons.
for prefix in ('round1_','round13_','round14_','round17_','round18_','round19_'):
 for p in (ROOT/'question3/results').glob(prefix+'*'):
  if p.is_dir():
   for fn in ('summary.json','comparison.json','configs.json','paired_cases.csv'):add(p/fn)
   for f in p.glob('code_snapshot/**/*.py'):add(f)
  elif p.suffix=='.json':add(p)
# Representative Q4 failure case includes complete public actions and events.
for variant in ('BASE25','COVER_EXCHANGE_ELASTIC'):
 for name in ('actions.jsonl','strategy.jsonl','result.json'):
  add(f'{reset}/final_validation/{variant}/uniform_4c920b65f2c8599c__positive__bounded/{name}')
# Keep official practice original result sidecars only; encrypted envelopes contain team identity.
glob('JammersSimulatorData/behavior-logs/*.result.json')
# Manuscript source and derived analyses, excluding transient build files and private local paths.
glob('manuscript/sections/*.tex');add('manuscript/main.tex');add('manuscript/ai_details.tex')
glob('manuscript/analysis/*');glob('manuscript/figures/*')
for p in ('README.md','requirements.txt','build.sh','restore_evidence.py'):add('manuscript/'+p)
add('manuscript/package_sources.py')
for p in M.glob('audit/*.md'):add(p)
for p in M.glob('audit/reviews/*.md'):add(p)
# Single archive compression shares repeated result keys across files.
records=[];py_unique={};changed=[]
regular={};evidence={}
for rel in sorted(selected):
 data=(ROOT/rel).read_bytes();sha=hashlib.sha256(data).hexdigest()
 # Anonymous diagnostic/lock metadata copies; original hash chains still refer to originals.
 # Executable code, algorithm configurations and numerical result values remain unchanged.
 if (rel.parts[0]=='manuscript' or str(rel).startswith(reset+'/')) and rel.suffix in ('.md','.json','.txt'):
  raw=data.decode('utf-8');clean=raw.replace(str(ROOT),'PROJECT_ROOT').replace(str(Path.home())+'/', 'USER_HOME/')
  if clean!=raw:data=clean.encode();changed.append(str(rel))
 output_sha=hashlib.sha256(data).hexdigest()
 records.append({'path':str(rel),'bytes':len(data),'original_sha256':sha,'sha256':output_sha,'copy_anonymized':sha!=output_sha})
 if rel.suffix=='.py':py_unique.setdefault(output_sha,[]).append(str(rel))
 if rel.parts[0]=='manuscript' or (rel.suffix=='.py' and 'frozen' not in str(rel) and 'code_snapshot' not in rel.parts) or ('configs' in rel.parts and len(rel.parts)<5) or rel.name.startswith('requirements'):
  regular[str(rel)]=data
 else:evidence[str(rel)]=data
# Delete only this builder's previous support staging directory.
shutil.rmtree(STAGE);STAGE.mkdir(parents=True)
for rel,data in regular.items():
 p=STAGE/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
archive=STAGE/'evidence.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=9) as tar:
 for rel,data in evidence.items():
  info=tarfile.TarInfo(rel);info.size=len(data);info.mtime=0;info.mode=0o644;tar.addfile(info,io.BytesIO(data))
manifest={'version':1,'files':records,'regular_files':len(regular),'archived_files':len(evidence),'anonymized_copies':changed,
 'anonymized_lock_note':'Absolute local paths in Q4 lock/command metadata are projected to PROJECT_ROOT/USER_HOME. Existing lock-chain hashes refer to original files, not the projected bytes. Consult original_sha256; byte-level original lock verification requires the local originals.',
 'excluded':'Original credential databases, encrypted practice envelopes with team identity, complete unused action histories; formal logs not available.'}
(STAGE/'SUPPORT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
# Copy the restore script to the top-level for a one-command extraction.
shutil.copy2(M/'restore_evidence.py',STAGE/'restore_evidence.py')
# Exact complete source bodies, once per content hash; duplicate locations have a map.
code_dir=M/'build/code';code_dir.mkdir(exist_ok=True)
code_tex=[];code_map=[]
for i,(sha,paths) in enumerate(sorted(py_unique.items(),key=lambda x:x[1][0]),1):
 representative=paths[0];data=(ROOT/representative).read_bytes();out=code_dir/f'{i:03}.py';out.write_bytes(data)
 code_tex += [f'\\subsection*{{程序 {i}：\\texttt{{{Path(representative).name.replace("_",r"\_")}}}}}',
  '\\noindent 文件路径：\\path{'+representative+'}\\par',
  f'\\VerbatimInput[fontsize=\\fontsize{{7.3}}{{8.5}}\\selectfont,breaklines=true,breakanywhere=true,tabsize=4,numbers=left,numbersep=4pt,xleftmargin=12pt]{{build/code/{i:03}.py}}']
 code_map.append({'program':i,'sha256':sha,'paths':paths})
(M/'build/code_appendix.tex').write_text('\n'.join(code_tex))
(M/'build/source_map.json').write_text(json.dumps(code_map,ensure_ascii=False,indent=2))
# Include all original filenames via a compact full list in the appendix, grouped by directories.
dirs={}
for name in regular:
 p=Path(name);dirs.setdefault(str(p.parent),[]).append(p.name)
tex=[f'支撑包保存 {len(records)} 个来源文件，其中 {len(py_unique)} 份内容不同的完整Python源程序。相同源码的多个冻结路径不重复印刷，映射见\\path{{manuscript/build/source_map.json}}。',
'较大的逐例结果以\\path{evidence.tar.gz}保存，解压支撑ZIP后运行\\texttt{python restore\\_evidence.py}恢复原目录并校验哈希。',
'演练原始加密包含身份字段，保留于本地项目；支撑包只含脱敏统计投影、原结果旁文件及原件SHA256。它可重算统计，但不替代原件身份或签名核验。',
'部分问题四历史命令与锁元数据的本机路径已脱敏，原件及副本哈希均列入清单；旧锁链哈希仍指向本地原件，不宣称脱敏副本与原锁字节相同。',
'顶层文件为\\path{evidence.tar.gz}、\\path{SUPPORT_MANIFEST.json}、\\path{restore_evidence.py}及AI工具使用详情PDF。以下按目录列出直接文件；压缩证据的完整内部成员由\\path{SUPPORT_MANIFEST.json}列出。']
# Directory-level list is readable; full path list delivered in machine-readable manifest.
for directory,names in sorted(dirs.items()):
 if len(directory.split('/'))>5 and ('final_validation' in directory or 'results' in directory):continue
 tex.append('\\par\\noindent\\path{'+directory+'/}：'+str(len(names))+'个文件。\\par')
 tex.append('\\begingroup\\footnotesize '+ '\\allowbreak；'.join('\\path{'+n+'}' for n in names)+'\\par\\endgroup')
(M/'build/support_inventory.tex').write_text('\n'.join(tex))
for fn in ('code_appendix.tex','support_inventory.tex','source_map.json'):
 dest=STAGE/'manuscript/build'/fn;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(M/'build'/fn,dest)
shutil.copytree(code_dir,STAGE/'manuscript/build/code',dirs_exist_ok=True)
# Final human documents are added when available.
for fn in ('AI工具使用详情.pdf',):
 p=M/'delivery'/fn
 if p.exists():shutil.copy2(p,STAGE/fn)
zip_path=M/'delivery/支撑材料.zip';zip_path.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in sorted(STAGE.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(STAGE)))
summary={'source_files':len(records),'unique_python_sources':len(py_unique),'python_lines':sum(len((ROOT/v[0]).read_text().splitlines()) for v in py_unique.values()),'evidence_gzip_bytes':archive.stat().st_size,'support_zip_bytes':zip_path.stat().st_size,'within_20MB':zip_path.stat().st_size<=20_000_000}
(M/'build/package_result.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
