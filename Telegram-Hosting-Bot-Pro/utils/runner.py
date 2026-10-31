import asyncio, re, shutil
from pathlib import Path
from config import DOCKER_IMAGE, CONTAINER_MEMORY, CONTAINER_CPUS, CONTAINER_PIDS
from utils.database import get_bot_by_id, set_bot_runtime
from cryptography.fernet import Fernet
from config import FERNET_KEY
def decrypt_token(value):
 if not FERNET_KEY: raise RuntimeError("FERNET_KEY is not configured")
 return Fernet(FERNET_KEY.encode()).decrypt(value.encode()).decode()
async def docker(*args,timeout=90):
 if not shutil.which("docker"): raise RuntimeError("Docker is not installed")
 p=await asyncio.create_subprocess_exec("docker",*map(str,args),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
 try: out,err=await asyncio.wait_for(p.communicate(),timeout)
 except asyncio.TimeoutError: p.kill(); await p.wait(); raise RuntimeError("Docker command timed out")
 if p.returncode: raise RuntimeError((err.decode(errors="replace") or out.decode(errors="replace"))[-800:])
 return out.decode(errors="replace").strip()
def safe_container_name(bid): return f"tg-hosted-{int(bid)}"
async def start_hosted_bot(bid):
 row=await get_bot_by_id(bid)
 if not row: raise RuntimeError("Bot record not found")
 _,owner,name,token_enc,status,folder,_,_=row
 folder_path=Path(folder).resolve()
 if not folder_path.is_dir(): raise RuntimeError("Bot files are missing")
 # Require a conventional entrypoint; never execute an arbitrary filename supplied as a command.
 entry=next((x for x in ("main.py","bot.py","app.py") if (folder_path/x).is_file()),None)
 if not entry: raise RuntimeError("Add main.py, bot.py, or app.py to the project root")
 token=decrypt_token(token_enc)
 cname=safe_container_name(bid)
 await stop_hosted_bot(bid,quiet=True)
 await docker("run","-d","--name",cname,"--restart","unless-stopped",
  "--memory",CONTAINER_MEMORY,"--cpus",CONTAINER_CPUS,"--pids-limit",CONTAINER_PIDS,
  "--read-only","--tmpfs","/tmp:rw,noexec,nosuid,size=32m",
  "--cap-drop","ALL","--security-opt","no-new-privileges:true",
  "--user","10001:10001","--network","bridge",
  "-e",f"BOT_TOKEN={token}","-v",f"{folder_path}:/app:ro",
  "-w","/app",DOCKER_IMAGE,"python","-B",entry)
 await set_bot_runtime(bid,"running",cname)
 return cname
async def stop_hosted_bot(bid,quiet=False):
 cname=safe_container_name(bid)
 try:
  await docker("rm","-f",cname)
 except Exception:
  if not quiet: raise
 await set_bot_runtime(bid,"stopped",None)
async def container_logs(bid):
 try: return await docker("logs","--tail","30",safe_container_name(bid))
 except Exception as e: return str(e)
