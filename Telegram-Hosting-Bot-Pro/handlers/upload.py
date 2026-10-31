from aiogram import Router,F,Bot
from aiogram.types import Message,CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from pathlib import Path
import os,tempfile
from cryptography.fernet import Fernet
from config import ADMIN_IDS,MAX_FILE_SIZE_MB,MAX_BOTS_PER_USER,FERNET_KEY
from utils.database import is_banned,get_user_bots,add_hosted_bot,log_action
from utils.helpers import create_user_folder,is_allowed_file,extract_zip,delete_folder
router=Router()
class Upload(StatesGroup): name=State(); token=State(); file=State()
@router.callback_query(F.data=="upload_bot")
async def begin(c:CallbackQuery,state:FSMContext):
 uid=c.from_user.id
 if await is_banned(uid): return await c.answer("محظور",show_alert=True)
 if uid not in ADMIN_IDS and len(await get_user_bots(uid))>=MAX_BOTS_PER_USER: return await c.answer("وصلت الحد المسموح",show_alert=True)
 await state.set_state(Upload.name); await c.message.edit_text("أرسل اسم المشروع (حروف/أرقام وشرطة فقط):"); await c.answer()
@router.message(Upload.name)
async def name(m:Message,state:FSMContext):
 n=(m.text or "").strip()
 if not n or len(n)>32 or not n.replace("_","").replace("-","").isalnum(): return await m.answer("اسم غير صالح.")
 await state.update_data(name=n); await state.set_state(Upload.token); await m.answer("أرسل توكن بوتك برسالة منفصلة. سيتم حذف الرسالة ومحاولة تشفير التوكن.")
@router.message(Upload.token)
async def token(m:Message,state:FSMContext):
 t=(m.text or "").strip()
 try: await m.delete()
 except Exception: pass
 if ":" not in t or len(t)<30: return await m.answer("صيغة التوكن غير صحيحة، أعد الإرسال.")
 if not FERNET_KEY: await state.clear(); return await m.answer("إعداد الخادم ناقص: FERNET_KEY غير مضبوط.")
 await state.update_data(token=t); await state.set_state(Upload.file); await m.answer(f"أرسل ملف .py أو .zip (حد {MAX_FILE_SIZE_MB}MB). لا ترفع ملفات أسرار أو بيانات شخصية.")
@router.message(Upload.file,F.document)
async def receive(m:Message,state:FSMContext,bot:Bot):
 d=m.document
 if not d.file_name or not is_allowed_file(d.file_name) or (d.file_size or 0)>MAX_FILE_SIZE_MB*1024*1024: return await m.answer("ملف غير مسموح أو يتجاوز الحد.")
 data=await state.get_data(); folder=None; tmp=None
 try:
  folder=create_user_folder(m.from_user.id,data["name"])
  fd,tmp=tempfile.mkstemp(suffix=Path(d.file_name).suffix); os.close(fd)
  f=await bot.get_file(d.file_id); await bot.download_file(f.file_path,tmp)
  if d.file_name.lower().endswith(".zip"): extract_zip(tmp,folder)
  else: os.replace(tmp,str(Path(folder)/"main.py")); tmp=None
  if not any((Path(folder)/x).is_file() for x in ("main.py","bot.py","app.py")): raise ValueError("يجب وجود main.py أو bot.py أو app.py في جذر المشروع")
  enc=Fernet(FERNET_KEY.encode()).encrypt(data["token"].encode()).decode()
  bid=await add_hosted_bot(m.from_user.id,data["name"],enc,folder)
  await log_action(m.from_user.id,"upload",f"id={bid}")
  for aid in ADMIN_IDS:
   try: await bot.send_message(aid,f"📥 طلب مراجعة جديد\nID: {bid}\nالمالك: {m.from_user.id}\nالاسم: {data['name']}")
   except Exception: pass
  await m.answer(f"✅ تم استلام المشروع. رقم الطلب: #{bid}\nالحالة: بانتظار موافقة الإدارة.")
 except Exception as e:
  if folder: delete_folder(folder)
  await m.answer(f"تعذر رفع الملف: {str(e)[:180]}")
 finally:
  if tmp and os.path.exists(tmp): os.unlink(tmp)
  await state.clear()
@router.message(Upload.file)
async def wrong(m:Message): await m.answer("أرسل ملفاً كمرفق document أو /cancel.")
@router.message(F.text=="/cancel")
async def cancel(m:Message,state:FSMContext): await state.clear(); await m.answer("تم الإلغاء.")
