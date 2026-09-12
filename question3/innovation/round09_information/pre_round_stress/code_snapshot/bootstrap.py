"""Freeze source materials and recommendation before any experimental changes."""
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

def main():
    frozen = ROOT / 'frozen'
    frozen.mkdir(exist_ok=False)
    paths = list((REPO/'question3').glob('*.py'))
    paths += [REPO/'question1/solve.py', REPO/'question2/strategy.py',
              REPO/'question3/configs/recommended_omni.json',
              REPO/'question3/releases/recommended_manifest.json']
    paths += list((REPO/'question3/docs').glob('*'))
    paths += list((REPO/'B题').rglob('*.pdf')) + list((REPO/'B题').rglob('*.docx'))
    hashes = {}
    for p in paths:
        if not p.is_file():
            continue
        rel = p.relative_to(REPO)
        dst = frozen/rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        hashes[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    prior = json.loads((REPO/'question3/releases/recommended_manifest.json').read_text())
    mismatch = [p for p,h in prior['code_sha256'].items() if hashes.get(p) != h]
    assert not mismatch, mismatch
    assert hashes['question3/configs/recommended_omni.json'] == prior['config_sha256']
    (ROOT/'freeze_manifest.json').write_text(json.dumps(dict(
        sha256=hashes, recommendation_matches_manifest=True,
        python=sys.version, platform=platform.platform(),
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        initial_git_status=subprocess.check_output(['git','status','--short'],cwd=REPO,text=True),
        official_runs=0, formal_runs=0),ensure_ascii=False,indent=2))
    sources = ROOT/'source_review'
    sources.mkdir()
    subprocess.run(['pdftotext','-layout',str(REPO/'B题/B题.pdf'),str(sources/'题面.txt')],check=True)
    for p in (REPO/'B题/附件').glob('*.docx'):
        with zipfile.ZipFile(p) as z:
            xml = ET.fromstring(z.read('word/document.xml'))
        ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs = [''.join(t.text or '' for t in para.findall('.//w:t',ns)) for para in xml.findall('.//w:p',ns)]
        (sources/(p.stem+'.txt')).write_text('\n'.join(paragraphs))
    print(json.dumps({'frozen_files':len(hashes),'manifest_match':True}))

if __name__ == '__main__':
    main()
