import asyncio,logging
from aiogram import Bot,Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from utils.database import init_db
from handlers import start,upload,my_bots,admin
async def main():
 logging.basicConfig(level=logging.INFO)
 await init_db()
 bot=Bot(BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
 dp=Dispatcher(storage=MemoryStorage())
 for r in (start.router,upload.router,my_bots.router,admin.router): dp.include_router(r)
 await dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types())
if __name__=="__main__": asyncio.run(main())
