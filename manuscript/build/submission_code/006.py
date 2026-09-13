"""Package the current paper, complete source appendix and necessary evidence.
Run with Python 3.13: python manuscript/package_submission.py
No simulator is started. ZIP and PDF must each remain below 20,000,000 bytes.
"""
from pathlib import Path
import ast, hashlib, io, json, re, shutil, tarfile, zipfile
from PIL import Image, PngImagePlugin
ROOT = Path(__file__).resolve().parents[1]
M = ROOT / 'manuscript'
D = M / 'story_draft'
BUILD = M / 'build'
STAGE = BUILD / 'submission_support'
# Reuse the historical evidence selection, not its obsolete manuscript or output.
namespace = {'__file__': str(M / 'package_sources.py')}
selection = (M / 'package_sources.py').read_text().split('# Single archive compression')[0]
exec(compile(selection, 'package_sources_selection', 'exec'), namespace)
selected = {p for p in namespace['selected'] if p.parts[0] not in ('manuscript', 'JammersSimulatorData')}
def add(path):
    p = Path(path)
    if not p.is_absolute(): p = ROOT / p
    if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
        selected.add(p.relative_to(ROOT))
# Exact image assets referenced by the current TeX, never an old illustration set.
tex = (D / '中文论文初稿.tex').read_text()
for name in re.findall(r'\\includegraphics\[[^\]]*\]\{([^}]+)\}', tex): add(D / name)
for pattern in ('analysis/*.py', 'analysis/source_data/*', 'figures/*.csv', 'figures/*.json', 'plot_data/20260913_process/*'):
    for p in D.glob(pattern): add(p)
for name in ('中文论文初稿.md', '中文论文初稿.tex'): add(D / name)
for name in ('requirements.txt', 'package_sources.py', 'package_submission.py', 'ai_details.tex'): add(M / name)
for p in (M / 'analysis').glob('*'): add(p)
for q, indices in ((3, (1,2,4)), (4, (1,2,3))):
    for p in (ROOT / f'question{q}/results/jlog_question{q}').glob(f'formal-p{q}-*.jlog'): add(p)
    for i in indices:
        for p in (ROOT / f'question{q}/results/windows_q{q}_final_{i:03d}').rglob('*'): add(p)
# Supplementary dispatch development discussed in Appendix B.5.
for p in (ROOT/'question3/dispatch_refinement').rglob('*'): add(p)
for p in (ROOT/'question3/results/dispatch_20260913').rglob('*'):
    if p.name in ('summary.json','comparison.json','configs.json','fixtures.json','lock.json') or p.suffix == '.py': add(p)
# Scripts/data for process figures use these compact inputs and the preserved formal runs.
for script in ('export_q3_convergence.py','export_q4_discovery.py','export_formal_process.py'):
    add(D/'analysis'/script)
# Unused whole-project manifests index excluded historical traces, not paper inputs.
for name in ('paper_evidence/q4_mechanism_reset_20260912/ARTIFACT_SHA256.json', 'question4/innovation/frozen_manifest.json'):
    selected.discard(Path(name))
STAGE.mkdir(parents=True, exist_ok=True)
shutil.rmtree(STAGE)
STAGE.mkdir()
records=[]; sources={}; regular={}; evidence={}
for rel in sorted(selected):
    data=(ROOT/rel).read_bytes()
    original=hashlib.sha256(data).hexdigest()
    if rel.suffix == '.png':
        # Lossless encoding only: preserve pixels, dimensions and ancillary metadata.
        im=Image.open(io.BytesIO(data)); metadata=PngImagePlugin.PngInfo(); offset=8
        while offset < len(data):
            size=int.from_bytes(data[offset:offset+4], 'big'); kind=data[offset+4:offset+8]
            if kind not in (b'IHDR',b'IDAT',b'IEND'):
                metadata.add(kind,data[offset+8:offset+8+size])
            offset+=size+12
        output=io.BytesIO();im.save(output,format='PNG',optimize=True,compress_level=9,pnginfo=metadata)
        optimized=output.getvalue()
        assert Image.open(io.BytesIO(optimized)).tobytes()==im.tobytes()
        if len(optimized)<len(data): data=optimized
    # Diagnostic copies may contain local usernames; retain both hashes.
    if rel.suffix in ('.py','.md','.json','.jsonl','.txt','.tex','.csv','.sh'):
        try:
            text=data.decode('utf-8')
            text=text.replace(str(ROOT), 'PROJECT_ROOT').replace(str(Path.home())+'/', 'USER_HOME/')
            # Windows profile components are diagnostic paths, not model inputs.
            text=re.sub(r'(?i)([A-Z]:[\\/]+Users[\\/]+)[^\\/\s"\']+', r'\1USER', text)
            data=text.encode('utf-8')
        except UnicodeDecodeError: pass
    sha=hashlib.sha256(data).hexdigest()
    records.append(dict(path=str(rel),bytes=len(data),sha256=sha,original_sha256=original,copy_anonymized=sha!=original and rel.suffix!='.png',lossless_png=sha!=original and rel.suffix=='.png'))
    if rel.suffix=='.py':
        ast.parse(data.decode('utf-8-sig'),filename=str(rel))
        sources.setdefault(sha,dict(data=data,paths=[]))['paths'].append(str(rel))
    is_regular = rel.suffix in ('.png','.jpg','.pdf','.jlog') or str(rel) in ('manuscript/story_draft/中文论文初稿.tex','manuscript/story_draft/中文论文初稿.md')
    (regular if is_regular else evidence)[str(rel)]=data
