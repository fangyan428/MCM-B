"""Immutable round7 K runtime with compact two-stage evidence; raw logs stay in repo."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED


def main():
    root=Path('question3');out=root/'releases/q3_omni_round7.zip'
    if out.exists():raise RuntimeError('Do not overwrite release')
    lock=json.loads((root/'results/round7_k_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    assert json.loads((root/'configs/recommended_omni.json').read_text())==lock['configs']['K']
    with ZipFile(root/'releases/q3_omni_round5.zip') as z:files={Path(p) for p in z.namelist()}
    files.update(root.glob('*.py'))
    for folder,pattern in [('configs','*.json'),('tests','*.py'),('diagnostics','*.py'),('docs','*')]:
        files.update(p for p in (root/folder).rglob(pattern) if p.is_file())
    files.update([root/'STATUS.md',root/'README.md',root/'RUN_RECOMMENDED.md',root/'releases/recommended_manifest.json',root/'releases/recommended_manifest_round5.json'])
    for prefix in ['round6','round7']:
        files.update(p for p in (root/'results').glob(prefix+'_*') if p.is_file())
        for d in (root/'results').glob(prefix+'_*'):
            if d.is_dir():
                for name in ['summary.json','configs.json','comparison.json','paired_cases.csv']:
                    if (d/name).exists():files.add(d/name)
    for b,c,variants in [('round7_holdout_main','holdout_70047_smooth',['REF','D','K','DK']),
                         ('round7_k_holdout_main','holdout_90015_smooth',['REF','K']),
                         ('round7_k_outer_main','outer_holdout_100006_negative',['REF','K'])]:
        for v in variants:files.update((root/'results'/b/v/c).glob('*.*'))
    for d in ['round7_release_http','round7_k_release_http']:
        files.update(p for p in (root/'results'/d).rglob('*') if p.is_file())
    with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):
            if not p.is_file():raise RuntimeError('Missing input: '+str(p))
            z.write(p,p.as_posix())
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(digest+'  '+out.name+'\n')
    print(json.dumps(dict(path=str(out),files=len(files),bytes=out.stat().st_size,sha256=digest),indent=2))


if __name__=='__main__':main()
