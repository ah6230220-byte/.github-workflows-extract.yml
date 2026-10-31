import os, shutil, zipfile, stat
from pathlib import Path, PurePosixPath
from config import HOSTING_DIR, MAX_EXTRACTED_MB
def create_user_folder(uid,name):
 HOSTING_DIR.mkdir(parents=True,exist_ok=True)
 p=(HOSTING_DIR/f"{uid}_{name}").resolve()
 if HOSTING_DIR not in p.parents: raise ValueError("Invalid path")
 p.mkdir(mode=0o755,parents=True,exist_ok=False); return str(p)
def is_allowed_file(name): return Path(name or "").suffix.lower() in {".py",".zip"}
def extract_zip(src,dest):
 root=Path(dest).resolve(); total=0
 with zipfile.ZipFile(src) as z:
  infos=z.infolist()
  if len(infos)>200: raise ValueError("Too many files in archive")
  for i in infos:
   pp=PurePosixPath(i.filename)
   mode=(i.external_attr>>16)&0xffff
   if pp.is_absolute() or ".." in pp.parts or not pp.parts or stat.S_ISLNK(mode): raise ValueError("Unsafe ZIP entry")
   total+=i.file_size
   if total>MAX_EXTRACTED_MB*1024*1024: raise ValueError("Extracted archive too large")
  z.extractall(root)
  for item in root.rglob("*"):
   if item.is_dir(): item.chmod(0o755)
   elif item.is_file(): item.chmod(0o644)
def delete_folder(path):
 p=Path(path).resolve()
 if HOSTING_DIR.resolve() not in p.parents: return
 shutil.rmtree(p,ignore_errors=True)
