"""Package runnable sources and compact evidence; all raw runs remain in results."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED


def main():
    root=Path('question3');out=root/'releases/q3_omni_round5.zip'
    if out.exists():raise RuntimeError('Do not overwrite an existing release')
    lock=json.loads((root/'results/round5_lock.json').read_text())
    for p,h in lock['code_sha256'].items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise RuntimeError('Code lock changed: '+p)
    # Preserve the prior package's historical reports/configs, using current runnable files.
    with ZipFile(root/'releases/q3_omni_optimized.zip') as z:
        files={Path(p) for p in z.namelist()}
    files.update(root.glob('*.py'))
    for folder,pattern in [('configs','*.json'),('tests','*.py'),('diagnostics','*.py'),('docs','*')]:
        files.update(p for p in (root/folder).rglob(pattern) if p.is_file())
    files.update([root/'STATUS.md',root/'README.md',root/'RUN_RECOMMENDED.md',root/'releases/recommended_manifest.json',root/'releases/recommended_manifest_round4.json'])
    files.update(p for p in (root/'results').glob('round5_*') if p.is_file())
    for d in (root/'results').glob('round5_*'):
        if d.is_dir():
            for n in ['summary.json','configs.json','comparison.json','paired_cases.csv']:
                if (d/n).exists():files.add(d/n)
    # Retain representative adverse action-level evidence in the compact package.
    for b,c in [('round5_holdout_main','holdout_40032_spatial_hash'),
                ('round5_structured_dev_main','structured_dev_5_positive'),
                ('round5_outer_main','outer_holdout_50000_positive')]:
        for v in ['REF','COMPACT_BATCH']:
            files.update((root/'results'/b/v/c).glob('*.*'))
    files.update(p for p in (root/'results/round5_release_http').rglob('*') if p.is_file())
    with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):
            if not p.is_file():raise RuntimeError('Missing package input: '+str(p))
            z.write(p,p.as_posix())
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(digest+'  '+out.name+'\n')
    print(json.dumps(dict(path=str(out),files=len(files),bytes=out.stat().st_size,sha256=digest),indent=2))


if __name__=='__main__':main()
