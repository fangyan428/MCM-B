"""Immutable ZL runtime and compact experiment evidence; retain prior packages."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED


def main():
    r=Path('question3');out=r/'releases/q3_omni_round9.zip'
    if out.exists():raise RuntimeError('Do not overwrite release')
    lock=json.loads((r/'results/round9_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    assert json.loads((r/'configs/recommended_omni.json').read_text())==lock['configs']['ZL']
    with ZipFile(r/'releases/q3_omni_round7.zip') as z:files={Path(p) for p in z.namelist()}
    files.update(r.glob('*.py'))
    for folder,pattern in [('configs','*.json'),('tests','*.py'),('diagnostics','*.py'),('docs','*')]:
        files.update(p for p in (r/folder).rglob(pattern) if p.is_file())
    files.update([r/'STATUS.md',r/'README.md',r/'RUN_RECOMMENDED.md',r/'releases/recommended_manifest.json',r/'releases/recommended_manifest_round7.json'])
    for prefix in ['round8','round9']:
        files.update(p for p in (r/'results').glob(prefix+'_*') if p.is_file())
        for d in (r/'results').glob(prefix+'_*'):
            if d.is_dir():
                for name in ['summary.json','comparison.json','configs.json','paired_cases.csv']:
                    if (d/name).exists():files.add(d/name)
    for b,c,variants in [('round9_adverse_main','holdout_110019_negative',['REF','J','JL','ZL']),
                         ('round9_adverse_main','outer_holdout_120008_spatial_hash',['REF','ZL']),
                         ('round9_holdout_main','holdout_130023_smooth',['REF','ZL'])]:
        for v in variants:files.update((r/'results'/b/v/c).glob('*.*'))
    for d in ['round8_self_http','round9_self_http']:
        files.update(p for p in (r/'results'/d).rglob('*') if p.is_file())
    with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):
            if not p.is_file():raise RuntimeError('Missing input: '+str(p))
            z.write(p,p.as_posix())
    h=hashlib.sha256(out.read_bytes()).hexdigest();out.with_suffix('.zip.sha256').write_text(h+'  '+out.name+'\n')
    print(json.dumps(dict(path=str(out),files=len(files),bytes=out.stat().st_size,sha256=h),indent=2))


if __name__=='__main__':main()
