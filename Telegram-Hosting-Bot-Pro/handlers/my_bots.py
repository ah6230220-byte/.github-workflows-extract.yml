from aiogram import Router,F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.database import get_user_bots
router=Router()
@router.callback_query(F.data=="my_bots")
async def mine(c:CallbackQuery):
 rows=await get_user_bots(c.from_user.id)
 if not rows: await c.message.edit_text("لا توجد مشاريع مرفوعة بعد."); await c.answer(); return
 b=InlineKeyboardBuilder(); txt="📋 <b>مشاريعك</b>\n\n"
 for bid,name,status,_ in rows:
  txt+=f"#{bid} · {name} · {status}\n"

 b.adjust(1); await c.message.edit_text(txt,reply_markup=b.as_markup(),parse_mode="HTML"); await c.answer()