for name,data in regular.items():
    p=STAGE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
with tarfile.open(STAGE/'evidence.tar.xz','w:xz',preset=9) as tar:
    for name,data in evidence.items():
        info=tarfile.TarInfo(name);info.size=len(data);info.mtime=0;info.mode=0o644
        tar.addfile(info,io.BytesIO(data))
restore='''from pathlib import Path
import hashlib,json,tarfile
root=Path(__file__).resolve().parent
with tarfile.open(root/'evidence.tar.xz','r:xz') as tar:
    for item in tar:
        dst=(root/item.name).resolve()
        if not dst.is_relative_to(root) or not item.isfile(): raise ValueError('Unsafe member')
        data=tar.extractfile(item).read()
        if dst.exists() and dst.read_bytes()!=data: raise ValueError('Existing file differs: '+item.name)
        dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
for row in json.loads((root/'SUPPORT_MANIFEST.json').read_text())['files']:
    assert hashlib.sha256((root/row['path']).read_bytes()).hexdigest()==row['sha256'],row['path']
print('All support hashes verified.')
'''
(STAGE/'restore_evidence.py').write_text(restore)
# Full code bodies appear once, with every duplicate frozen path explicitly mapped.
code_dir=BUILD/'submission_code';code_dir.mkdir(exist_ok=True)
code_tex=[];code_map=[]
for i,(sha,entry) in enumerate(sorted(sources.items(),key=lambda x:x[1]['paths'][0]),1):
    name=f'{i:03d}.py';(code_dir/name).write_bytes(entry['data'])
    code_tex += [r'\subsection*{程序 '+str(i)+'}',r'\noindent 对应文件：'+'；'.join(r'\path{'+p+'}' for p in entry['paths'])+r'\par',
                 r'\VerbatimInput[fontsize=\fontsize{7.3}{8.5}\selectfont,breaklines=true,breakanywhere=true,tabsize=4,numbers=left,numbersep=4pt,xleftmargin=12pt]{../build/submission_code/'+name+'}']
    code_map.append(dict(program=i,sha256=sha,paths=entry['paths']))
(BUILD/'submission_code.tex').write_text('\n'.join(code_tex))
# Print all direct file names. The single evidence archive has a full internal manifest.
inventory=[r'支撑包中的\path{evidence.tar.xz}保存较大的原始逐例结果、配置和冻结文件；运行\path{restore_evidence.py}恢复目录，并按\path{SUPPORT_MANIFEST.json}逐文件校验。六份正式\path{.jlog}以原名、原始字节直接保存在第三、四问日志目录。',r'全部完整Python源程序如下，相同内容的冻结副本只打印一次；对应路径全部列出。诊断文本中的本机用户目录已替换，原件和副本哈希均保留；正式日志未作改动。',r'\subsection*{支撑材料文件列表}',r'顶层文件：\path{README.md}、\path{AI工具使用详情.pdf}、\path{SUPPORT_MANIFEST.json}、\path{SOURCE_MAP.json}、\path{restore_evidence.py}、\path{evidence.tar.xz}。']
for name in sorted(regular): inventory.append(r'\par\noindent\path{'+name+'}')
inventory.append(r'\par\noindent 排版生成文件：\path{manuscript/build/submission_inventory.tex}、\path{manuscript/build/submission_code.tex}及\path{manuscript/build/submission_code/}中的编号源码副本。压缩证据内部逐文件路径、大小和哈希见\path{SUPPORT_MANIFEST.json}。')
inventory_text='\n'.join(inventory)
# URL verbatim mode disables CJK switching; use ordinary text for Chinese names.
def cjk_path(match):
    name=match.group(1)
    if name.isascii(): return match.group(0)
    escaped=name.replace('_',r'\_').replace('%',r'\%').replace('&',r'\&')
    return r'\texttt{'+escaped+'}'
