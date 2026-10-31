from aiogram import Router,F
from aiogram.types import CallbackQuery,Message,Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS
from utils.database import get_stats,get_all_bots,get_bot_by_id,set_bot_runtime,ban_user,log_action
from utils.runner import start_hosted_bot,stop_hosted_bot,container_logs
router=Router()
def admin(fn):
 async def wrap(e,*a,**kw):
  if not e.from_user or e.from_user.id not in ADMIN_IDS:
   if isinstance(e,CallbackQuery): await e.answer("غير مصرح",show_alert=True)
   else: await e.answer("غير مصرح")
   return
  return await fn(e,*a,**kw)
 return wrap
@router.callback_query(F.data=="admin_panel")
@admin
async def panel(c:CallbackQuery):
 s=await get_stats(); b=InlineKeyboardBuilder()
 for label,data in [("📊 إحصائيات","astats"),("📋 إدارة المشاريع","abots")]: b.button(text=label,callback_data=data)
 b.adjust(1); await c.message.edit_text(f"🛠 لوحة الإدارة\nالمستخدمون: {s['users']}\nالمشاريع: {s['bots']}\nقيد التشغيل: {s['running']}",reply_markup=b.as_markup()); await c.answer()
@router.callback_query(F.data=="astats")
@admin
async def stats(c:CallbackQuery):
 s=await get_stats(); await c.message.edit_text(f"المستخدمون: {s['users']}\nالمشاريع: {s['bots']}\nالشغالة: {s['running']}"); await c.answer()
@router.callback_query(F.data=="abots")
@admin
async def bots(c:CallbackQuery):
 rows=await get_all_bots(); b=InlineKeyboardBuilder(); txt="📋 المشاريع (آخر 30)\n\n"
 for bid,owner,name,status in rows:
  txt+=f"#{bid} {name} | {status} | {owner}\n"
  b.button(text=f"{'⏹ إيقاف' if status=='running' else '▶ تشغيل'} #{bid} {name}",callback_data=f"atoggle_{bid}")
  b.button(text=f"📜 سجل #{bid}",callback_data=f"alogs_{bid}")
 b.adjust(1); await c.message.edit_text(txt or "لا توجد مشاريع",reply_markup=b.as_markup()); await c.answer()
@router.callback_query(F.data.startswith("atoggle_"))
@admin
async def toggle(c:CallbackQuery,bot:Bot):
 bid=int(c.data.split("_")[-1]); row=await get_bot_by_id(bid)
 if not row: return await c.answer("غير موجود",show_alert=True)
 try:
  if row[4]=="running": await stop_hosted_bot(bid); msg="تم الإيقاف"
  else: await start_hosted_bot(bid); msg="تم التشغيل داخل Docker"
  await log_action(c.from_user.id,"toggle",f"{bid}")
  try: await bot.send_message(row[1],f"تحديث مشروعك #{bid}: {msg}")
  except Exception: pass
  await c.answer(msg,show_alert=True); await bots(c)
 except Exception as e: await c.answer(str(e)[:180],show_alert=True)
@router.callback_query(F.data.startswith("alogs_"))
@admin
async def logs(c:CallbackQuery):
 bid=int(c.data.split("_")[-1]); out=await container_logs(bid)
 await c.message.answer(f"<pre>{out[:3500]}</pre>",parse_mode="HTML"); await c.answer()
@router.message(Command("ban"))
@admin
async def ban(m:Message):
 try: uid=int(m.text.split()[1]); await ban_user(uid,True); await log_action(m.from_user.id,"ban",str(uid)); await m.answer("تم الحظر.")
 except Exception: await m.answer("استخدم /ban USER_ID")
@router.message(Command("unban"))
@admin
async def unban(m:Message):
 try: uid=int(m.text.split()[1]); await ban_user(uid,False); await log_action(m.from_user.id,"unban",str(uid)); await m.answer("تم فك الحظر.")
 except Exception: await m.answer("استخدم /unban USER_ID")
