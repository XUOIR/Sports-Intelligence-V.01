"""Package only allowlisted source paths. No environment files or local dependencies."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import os

root=Path(__file__).resolve().parents[1]
files=[]
for folder in ('backend','frontend','docs','scripts','.github'):
    for current,directories,names in os.walk(root/folder):
        directories[:]=[d for d in directories if d not in {'node_modules','.next','__pycache__','.pytest_cache','.git'} and not d.endswith('.egg-info')]
        for name in names:
            path=Path(current)/name
            if path.is_symlink() or name.startswith('.env') or name.endswith(('.pyc','.tsbuildinfo','.log')):
                continue
            files.append(path)
for name in ('README.md','.gitignore','.dockerignore','.env.example','render.yaml','compose.yaml'):
    files.append(root/name)
target=root/'artifacts'/'Sports-Intelligence-V0.1.zip'
target.parent.mkdir(exist_ok=True)
with ZipFile(target,'w',ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path,path.relative_to(root).as_posix())
with ZipFile(target) as archive:
    assert all(not Path(name).name.startswith('.env') or name=='.env.example' for name in archive.namelist())
    assert not any('/node_modules/' in name or '/.next/' in name for name in archive.namelist())
print(f'Source archive verified: {len(files)} files, {target.stat().st_size:,} bytes')
