"""Immutable public-range BOTH runtime and compact experiment evidence; retain prior packages."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED


def main():
    r=Path('question3');out=r/'releases/q3_omni_round19.zip'
    if out.exists():raise RuntimeError('Do not overwrite release')
    lock=json.loads((r/'results/round19_lock.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in lock['code_sha256'].items())
    assert json.loads((r/'configs/recommended_omni.json').read_text())==lock['configs']['BOTH']
    with ZipFile(r/'releases/q3_omni_round16.zip') as z:files={Path(p) for p in z.namelist()}
    files.update(r.glob('*.py'))
    for folder,pattern in [('configs','*.json'),('tests','*.py'),('diagnostics','*.py'),('docs','*')]:
        files.update(p for p in (r/folder).rglob(pattern) if p.is_file())
    files.update([r/'STATUS.md',r/'README.md',r/'RUN_RECOMMENDED.md',r/'releases/recommended_manifest.json',r/'releases/recommended_manifest_round16.json'])
    for prefix in ['round17','round18','round19']:
        files.update(p for p in (r/'results').glob(prefix+'_*') if p.is_file() and p.name not in ('round19_package_build.json','round19_release_package_smoke.json'))
        for d in (r/'results').glob(prefix+'_*'):
            if d.is_dir():
                for name in ['summary.json','comparison.json','configs.json','paired_cases.csv']:
                    if (d/name).exists():files.add(d/name)
    for b,c,variants in [('round19_dev_main','clustered_16',['REF','PRIMARY','SHARED','BOTH']),
                         ('round19_outer_main','outer_holdout_260007_negative',['REF','PRIMARY','SHARED','BOTH']),
                         ('round19_holdout_main','holdout_250022_positive',['REF','BOTH']),
                         ('round19_holdout_main','holdout_250019_negative',['REF','BOTH']),
                         ('round19_outer_main','outer_holdout_260006_negative',['REF','BOTH']),
                         ('round19_adverse_main','holdout_130023_smooth',['REF','BOTH']),
                         ('round19_dev_main','late_channel20_after_ten',['REF','BOTH'])]:
        for v in variants:files.update((r/'results'/b/v/c).glob('*.*'))
    for d in ['round19_self_http']:
        files.update(p for p in (r/'results'/d).rglob('*') if p.is_file())
    with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):
            if not p.is_file():raise RuntimeError('Missing input: '+str(p))
            z.write(p,p.as_posix())
    h=hashlib.sha256(out.read_bytes()).hexdigest();out.with_suffix('.zip.sha256').write_text(h+'  '+out.name+'\n')
    print(json.dumps(dict(path=str(out),files=len(files),bytes=out.stat().st_size,sha256=h),indent=2))


if __name__=='__main__':main()
