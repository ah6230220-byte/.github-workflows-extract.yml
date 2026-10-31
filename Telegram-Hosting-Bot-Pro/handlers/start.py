from aiogram import Router,F
from aiogram.types import Message,CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS
from utils.database import add_user,is_banned
router=Router()
def main_menu_kb(admin=False):
 b=InlineKeyboardBuilder(); b.button(text="📤 رفع مشروع",callback_data="upload_bot"); b.button(text="📋 مشاريعي",callback_data="my_bots"); b.button(text="ℹ️ المساعدة",callback_data="help")
 if admin: b.button(text="🛠 لوحة الإدارة",callback_data="admin_panel")
 b.adjust(2); return b.as_markup()
@router.message(CommandStart())
async def start(m:Message):
 if await is_banned(m.from_user.id): return await m.answer("⛔ حسابك محظور.")
 await add_user(m.from_user.id,m.from_user.username,m.from_user.full_name)
 await m.answer("🚀 <b>منصة استضافة بوتات تيليجرام</b>\nارفع مشروعك، وانتظر موافقة الإدارة، ثم يمكن تشغيله داخل حاوية Docker مع حدود موارد.",reply_markup=main_menu_kb(m.from_user.id in ADMIN_IDS),parse_mode="HTML")
@router.callback_query(F.data=="help")
async def help(c:CallbackQuery):
 await c.message.edit_text("📖 أرسل مشروع Python بصيغة .py أو .zip. يجب أن يحتوي مجلد المشروع على main.py أو bot.py أو app.py. التشغيل يتطلب VPS يدعم Docker؛ الاستضافة المشتركة مثل 000webhost لا تدعم هذا النوع من تشغيل العمليات.",parse_mode="HTML"); await c.answer()
