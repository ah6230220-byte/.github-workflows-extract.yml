import aiosqlite, os
from config import DATABASE_PATH
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
async def init_db():
 async with aiosqlite.connect(DATABASE_PATH) as db:
  await db.executescript("""
  PRAGMA journal_mode=WAL;
  CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,is_banned INTEGER DEFAULT 0,joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS hosted_bots(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_id INTEGER,bot_name TEXT,token_enc TEXT,status TEXT DEFAULT 'pending',folder_path TEXT,container_name TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,details TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
  """)
  # Migrate old DBs without exposing or deleting existing data
  cols={r[1] for r in await (await db.execute("PRAGMA table_info(hosted_bots)")).fetchall()}
  if 'token_enc' not in cols: await db.execute("ALTER TABLE hosted_bots ADD COLUMN token_enc TEXT")
  if 'container_name' not in cols: await db.execute("ALTER TABLE hosted_bots ADD COLUMN container_name TEXT")
  await db.commit()
async def add_user(uid,username=None,full_name=None):
 async with aiosqlite.connect(DATABASE_PATH) as d:
  await d.execute("INSERT INTO users(user_id,username,full_name) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,full_name=excluded.full_name",(uid,username,full_name)); await d.commit()
async def is_banned(uid):
 async with aiosqlite.connect(DATABASE_PATH) as d:
  r=await (await d.execute("SELECT is_banned FROM users WHERE user_id=?",(uid,))).fetchone(); return bool(r and r[0])
async def ban_user(uid,ban=True):
 async with aiosqlite.connect(DATABASE_PATH) as d: await d.execute("UPDATE users SET is_banned=? WHERE user_id=?",(int(ban),uid)); await d.commit()
async def get_user_bots(uid):
 async with aiosqlite.connect(DATABASE_PATH) as d: return await (await d.execute("SELECT id,bot_name,status,created_at FROM hosted_bots WHERE owner_id=? ORDER BY id DESC",(uid,))).fetchall()
async def add_hosted_bot(uid,name,token_enc,folder):
 async with aiosqlite.connect(DATABASE_PATH) as d:
  c=await d.execute("INSERT INTO hosted_bots(owner_id,bot_name,token_enc,folder_path) VALUES(?,?,?,?)",(uid,name,token_enc,folder)); await d.commit(); return c.lastrowid
async def get_bot_by_id(bid):
 async with aiosqlite.connect(DATABASE_PATH) as d: return await (await d.execute("SELECT id,owner_id,bot_name,token_enc,status,folder_path,container_name,created_at FROM hosted_bots WHERE id=?",(bid,))).fetchone()
async def get_all_bots():
 async with aiosqlite.connect(DATABASE_PATH) as d: return await (await d.execute("SELECT id,owner_id,bot_name,status FROM hosted_bots ORDER BY id DESC LIMIT 30")).fetchall()
async def set_bot_runtime(bid,status,container=None):
 async with aiosqlite.connect(DATABASE_PATH) as d: await d.execute("UPDATE hosted_bots SET status=?,container_name=? WHERE id=?",(status,container,bid)); await d.commit()
async def delete_bot(bid):
 async with aiosqlite.connect(DATABASE_PATH) as d: await d.execute("DELETE FROM hosted_bots WHERE id=?",(bid,)); await d.commit()
async def log_action(uid,action,details=""):
 async with aiosqlite.connect(DATABASE_PATH) as d: await d.execute("INSERT INTO logs(user_id,action,details) VALUES(?,?,?)",(uid,action,details[:500])); await d.commit()
async def get_stats():
 async with aiosqlite.connect(DATABASE_PATH) as d:
  users=(await (await d.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
  bots=(await (await d.execute("SELECT COUNT(*) FROM hosted_bots")).fetchone())[0]
  running=(await (await d.execute("SELECT COUNT(*) FROM hosted_bots WHERE status='running'")).fetchone())[0]
  return dict(users=users,bots=bots,running=running)
