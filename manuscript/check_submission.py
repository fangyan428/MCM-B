"""Read-only verification of the delivered PDF, source index and support ZIP."""
from pathlib import Path
import hashlib, io, json, re, tarfile, zipfile
import pymupdf as fitz
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'manuscript/delivery'
pdf=D/'参赛论文.pdf'
report={}
with fitz.open(pdf) as doc:
    texts=[p.get_text() for p in doc]
    report['pdf_pages']=len(doc)
    report['pdf_bytes']=pdf.stat().st_size
    report['a4_all_pages']=all(abs(p.rect.width-595.276)<1 and abs(p.rect.height-841.89)<1 for p in doc)
    report['abstract_one_page']='关键词' in texts[0] and '1 问题重述' in texts[1]
    report['draft_label_on_first_page']='初稿' in texts[0]
    compact=[re.sub(r'\s+','',t) for t in texts]
    statement=next(i for i,t in enumerate(compact) if 'AI工具使用声明' in t)
    references=next(i for i,t in enumerate(texts) if '参考文献' in t)
    appendix=next(i for i,t in enumerate(texts) if t.strip().startswith('附录\n'))
    report['statement_pdf_page']=statement+1
    report['references_pdf_page']=references+1
    report['body_including_references_pages']=appendix-1
    report['statement_before_references']=statement<references or compact[statement].index('AI工具使用声明')<compact[references].index('参考文献')
    report['footer_failures']=[]
    report['text_outside_page']=[]
    for i,p in enumerate(doc):
        words=p.get_text('words')
        footer=[w for w in words if w[4]==str(i+1) and w[1]>p.rect.height-65 and abs((w[0]+w[2])/2-p.rect.width/2)<3]
        if not footer:report['footer_failures'].append(i+1)
        if any(w[0]<-1 or w[1]<-1 or w[2]>p.rect.width+1 or w[3]>p.rect.height+1 for w in words):report['text_outside_page'].append(i+1)
    report['metadata_author']=doc.metadata.get('author','')
    report['source_program_headings']=sum(len(re.findall(r'(?:^|\n)程序\s*\d+\n',t)) for t in texts)
with zipfile.ZipFile(D/'支撑材料.zip') as z:
    assert z.testzip() is None
    files={n:z.read(n) for n in z.namelist()}
    manifest=json.loads(files['SUPPORT_MANIFEST.json'])
    with tarfile.open(fileobj=io.BytesIO(files['evidence.tar.xz']),mode='r:xz') as tar:
        for item in tar:
            assert item.isfile() and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts
            if item.name in files:
                assert item.name in manifest.get('direct_file_overrides',[])
                continue
            files[item.name]=tar.extractfile(item).read()
    for row in manifest['files']:
        assert hashlib.sha256(files[row['path']]).hexdigest()==row['sha256'],row['path']
    source_map=json.loads(files['SOURCE_MAP.json'])
    for row in source_map:
        for p in row['paths']:assert hashlib.sha256(files[p]).hexdigest()==row['sha256']
    logs=[p for p in files if p.endswith('.jlog')]
    assert len(logs)==6
    for p in logs:assert files[p]==(ROOT/p).read_bytes()
    report.update(support_bytes=(D/'支撑材料.zip').stat().st_size,verified_files=len(manifest['files']),formal_original_logs=len(logs),unique_source_programs=len(source_map),ai_pdf_present='AI工具使用详情.pdf' in files)
assert report['pdf_bytes']<=20_000_000 and report['support_bytes']<=20_000_000
assert report['a4_all_pages'] and report['abstract_one_page'] and report['statement_before_references']
assert not report['draft_label_on_first_page'] and not report['footer_failures'] and not report['text_outside_page']
assert report['body_including_references_pages']<=30
assert report['source_program_headings']==report['unique_source_programs']
(D/'format2026核查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
