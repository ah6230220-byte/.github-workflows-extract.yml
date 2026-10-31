import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN","").strip()
if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN missing in .env")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()]
if not ADMIN_IDS: raise RuntimeError("Set ADMIN_IDS to your Telegram numeric user ID")
ROOT = Path(__file__).resolve().parent
HOSTING_DIR = Path(os.getenv("HOSTING_DIR", ROOT/"hosted_bots")).resolve()
DATABASE_PATH = str(Path(os.getenv("DATABASE_PATH", ROOT/"data/hosting.db")).resolve())
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB","10"))
MAX_BOTS_PER_USER = int(os.getenv("MAX_BOTS_PER_USER","3"))
MAX_EXTRACTED_MB = int(os.getenv("MAX_EXTRACTED_MB","30"))
FERNET_KEY = os.getenv("FERNET_KEY","").strip()
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE","python:3.12-slim")
CONTAINER_MEMORY = os.getenv("CONTAINER_MEMORY","256m")
CONTAINER_CPUS = os.getenv("CONTAINER_CPUS","0.50")
CONTAINER_PIDS = os.getenv("CONTAINER_PIDS","64")