inventory_text=re.sub(r'\\path\{([^}]+)\}',cjk_path,inventory_text)
(BUILD/'submission_inventory.tex').write_text(inventory_text)
for name in ('submission_code.tex','submission_inventory.tex'):
    dst=STAGE/'manuscript/build'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BUILD/name,dst)
shutil.copytree(code_dir,STAGE/'manuscript/build/submission_code')
(STAGE/'SOURCE_MAP.json').write_text(json.dumps(code_map,ensure_ascii=False,indent=2))
shutil.copy2(M/'delivery/AI工具使用详情.pdf',STAGE/'AI工具使用详情.pdf')
(STAGE/'README.md').write_text('''# 支撑材料使用说明

对应论文：从两次测向到完整清除：有界误差下无线电干扰源的鲁棒定位与在线调度。

1. 先运行 `python restore_evidence.py`，恢复压缩证据并逐文件校验。
2. 安装 `python -m pip install -r manuscript/requirements.txt`。Python 3.13；NumPy 2.4、SciPy 1.17。
3. 基本检查：`python -m unittest discover -s question1 -p 'test*.py'`；`python -m unittest discover -s question2 -p 'test*.py'`。
4. 正式过程复算：`python manuscript/story_draft/analysis/export_formal_process.py`。仅读取已有日志，不启动测试。
5. 论文源文件是 `manuscript/story_draft/中文论文初稿.tex`，在所在目录用Tectonic或XeLaTeX编译；需Noto Serif/Sans CJK SC、Times New Roman和DejaVu Sans Mono字体。不要用早期的build_document.py覆盖现有TeX。

完整Python程序在论文附录F逐份收录；SOURCE_MAP.json映射重复冻结路径。较大历史证据以evidence.tar.xz保存；标准Python可解压。保留正文最终逐例数值、必要对照、源程序与配置，不声称包含全部未采用研发方案的逐动作历史。第三、四问六份正式日志原名和原字节保留，不修改其头信息或加密体；自动核验未解密官方行为体。官方原件与旁路动作记录的联系按题号、顺序和时间戳核对。

诊断文本的本机绝对目录可能已替换为PROJECT_ROOT、USER_HOME或USER；清单保留原始及交付哈希，旧源码锁若指向原始字节，不应把投影副本当作原件验证。数值未替换。不存在的本机工作目录需要按解压路径配置。

AI用途与人工主导分工见AI工具使用详情.pdf；历史型号及逐项人工审查记录仍需参赛队据实补全。
''')
# Include generated files in the verification manifest, avoiding recursive self-hashes.
known={r['path'] for r in records}
for p in sorted(STAGE.rglob('*')):
    name=str(p.relative_to(STAGE))
    if p.is_file() and name not in known and name!='evidence.tar.xz':
        data=p.read_bytes();sha=hashlib.sha256(data).hexdigest()
        records.append(dict(path=name,bytes=len(data),sha256=sha,original_sha256=sha,copy_anonymized=False))
(STAGE/'SUPPORT_MANIFEST.json').write_text(json.dumps(dict(files=records,archive='evidence.tar.xz',formal_logs_unchanged=True),ensure_ascii=False,indent=2))
zip_path=M/'delivery/支撑材料.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(STAGE.rglob('*')):
        if p.is_file(): z.write(p,str(p.relative_to(STAGE)))
result=dict(files=len(records),unique_sources=len(sources),source_lines=sum(len(x['data'].splitlines()) for x in sources.values()),zip_bytes=zip_path.stat().st_size,within_20MB=zip_path.stat().st_size<=20_000_000)
(BUILD/'submission_package_result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
if not result['within_20MB']: raise SystemExit('Support ZIP exceeds 20 MB')
